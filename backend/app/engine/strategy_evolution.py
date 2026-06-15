"""策略自进化引擎——检测策略衰减、测试参数变体、推荐最优配置。"""

import logging
import math
import json
import copy
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import pandas as pd

from ..models import SessionLocal, StrategySnapshot, StrategyPerformance
from ..engine.registry import get_all_strategies, load_all_strategies, get_strategy
from ..engine.data_loader import StrategyDataLoader
from ..cache import CacheService

logger = logging.getLogger(__name__)


class StrategyEvolutionEngine:
    """策略自进化引擎：检测衰减、生成变体、回测优化。"""

    def __init__(self, loader: StrategyDataLoader, cache: CacheService):
        self.loader = loader
        self.cache = cache

    # ------------------------------------------------------------------
    # 衰减检测
    # ------------------------------------------------------------------
    def detect_decay(self, strategy_name: str, lookback_days: int = 20) -> Dict:
        """检测策略是否正在经历性能衰减。

        将历史分为近期(5天)和较早(15天)，比较胜率和平均收益。
        decay_score > 20 = 严重衰减, 10-20 = 轻度衰减, <10 = 正常
        """
        load_all_strategies()
        strategy = get_strategy(strategy_name)
        if not strategy:
            return {"name": strategy_name, "decay_score": 0, "status": "dormant", "error": "策略不存在"}

        session = SessionLocal()
        try:
            # 获取最近的交易日
            dates = session.query(StrategySnapshot.trade_date).filter(
                StrategySnapshot.strategy_name == strategy_name
            ).distinct().order_by(StrategySnapshot.trade_date.desc()).limit(lookback_days).all()
            dates = [d[0] for d in dates]

            if len(dates) < 3:
                return {
                    "name": strategy_name,
                    "description": strategy.description,
                    "category": strategy.category,
                    "icon": strategy.icon,
                    "decay_score": 0,
                    "status": "dormant",
                    "message": "数据不足，无法检测衰减",
                    "recent_win_rate": None,
                    "historical_win_rate": None,
                }

            # 分割：近期(前5天) vs 较早(后15天)
            recent_dates = dates[:min(5, len(dates))]
            older_dates = dates[min(5, len(dates)):]

            recent_stats = self._get_period_stats(session, strategy_name, recent_dates)
            older_stats = self._get_period_stats(session, strategy_name, older_dates) if older_dates else {"win_rate": 0, "avg_return": 0}

            # 计算衰减分数
            wr_diff = (older_stats["win_rate"] - recent_stats["win_rate"])
            ret_diff = (older_stats["avg_return"] - recent_stats["avg_return"])
            decay_score = round(wr_diff * 0.6 + ret_diff * 0.4, 2)
            decay_score = max(0, decay_score)  # 不负数

            # 确定状态
            if decay_score > 20:
                status = "declining"
            elif decay_score > 10:
                status = "mature"
            elif recent_stats["win_rate"] > older_stats["win_rate"]:
                status = "growing"
            else:
                status = "mature"

            return {
                "name": strategy_name,
                "description": strategy.description,
                "category": strategy.category,
                "icon": strategy.icon,
                "decay_score": decay_score,
                "status": status,
                "recent_win_rate": recent_stats["win_rate"],
                "historical_win_rate": older_stats["win_rate"],
                "recent_avg_return": recent_stats["avg_return"],
                "historical_avg_return": older_stats["avg_return"],
                "recent_days": len(recent_dates),
                "older_days": len(older_dates),
            }
        except Exception as exc:
            logger.error("detect_decay failed for %s: %s", strategy_name, exc)
            return {"name": strategy_name, "decay_score": 0, "status": "dormant", "error": str(exc)}
        finally:
            session.close()

    def _get_period_stats(self, session, strategy_name: str, dates: list) -> Dict:
        """计算指定日期区间的绩效统计。"""
        if not dates:
            return {"win_rate": 0, "avg_return": 0, "total_tracked": 0}

        perfs = session.query(StrategyPerformance).filter(
            StrategyPerformance.strategy_name == strategy_name,
            StrategyPerformance.trade_date.in_(dates)
        ).all()

        if not perfs:
            return {"win_rate": 0, "avg_return": 0, "total_tracked": 0}

        r1d = [p.ret_1d for p in perfs if p.ret_1d is not None]
        if not r1d:
            return {"win_rate": 0, "avg_return": 0, "total_tracked": 0}

        win_rate = round(sum(1 for v in r1d if v > 0) / len(r1d) * 100, 1)
        avg_return = round(sum(r1d) / len(r1d), 2)

        return {"win_rate": win_rate, "avg_return": avg_return, "total_tracked": len(r1d)}

    # ------------------------------------------------------------------
    # 参数变体生成
    # ------------------------------------------------------------------
    def generate_variants(self, strategy_name: str) -> List[Dict]:
        """为策略生成参数变体。

        定义关键策略的参数搜索空间：
        - low_valuation_gold: PE/PB/DV 阈值
        - high_dividend: DV/PE 阈值
        - main_fund_inflow: 净流入阈值
        - volume_breakthrough: 量比/涨幅阈值
        - ma_alignment: MA 周期组合
        """
        variant_spaces = {
            "low_valuation_gold": [
                {"pe_max": 8, "pb_max": 1.5, "dv_min": 4, "desc": "PE<8, PB<1.5, 股息>4%"},
                {"pe_max": 10, "pb_max": 1.5, "dv_min": 3, "desc": "PE<10, PB<1.5, 股息>3%"},
                {"pe_max": 10, "pb_max": 2, "dv_min": 4, "desc": "PE<10, PB<2, 股息>4%"},
                {"pe_max": 12, "pb_max": 2, "dv_min": 3, "desc": "PE<12, PB<2, 股息>3%"},
                {"pe_max": 15, "pb_max": 2.5, "dv_min": 2, "desc": "PE<15, PB<2.5, 股息>2%"},
                {"pe_max": 18, "pb_max": 2, "dv_min": 3, "desc": "PE<18, PB<2, 股息>3%"},
                {"pe_max": 20, "pb_max": 2.5, "dv_min": 2, "desc": "PE<20, PB<2.5, 股息>2%"},
            ],
            "high_dividend": [
                {"dv_min": 2, "pe_max": 15, "desc": "股息>2%, PE<15"},
                {"dv_min": 3, "pe_max": 15, "desc": "股息>3%, PE<15"},
                {"dv_min": 4, "pe_max": 20, "desc": "股息>4%, PE<20"},
                {"dv_min": 5, "pe_max": 20, "desc": "股息>5%, PE<20"},
                {"dv_min": 3, "pe_max": 25, "desc": "股息>3%, PE<25"},
                {"dv_min": 6, "pe_max": 15, "desc": "股息>6%, PE<15"},
            ],
            "main_fund_inflow": [
                {"net_min": 500, "desc": "净流入>500万"},
                {"net_min": 200, "desc": "净流入>200万"},
                {"net_min": 0, "desc": "净流入>0"},
                {"net_min": -200, "desc": "净流入>-200万(宽松)"},
                {"net_min": -500, "desc": "净流入>-500万(极宽松)"},
            ],
            "volume_breakthrough": [
                {"vol_ratio": 1.5, "pct_min": 2, "desc": "量比>1.5, 涨>2%"},
                {"vol_ratio": 2, "pct_min": 3, "desc": "量比>2, 涨>3%"},
                {"vol_ratio": 2.5, "pct_min": 3, "desc": "量比>2.5, 涨>3%"},
                {"vol_ratio": 3, "pct_min": 5, "desc": "量比>3, 涨>5%"},
                {"vol_ratio": 2, "pct_min": 2, "desc": "量比>2, 涨>2%"},
                {"vol_ratio": 1.5, "pct_min": 3, "desc": "量比>1.5, 涨>3%"},
            ],
            "ma_alignment": [
                {"ma_short": 5, "ma_mid": 10, "ma_long": 20, "desc": "MA5>MA10>MA20"},
                {"ma_short": 5, "ma_mid": 20, "ma_long": 60, "desc": "MA5>MA20>MA60"},
                {"ma_short": 10, "ma_mid": 20, "ma_long": 60, "desc": "MA10>MA20>MA60"},
                {"ma_short": 5, "ma_mid": 10, "ma_long": 30, "desc": "MA5>MA10>MA30"},
            ],
            "oversold_bounce": [
                {"drop_pct": 15, "turnover_min": 3, "desc": "跌>15%, 换手>3%"},
                {"drop_pct": 20, "turnover_min": 3, "desc": "跌>20%, 换手>3%"},
                {"drop_pct": 10, "turnover_min": 5, "desc": "跌>10%, 换手>5%"},
                {"drop_pct": 15, "turnover_min": 5, "desc": "跌>15%, 换手>5%"},
                {"drop_pct": 25, "turnover_min": 2, "desc": "跌>25%, 换手>2%"},
            ],
            "kdj_oversold_rebound": [
                {"k_threshold": 15, "desc": "K值<15"},
                {"k_threshold": 20, "desc": "K值<20"},
                {"k_threshold": 25, "desc": "K值<25"},
                {"k_threshold": 20, "j_threshold": 0, "desc": "K<20, J<0"},
            ],
            "volume_anomaly": [
                {"turnover_min": 5, "vol_ratio_min": 1.5, "desc": "换手>5%, 量比>1.5"},
                {"turnover_min": 8, "vol_ratio_min": 2, "desc": "换手>8%, 量比>2"},
                {"turnover_min": 3, "vol_ratio_min": 1.5, "desc": "换手>3%, 量比>1.5"},
                {"turnover_min": 5, "vol_ratio_min": 2.5, "desc": "换手>5%, 量比>2.5"},
            ],
        }

        variants = variant_spaces.get(strategy_name, [])
        return [{"id": i, **v} for i, v in enumerate(variants)]

    # ------------------------------------------------------------------
    # 参数变体回测
    # ------------------------------------------------------------------
    def backtest_variant(self, strategy_name: str, variant_params: Dict,
                         start_date: str, end_date: str, hold_days: int = 5, top_n: int = 30) -> Dict:
        """回测指定参数变体。

        通过临时替换策略的 check 方法来测试不同参数。
        """
        from ..engine.backtest import BacktestEngine

        strategy = get_strategy(strategy_name)
        if not strategy:
            return {"error": f"未找到策略: {strategy_name}"}

        # 保存原始 check 方法
        original_check = strategy.check

        # 创建参数化 check 方法
        def parameterized_check(data):
            return self._apply_params(strategy, original_check, data, variant_params)

        # 替换 check 方法
        strategy.check = parameterized_check

        try:
            engine = BacktestEngine(self.loader)
            result = engine.run(strategy_name, start_date, end_date, hold_days, top_n)

            if not result.get("success"):
                return {"error": result.get("error", "回测失败")}

            stats = result.get("data", {}).get("stats", {})
            equity_curve = result.get("data", {}).get("equity_curve", [])

            # 计算夏普比率
            returns = [d.get("avg_return", 0) for d in result.get("data", {}).get("daily_results", []) if d.get("avg_return") is not None]
            sharpe = self._calc_sharpe(returns)

            # 计算最大回撤
            max_dd = self._calc_max_drawdown(equity_curve)

            return {
                "win_rate": stats.get("win_rate", 0),
                "avg_return": stats.get("avg_return", 0),
                "sharpe": sharpe,
                "max_drawdown": max_dd,
                "total_return": stats.get("total_return", 0),
                "avg_picks": stats.get("avg_picks_per_day", 0),
                "total_days": stats.get("valid_days", 0),
                "params_desc": variant_params.get("desc", str(variant_params)),
            }
        finally:
            # 恢复原始 check 方法
            strategy.check = original_check

    def _apply_params(self, strategy, original_check, data: Dict, params: Dict) -> list:
        """应用参数变体到策略检查。

        对于支持参数化的策略，修改筛选条件。
        """
        df = data.get("daily_basic")
        if df is None or df.empty:
            return original_check(data)

        strategy_name = strategy.name

        if strategy_name == "low_valuation_gold":
            return self._check_low_valuation_variant(df, data, params, strategy)
        elif strategy_name == "high_dividend":
            return self._check_high_dividend_variant(df, data, params, strategy)
        elif strategy_name == "main_fund_inflow":
            return self._check_main_fund_variant(df, data, params, strategy)
        elif strategy_name == "volume_breakthrough":
            return self._check_volume_breakthrough_variant(df, data, params, strategy)
        elif strategy_name == "oversold_bounce":
            return self._check_oversold_bounce_variant(df, data, params, strategy)
        elif strategy_name == "kdj_oversold_rebound":
            return self._check_kdj_variant(df, data, params, strategy)
        elif strategy_name == "volume_anomaly":
            return self._check_volume_anomaly_variant(df, data, params, strategy)
        else:
            return original_check(data)

    def _check_low_valuation_variant(self, df, data, params, strategy):
        pe_max = params.get("pe_max", 15)
        pb_max = params.get("pb_max", 2)
        dv_min = params.get("dv_min", 3)

        pe_col = strategy._find_col(df, ["pe_ttm", "pt"])
        pb_col = strategy._find_col(df, ["pb"])
        dv_col = strategy._find_col(df, ["dv_ratio", "dr"])
        mv_col = strategy._find_col(df, ["total_mv", "tmv"])
        name_col = strategy._find_col(df, ["name", "nm"])
        code_col = strategy._find_col(df, ["ts_code", "tc"])

        if not all([pe_col, pb_col, dv_col, mv_col, code_col]):
            return []

        results = []
        for _, row in df.iterrows():
            pe_ttm = strategy._safe(row, pe_col)
            pb = strategy._safe(row, pb_col)
            dv = strategy._safe(row, dv_col)
            mv = strategy._safe(row, mv_col)

            if pe_ttm is None or pb is None or dv is None or mv is None:
                continue
            if pe_ttm <= 0 or pe_ttm >= pe_max:
                continue
            if pb <= 0 or pb >= pb_max:
                continue
            if dv < dv_min:
                continue
            if mv < 5000000:
                continue

            ts_code = str(row.get(code_col, ""))
            stock_name = str(row.get(name_col, "")) if name_col else ts_code

            pe_score = max(0, min(50, (pe_max - pe_ttm) / pe_max * 50))
            dv_score = max(0, min(30, (dv - dv_min) / 5 * 30))
            pb_score = max(0, min(20, (pb_max - pb) / pb_max * 20))
            total_score = pe_score + dv_score + pb_score

            from ..base import StrategyResult
            results.append(StrategyResult(
                ts_code=ts_code, name=stock_name, score=total_score,
                signals={"pe_ttm": pe_ttm, "pb": pb, "dv_ratio": dv},
                reason=f"PE={pe_ttm:.1f}, PB={pb:.2f}, 股息={dv:.1f}%",
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _check_high_dividend_variant(self, df, data, params, strategy):
        dv_min = params.get("dv_min", 3)
        pe_max = params.get("pe_max", 20)

        pe_col = strategy._find_col(df, ["pe_ttm", "pt"])
        dv_col = strategy._find_col(df, ["dv_ratio", "dr"])
        mv_col = strategy._find_col(df, ["total_mv", "tmv"])
        name_col = strategy._find_col(df, ["name", "nm"])
        code_col = strategy._find_col(df, ["ts_code", "tc"])

        if not all([pe_col, dv_col, code_col]):
            return []

        results = []
        for _, row in df.iterrows():
            pe = strategy._safe(row, pe_col)
            dv = strategy._safe(row, dv_col)
            mv = strategy._safe(row, mv_col)

            if pe is None or dv is None:
                continue
            if pe <= 0 or pe >= pe_max:
                continue
            if dv < dv_min:
                continue
            if mv and mv < 3000000:
                continue

            ts_code = str(row.get(code_col, ""))
            stock_name = str(row.get(name_col, "")) if name_col else ts_code

            score = min(100, dv * 10 + max(0, (pe_max - pe) / pe_max * 50))

            from ..base import StrategyResult
            results.append(StrategyResult(
                ts_code=ts_code, name=stock_name, score=score,
                signals={"pe_ttm": pe, "dv_ratio": dv},
                reason=f"股息率={dv:.1f}%, PE={pe:.1f}",
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _check_main_fund_variant(self, df, data, params, strategy):
        net_min = params.get("net_min", 0)

        code_col = strategy._find_col(df, ["ts_code", "tc"])
        net_col = strategy._find_col(df, ["net_amount", "net_mf_amount"])
        name_col = strategy._find_col(df, ["name", "nm"])

        if not all([code_col, net_col]):
            return []

        results = []
        for _, row in df.iterrows():
            net = strategy._safe(row, net_col)
            if net is None or net < net_min:
                continue

            ts_code = str(row.get(code_col, ""))
            stock_name = str(row.get(name_col, "")) if name_col else ts_code

            score = min(100, max(0, net / 1000 * 50 + 50))

            from ..base import StrategyResult
            results.append(StrategyResult(
                ts_code=ts_code, name=stock_name, score=score,
                signals={"net_amount": net},
                reason=f"主力净流入={net:.0f}万",
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _check_volume_breakthrough_variant(self, df, data, params, strategy):
        vol_ratio = params.get("vol_ratio", 2)
        pct_min = params.get("pct_min", 3)

        daily = data.get("daily_basic")
        if daily is None or daily.empty:
            return []

        code_col = strategy._find_col(daily, ["ts_code", "tc"])
        vr_col = strategy._find_col(daily, ["volume_ratio", "vr"])
        pct_col = strategy._find_col(daily, ["pct_change", "pc"])
        mv_col = strategy._find_col(daily, ["total_mv", "tmv"])
        name_col = strategy._find_col(daily, ["name", "nm"])

        if not all([code_col, vr_col, pct_col]):
            return []

        results = []
        for _, row in daily.iterrows():
            vr = strategy._safe(row, vr_col)
            pct = strategy._safe(row, pct_col)
            mv = strategy._safe(row, mv_col)

            if vr is None or pct is None:
                continue
            if vr < vol_ratio or pct < pct_min:
                continue
            if mv and mv < 3000000:
                continue

            ts_code = str(row.get(code_col, ""))
            stock_name = str(row.get(name_col, "")) if name_col else ts_code

            score = min(100, vr * 20 + pct * 5)

            from ..base import StrategyResult
            results.append(StrategyResult(
                ts_code=ts_code, name=stock_name, score=score,
                signals={"volume_ratio": vr, "pct_change": pct},
                reason=f"量比={vr:.1f}, 涨幅={pct:.1f}%",
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _check_oversold_bounce_variant(self, df, data, params, strategy):
        drop_pct = params.get("drop_pct", 15)
        turnover_min = params.get("turnover_min", 3)

        daily_basic = data.get("daily_basic")
        if daily_basic is None or daily_basic.empty:
            return []

        code_col = strategy._find_col(daily_basic, ["ts_code", "tc"])
        tr_col = strategy._find_col(daily_basic, ["turnover_rate", "tr"])
        mv_col = strategy._find_col(daily_basic, ["total_mv", "tmv"])
        name_col = strategy._find_col(daily_basic, ["name", "nm"])

        # Use daily_multi to calculate 20-day drop
        daily_multi = data.get("daily_multi")
        if daily_multi is None or daily_multi.empty:
            return []

        results = []
        # Group by ts_code to calculate drop
        for ts_code, group in daily_multi.groupby("ts_code"):
            if len(group) < 2:
                continue
            group = group.sort_values("trade_date")
            first_close = group.iloc[0].get("close", 0)
            last_close = group.iloc[-1].get("close", 0)
            if first_close == 0:
                continue
            drop = (last_close - first_close) / first_close * 100
            if drop > -drop_pct:
                continue

            # Check turnover from daily_basic
            tr_row = daily_basic[daily_basic[code_col] == ts_code] if code_col in daily_basic.columns else pd.DataFrame()
            if tr_row.empty:
                continue
            tr = strategy._safe(tr_row.iloc[0], tr_col) if tr_col else None
            mv = strategy._safe(tr_row.iloc[0], mv_col) if mv_col else None
            nm = str(tr_row.iloc[0].get(name_col, "")) if name_col and not tr_row.empty else ts_code

            if tr is None or tr < turnover_min:
                continue
            if mv and (mv < 3000000 or mv > 50000000):
                continue

            score = min(100, abs(drop) * 3 + tr * 5)

            from ..base import StrategyResult
            results.append(StrategyResult(
                ts_code=ts_code, name=nm, score=score,
                signals={"drop_pct": round(drop, 2), "turnover_rate": tr},
                reason=f"跌幅={drop:.1f}%, 换手={tr:.1f}%",
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _check_kdj_variant(self, df, data, params, strategy):
        k_thresh = params.get("k_threshold", 20)
        j_thresh = params.get("j_threshold", None)

        stk = data.get("stk_factor")
        if stk is None or stk.empty:
            return []

        code_col = strategy._find_col(stk, ["ts_code", "tc"])
        k_col = strategy._find_col(stk, ["kdj_k", "k"])
        d_col = strategy._find_col(stk, ["kdj_d", "d"])
        j_col = strategy._find_col(stk, ["kdj_j", "j"])
        name_col = strategy._find_col(stk, ["name", "nm"])

        if not all([code_col, k_col, d_col]):
            return []

        results = []
        for _, row in stk.iterrows():
            k = strategy._safe(row, k_col)
            d = strategy._safe(row, d_col)
            j = strategy._safe(row, j_col) if j_col else None

            if k is None or d is None:
                continue
            if k >= k_thresh:
                continue
            if j_thresh is not None and j is not None and j >= j_thresh:
                continue
            if k <= d:
                continue

            ts_code = str(row.get(code_col, ""))
            stock_name = str(row.get(name_col, "")) if name_col else ts_code

            score = min(100, (k_thresh - k) * 5 + 30)

            from ..base import StrategyResult
            results.append(StrategyResult(
                ts_code=ts_code, name=stock_name, score=score,
                signals={"kdj_k": k, "kdj_d": d, "kdj_j": j},
                reason=f"K={k:.1f}, D={d:.1f}" + (f", J={j:.1f}" if j else ""),
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def _check_volume_anomaly_variant(self, df, data, params, strategy):
        turnover_min = params.get("turnover_min", 5)
        vol_ratio_min = params.get("vol_ratio_min", 1.5)

        daily_basic = data.get("daily_basic")
        if daily_basic is None or daily_basic.empty:
            return []

        code_col = strategy._find_col(daily_basic, ["ts_code", "tc"])
        tr_col = strategy._find_col(daily_basic, ["turnover_rate", "tr"])
        vr_col = strategy._find_col(daily_basic, ["volume_ratio", "vr"])
        pct_col = strategy._find_col(daily_basic, ["pct_change", "pc"])
        mv_col = strategy._find_col(daily_basic, ["total_mv", "tmv"])
        name_col = strategy._find_col(daily_basic, ["name", "nm"])

        if not all([code_col, tr_col]):
            return []

        results = []
        for _, row in daily_basic.iterrows():
            tr = strategy._safe(row, tr_col)
            vr = strategy._safe(row, vr_col) if vr_col else None
            pct = strategy._safe(row, pct_col) if pct_col else None
            mv = strategy._safe(row, mv_col) if mv_col else None

            if tr is None or tr < turnover_min:
                continue
            if vr is not None and vr < vol_ratio_min:
                continue
            if pct is not None and pct <= 0:
                continue
            if mv and mv < 3000000:
                continue

            ts_code = str(row.get(code_col, ""))
            stock_name = str(row.get(name_col, "")) if name_col else ts_code

            score = min(100, tr * 5 + (vr or 0) * 15 + (pct or 0) * 3)

            from ..base import StrategyResult
            results.append(StrategyResult(
                ts_code=ts_code, name=stock_name, score=score,
                signals={"turnover_rate": tr, "volume_ratio": vr, "pct_change": pct},
                reason=f"换手={tr:.1f}%, 量比={vr or 0:.1f}",
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    # ------------------------------------------------------------------
    # 统计计算
    # ------------------------------------------------------------------
    @staticmethod
    def _calc_sharpe(returns: list, risk_free_rate: float = 0) -> float:
        """计算年化夏普比率。"""
        if not returns or len(returns) < 2:
            return 0
        avg = sum(returns) / len(returns)
        variance = sum((r - avg) ** 2 for r in returns) / (len(returns) - 1)
        std = math.sqrt(variance) if variance > 0 else 0.001
        return round((avg - risk_free_rate) / std * math.sqrt(252), 2)

    @staticmethod
    def _calc_max_drawdown(equity_curve: list) -> float:
        """计算最大回撤百分比。"""
        if not equity_curve:
            return 0
        peak = equity_curve[0].get("value", 100)
        max_dd = 0
        for point in equity_curve:
            val = point.get("value", 100)
            if val > peak:
                peak = val
            dd = (peak - val) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        return round(max_dd, 2)

    # ------------------------------------------------------------------
    # 策略优化
    # ------------------------------------------------------------------
    def optimize_strategy(self, strategy_name: str, start_date: str = None, end_date: str = None,
                          hold_days: int = 5, top_n: int = 30) -> Dict:
        """完整优化：生成变体、回测所有、按夏普比率排名。"""
        load_all_strategies()
        strategy = get_strategy(strategy_name)
        if not strategy:
            return {"error": f"未找到策略: {strategy_name}"}

        # 默认日期范围：最近60个交易日
        if not start_date or not end_date:
            session = SessionLocal()
            try:
                dates = session.query(StrategySnapshot.trade_date).distinct().order_by(
                    StrategySnapshot.trade_date.desc()
                ).limit(60).all()
                dates = [d[0] for d in dates]
                if len(dates) < 10:
                    return {"error": "历史数据不足，至少需要10个交易日的策略执行记录"}
                end_date = dates[0]
                start_date = dates[-1]
            finally:
                session.close()

        # 生成变体
        variants = self.generate_variants(strategy_name)
        if not variants:
            return {"error": f"策略 {strategy_name} 暂不支持参数优化"}

        # 回测原始参数
        original_result = self.backtest_variant(
            strategy_name, {"desc": "原始参数"}, start_date, end_date, hold_days, top_n
        )

        # 回测所有变体
        all_results = []
        for variant in variants:
            try:
                result = self.backtest_variant(
                    strategy_name, variant, start_date, end_date, hold_days, top_n
                )
                if "error" not in result:
                    all_results.append({
                        "id": variant["id"],
                        "params_desc": variant["desc"],
                        "params": {k: v for k, v in variant.items() if k not in ("id", "desc")},
                        **result,
                    })
            except Exception as exc:
                logger.warning("Variant %s backtest failed: %s", variant["desc"], exc)

        # 按夏普比率排名
        all_results.sort(key=lambda x: x.get("sharpe", 0), reverse=True)
        for i, r in enumerate(all_results):
            r["rank"] = i + 1
            r["is_best"] = i == 0

        best = all_results[0] if all_results else None

        return {
            "strategy_name": strategy_name,
            "description": strategy.description,
            "category": strategy.category,
            "date_range": {"start": start_date, "end": end_date},
            "hold_days": hold_days,
            "top_n": top_n,
            "original": original_result,
            "best_variant": best,
            "all_variants": all_results,
            "total_variants_tested": len(all_results),
        }

    # ------------------------------------------------------------------
    # 进化报告
    # ------------------------------------------------------------------
    def get_evolution_report(self) -> Dict:
        """生成所有策略的综合进化报告。"""
        load_all_strategies()
        strategies = get_all_strategies()

        decay_results = []
        recommendations = []
        lifecycle_counts = {"growing": 0, "mature": 0, "declining": 0, "dormant": 0}

        for name in strategies:
            try:
                decay = self.detect_decay(name, lookback_days=20)
                decay_results.append(decay)

                status = decay.get("status", "dormant")
                lifecycle_counts[status] = lifecycle_counts.get(status, 0) + 1

                # 生成建议
                if decay.get("decay_score", 0) > 20:
                    recommendations.append({
                        "strategy_name": name,
                        "icon": decay.get("icon", ""),
                        "priority": "high",
                        "message": f"严重衰减(分数={decay['decay_score']:.1f})，建议立即优化参数",
                    })
                elif decay.get("decay_score", 0) > 10:
                    recommendations.append({
                        "strategy_name": name,
                        "icon": decay.get("icon", ""),
                        "priority": "medium",
                        "message": f"轻度衰减(分数={decay['decay_score']:.1f})，建议关注参数调整",
                    })
                elif decay.get("status") == "growing":
                    recommendations.append({
                        "strategy_name": name,
                        "icon": decay.get("icon", ""),
                        "priority": "low",
                        "message": f"表现提升中，当前配置有效",
                    })
            except Exception as exc:
                logger.warning("Evolution report failed for %s: %s", name, exc)

        # 按衰减分数排序
        decay_results.sort(key=lambda x: x.get("decay_score", 0), reverse=True)
        recommendations.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x["priority"], 3))

        return {
            "total_strategies": len(strategies),
            "total_analyzed": len(decay_results),
            "lifecycle": lifecycle_counts,
            "growing": lifecycle_counts.get("growing", 0),
            "mature": lifecycle_counts.get("mature", 0),
            "declining": lifecycle_counts.get("declining", 0),
            "dormant": lifecycle_counts.get("dormant", 0),
            "strategies": decay_results,
            "recommendations": recommendations,
            "generated_at": datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # 生命周期追踪
    # ------------------------------------------------------------------
    def get_strategy_lifecycle(self, strategy_name: str) -> Dict:
        """追踪策略的生命周期：出生、成长、成熟、衰退。"""
        load_all_strategies()
        strategy = get_strategy(strategy_name)
        if not strategy:
            return {"error": f"未找到策略: {strategy_name}"}

        session = SessionLocal()
        try:
            # 获取所有快照
            snapshots = session.query(StrategySnapshot).filter(
                StrategySnapshot.strategy_name == strategy_name
            ).order_by(StrategySnapshot.trade_date.asc()).all()

            if not snapshots:
                return {
                    "strategy_name": strategy_name,
                    "description": strategy.description,
                    "category": strategy.category,
                    "phase": "dormant",
                    "message": "暂无执行记录",
                    "timeline": [],
                }

            # 构建时间线
            timeline = []
            for sp in snapshots:
                perfs = session.query(StrategyPerformance).filter_by(
                    trade_date=sp.trade_date, strategy_name=strategy_name
                ).all()
                r1d = [p.ret_1d for p in perfs if p.ret_1d is not None]
                win_rate = round(sum(1 for v in r1d if v > 0) / len(r1d) * 100, 1) if r1d else 0
                avg_ret = round(sum(r1d) / len(r1d), 2) if r1d else 0

                timeline.append({
                    "date": sp.trade_date,
                    "pick_count": sp.pick_count,
                    "avg_score": sp.avg_score,
                    "win_rate_1d": win_rate,
                    "avg_return_1d": avg_ret,
                    "tracked_count": len(r1d),
                })

            # 判断生命周期阶段
            if len(timeline) < 5:
                phase = "growing"
                phase_desc = "成长期——数据积累中"
            else:
                recent = timeline[-5:]
                older = timeline[:-5] if len(timeline) > 5 else timeline

                recent_wr = sum(d["win_rate_1d"] for d in recent) / len(recent)
                older_wr = sum(d["win_rate_1d"] for d in older) / len(older) if older else 0

                if recent_wr > older_wr + 5:
                    phase = "growing"
                    phase_desc = "成长期——表现持续提升"
                elif recent_wr < older_wr - 10:
                    phase = "declining"
                    phase_desc = "衰退期——表现明显下滑"
                else:
                    phase = "mature"
                    phase_desc = "成熟期——表现稳定"

            # 计算总体统计
            all_returns = [d["avg_return_1d"] for d in timeline if d["avg_return_1d"] != 0]
            overall_win_rate = round(
                sum(1 for d in timeline if d["win_rate_1d"] > 50) / len(timeline) * 100, 1
            ) if timeline else 0

            return {
                "strategy_name": strategy_name,
                "description": strategy.description,
                "category": strategy.category,
                "icon": strategy.icon,
                "phase": phase,
                "phase_description": phase_desc,
                "birth_date": snapshots[0].trade_date,
                "latest_date": snapshots[-1].trade_date,
                "total_snapshots": len(snapshots),
                "overall_win_rate": overall_win_rate,
                "avg_picks_per_day": round(sum(d["pick_count"] for d in timeline) / len(timeline), 1),
                "timeline": timeline[-30:],  # 最近30天
            }
        except Exception as exc:
            logger.error("get_strategy_lifecycle failed: %s", exc)
            return {"error": str(exc)}
        finally:
            session.close()
