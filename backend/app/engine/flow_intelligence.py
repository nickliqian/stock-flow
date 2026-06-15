"""资金流向背离信号引擎——检测价格与资金流向的背离信号。

- 看涨背离（Bullish Divergence）：价格下跌 + 主力资金净流入 → 机构吸筹
- 看跌背离（Bearish Divergence）：价格上涨 + 主力资金净流出 → 机构出货
"""

import logging
from typing import Dict, Any, List, Optional
import pandas as pd

from ..clients.tushare import TuShareClient
from ..cache import CacheService
from ..engine.data_loader import StrategyDataLoader
from ..utils import get_last_n_trade_dates, get_latest_trade_date

logger = logging.getLogger(__name__)


class FlowIntelligenceEngine:
    """资金流向背离分析引擎。"""

    def __init__(self, client: TuShareClient, cache: CacheService):
        self.client = client
        self.cache = cache
        self.loader = StrategyDataLoader(client, cache)

    # ------------------------------------------------------------------
    # 市场级背离扫描
    # ------------------------------------------------------------------
    def detect_divergence(
        self,
        trade_date: Optional[str] = None,
        lookback_days: int = 10,
        signal_type: str = "all",
        min_strength: float = 50,
    ) -> Dict[str, Any]:
        """市场级背离扫描——检测价格与资金流向的背离信号。"""
        try:
            if not trade_date:
                trade_date = get_latest_trade_date(self.cache)

            # 加载数据
            daily_df = self.loader._load_daily_multi(trade_date, days=lookback_days + 5)
            mf_df = self.loader._load_moneyflow_multi(trade_date, days=lookback_days + 5)
            basic_df = self.loader._load_daily_basic(trade_date)
            sb_df = self.loader._load_stock_basic(trade_date)

            if daily_df is None or daily_df.empty:
                return {"success": True, "data": self._empty_result(trade_date, lookback_days, signal_type)}
            if mf_df is None or mf_df.empty:
                return {"success": True, "data": self._empty_result(trade_date, lookback_days, signal_type)}

            # 构建名称/行业映射
            name_map, industry_map = self._build_stock_maps(sb_df)

            # 构建市值映射
            mv_map = {}
            if basic_df is not None and not basic_df.empty:
                for _, row in basic_df.iterrows():
                    code = str(row.get("ts_code", ""))
                    mv = self._safe_val(row, "total_mv")
                    if code and mv is not None:
                        mv_map[code] = mv

            # 获取最近N个交易日列表
            trade_dates = sorted(daily_df["trade_date"].unique())[-lookback_days:]
            mf_dates = sorted(mf_df["trade_date"].unique())[-lookback_days:]

            # 获取所有股票代码（交集）
            daily_codes = set(daily_df["ts_code"].unique()) if "ts_code" in daily_df.columns else set()
            mf_codes = set(mf_df["ts_code"].unique()) if "ts_code" in mf_df.columns else set()
            all_codes = daily_codes & mf_codes

            results = []
            for ts_code in all_codes:
                name = name_map.get(ts_code, ts_code)
                industry = industry_map.get(ts_code, "")

                # 过滤 ST
                if "ST" in str(name).upper():
                    continue

                # 市值过滤：>30亿
                mv = mv_map.get(ts_code)
                if mv is not None and mv < 300000:  # 30亿 = 300000万元
                    continue

                # 提取该股票的价格序列
                stock_daily = daily_df[daily_df["ts_code"] == ts_code].sort_values("trade_date")
                stock_mf = mf_df[mf_df["ts_code"] == ts_code].sort_values("trade_date")

                if len(stock_daily) < 3 or len(stock_mf) < 3:
                    continue

                # 计算趋势
                price_trend = self._calc_price_trend(stock_daily, lookback_days)
                flow_trend = self._calc_flow_trend(stock_mf, lookback_days)

                if price_trend is None or flow_trend is None:
                    continue

                # 检测背离
                divergence = self._detect_single_divergence(
                    price_trend, flow_trend, stock_daily, stock_mf, lookback_days
                )
                if divergence is None:
                    continue

                # 按信号类型过滤
                if signal_type != "all" and divergence["signal_type"] != signal_type:
                    continue

                # 按强度过滤
                if divergence["signal_strength"] < min_strength:
                    continue

                divergence["ts_code"] = ts_code
                divergence["name"] = name
                divergence["industry"] = industry
                results.append(divergence)

            # 按信号强度排序
            results.sort(key=lambda x: x["signal_strength"], reverse=True)

            # 统计
            bullish = sum(1 for r in results if r["signal_type"] == "bullish")
            bearish = sum(1 for r in results if r["signal_type"] == "bearish")
            strong = sum(1 for r in results if r["signal_strength"] > 70)

            return {
                "success": True,
                "data": {
                    "trade_date": trade_date,
                    "lookback_days": lookback_days,
                    "summary": {
                        "total_scanned": len(all_codes),
                        "bullish_divergence": bullish,
                        "bearish_divergence": bearish,
                        "strong_signals": strong,
                    },
                    "results": results,
                    "signal_type": signal_type,
                },
            }

        except Exception as exc:
            logger.error("detect_divergence failed: %s", exc)
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # 单股深度分析
    # ------------------------------------------------------------------
    def analyze_stock(
        self, ts_code: str, lookback_days: int = 10
    ) -> Dict[str, Any]:
        """深度分析单只股票的资金流向背离信号。"""
        try:
            trade_date = get_latest_trade_date(self.cache)

            # 加载数据
            daily_df = self.loader._load_daily_multi(trade_date, days=lookback_days + 5)
            mf_df = self.loader._load_moneyflow_multi(trade_date, days=lookback_days + 5)
            basic_df = self.loader._load_daily_basic(trade_date)
            sb_df = self.loader._load_stock_basic(trade_date)

            name_map, industry_map = self._build_stock_maps(sb_df)
            name = name_map.get(ts_code, ts_code)
            industry = industry_map.get(ts_code, "")

            # 市值
            mv = None
            if basic_df is not None and not basic_df.empty:
                for _, row in basic_df[basic_df["ts_code"] == ts_code].iterrows():
                    mv = self._safe_val(row, "total_mv")

            # 股价数据
            stock_daily = pd.DataFrame()
            if daily_df is not None and not daily_df.empty:
                stock_daily = daily_df[daily_df["ts_code"] == ts_code].sort_values("trade_date")

            # 资金流数据
            stock_mf = pd.DataFrame()
            if mf_df is not None and not mf_df.empty:
                stock_mf = mf_df[mf_df["ts_code"] == ts_code].sort_values("trade_date")

            if stock_daily.empty or stock_mf.empty:
                return {
                    "success": True,
                    "data": {
                        "ts_code": ts_code,
                        "name": name,
                        "industry": industry,
                        "current_signal": "none",
                        "signal_strength": 0,
                        "lookback_days": lookback_days,
                        "daily_detail": [],
                        "flow_momentum": {},
                        "flow_persistence": {},
                        "divergence_analysis": {
                            "price_trend": "flat",
                            "flow_trend": "flat",
                            "divergence_type": "none",
                            "strength": 0,
                            "interpretation": "数据不足，无法分析",
                        },
                    },
                }

            # 取最近 lookback_days 天
            stock_daily_lb = stock_daily.tail(lookback_days)
            stock_mf_lb = stock_mf.tail(lookback_days)

            # 构建每日明细
            daily_detail = []
            merged = pd.merge(
                stock_daily_lb[["trade_date", "close", "pct_chg"]],
                stock_mf_lb[["trade_date", "buy_lg_amount", "sell_lg_amount",
                             "buy_elg_amount", "sell_elg_amount", "net_mf_amount"]],
                on="trade_date",
                how="inner",
            )

            for _, row in merged.iterrows():
                buy_lg = self._safe_val(row, "buy_lg_amount") or 0
                sell_lg = self._safe_val(row, "sell_lg_amount") or 0
                buy_elg = self._safe_val(row, "buy_elg_amount") or 0
                sell_elg = self._safe_val(row, "sell_elg_amount") or 0
                main_fund_net = (buy_lg - sell_lg) + (buy_elg - sell_elg)

                daily_detail.append({
                    "trade_date": str(row.get("trade_date", "")),
                    "close": round(float(row.get("close", 0) or 0), 2),
                    "pct_change": round(float(row.get("pct_chg", 0) or 0), 2),
                    "main_fund_net": round(main_fund_net, 2),
                    "main_fund_net_rate": round(main_fund_net / 10000, 2) if main_fund_net else 0,
                })

            # 趋势计算
            price_trend = self._calc_price_trend(stock_daily, lookback_days)
            flow_trend = self._calc_flow_trend(stock_mf, lookback_days)

            # 背离检测
            divergence = self._detect_single_divergence(
                price_trend, flow_trend, stock_daily, stock_mf, lookback_days
            )

            if divergence is None:
                divergence_type = "none"
                strength = 0
                interpretation = "价格与资金流向未出现明显背离"
                price_trend_dir = "flat"
                flow_trend_dir = "flat"
            else:
                divergence_type = divergence["signal_type"]
                strength = divergence["signal_strength"]
                price_trend_dir = "down" if divergence.get("price_trend", 0) < 0 else "up"
                flow_trend_dir = "up" if divergence.get("flow_trend", 0) > 0 else "down"

                if divergence_type == "bullish":
                    interpretation = "价格连续下跌但主力资金持续净流入，可能存在机构吸筹行为"
                else:
                    interpretation = "价格持续上涨但主力资金持续净流出，可能存在机构出货行为"

            # 流量动量
            flow_momentum = self._calc_flow_momentum(stock_mf_lb)

            # 流量持续性
            flow_persistence = self._calc_flow_persistence(stock_mf_lb)

            # 获取5日趋势
            price_trend_5d = self._calc_price_trend(stock_daily, min(5, lookback_days))
            flow_trend_5d = self._calc_flow_trend(stock_mf, min(5, lookback_days))

            return {
                "success": True,
                "data": {
                    "ts_code": ts_code,
                    "name": name,
                    "industry": industry,
                    "current_signal": divergence_type,
                    "signal_strength": strength,
                    "lookback_days": lookback_days,
                    "price_trend": round(price_trend, 2) if price_trend else 0,
                    "flow_trend": round(flow_trend, 2) if flow_trend else 0,
                    "price_trend_5d": round(price_trend_5d, 2) if price_trend_5d else 0,
                    "flow_trend_5d": round(flow_trend_5d, 2) if flow_trend_5d else 0,
                    "total_mv_yi": round(mv / 10000, 2) if mv else None,
                    "daily_detail": daily_detail,
                    "flow_momentum": flow_momentum,
                    "flow_persistence": flow_persistence,
                    "divergence_analysis": {
                        "price_trend": price_trend_dir,
                        "flow_trend": flow_trend_dir,
                        "divergence_type": divergence_type,
                        "strength": strength,
                        "interpretation": interpretation,
                    },
                },
            }

        except Exception as exc:
            logger.error("analyze_stock failed for %s: %s", ts_code, exc)
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_val(row, col):
        try:
            v = row.get(col) if hasattr(row, "get") else row[col]
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            return float(v)
        except (ValueError, TypeError, KeyError):
            return None

    @staticmethod
    def _build_stock_maps(sb_df):
        name_map = {}
        industry_map = {}
        if sb_df is not None and not sb_df.empty:
            for _, row in sb_df.iterrows():
                code = str(row.get("ts_code", ""))
                if code:
                    name_map[code] = str(row.get("name", ""))
                    industry_map[code] = str(row.get("industry", ""))
        return name_map, industry_map

    def _calc_price_trend(self, stock_daily: pd.DataFrame, lookback: int) -> Optional[float]:
        """计算价格趋势（累计涨跌幅%）。"""
        if stock_daily.empty:
            return None
        recent = stock_daily.tail(lookback)
        if len(recent) < 2:
            return None

        closes = recent["close"].tolist()
        if closes[0] and closes[0] > 0:
            return (closes[-1] / closes[0] - 1) * 100
        return None

    def _calc_flow_trend(self, stock_mf: pd.DataFrame, lookback: int) -> Optional[float]:
        """计算主力资金流向趋势（累计净流入万元）。

        主力资金 = (buy_lg - sell_lg) + (buy_elg - sell_elg)
        """
        if stock_mf.empty:
            return None
        recent = stock_mf.tail(lookback)
        if len(recent) < 2:
            return None

        total = 0.0
        for _, row in recent.iterrows():
            buy_lg = self._safe_val(row, "buy_lg_amount") or 0
            sell_lg = self._safe_val(row, "sell_lg_amount") or 0
            buy_elg = self._safe_val(row, "buy_elg_amount") or 0
            sell_elg = self._safe_val(row, "sell_elg_amount") or 0
            total += (buy_lg - sell_lg) + (buy_elg - sell_elg)

        return total

    def _detect_single_divergence(
        self,
        price_trend: float,
        flow_trend: float,
        stock_daily: pd.DataFrame,
        stock_mf: pd.DataFrame,
        lookback: int,
    ) -> Optional[Dict[str, Any]]:
        """检测单只股票的背离信号。"""
        # 看涨背离：价格下跌 + 资金净流入
        is_bullish = price_trend < -0.5 and flow_trend > 500  # 价格跌>0.5%, 资金净流入>500万
        # 看跌背离：价格上涨 + 资金净流出
        is_bearish = price_trend > 0.5 and flow_trend < -500

        if not is_bullish and not is_bearish:
            return None

        signal_type = "bullish" if is_bullish else "bearish"

        # 计算信号强度
        # 价格趋势贡献（绝对值越大信号越强）
        price_strength = min(40, abs(price_trend) * 4)
        # 资金流向贡献（绝对值越大信号越强）
        flow_strength = min(30, abs(flow_trend) / 1000 * 5)
        # 持续性贡献
        persistence_score = self._calc_persistence_score(stock_daily, stock_mf, lookback)
        persistence_strength = min(30, persistence_score * 0.3)

        signal_strength = min(100, price_strength + flow_strength + persistence_strength)

        # 计算5日趋势
        recent_daily = stock_daily.tail(5)
        recent_mf = stock_mf.tail(5)
        price_trend_5d = 0
        flow_trend_5d = 0
        if len(recent_daily) >= 2:
            closes = recent_daily["close"].tolist()
            if closes[0] and closes[0] > 0:
                price_trend_5d = (closes[-1] / closes[0] - 1) * 100
        for _, row in recent_mf.iterrows():
            buy_lg = self._safe_val(row, "buy_lg_amount") or 0
            sell_lg = self._safe_val(row, "sell_lg_amount") or 0
            buy_elg = self._safe_val(row, "buy_elg_amount") or 0
            sell_elg = self._safe_val(row, "sell_elg_amount") or 0
            flow_trend_5d += (buy_lg - sell_lg) + (buy_elg - sell_elg)

        # 持续天数
        persistence_days = self._count_persistence_days(stock_mf, lookback)

        return {
            "signal_type": signal_type,
            "signal_strength": round(signal_strength, 1),
            "price_trend": round(price_trend, 2),
            "flow_trend": round(flow_trend, 2),
            "price_trend_5d": round(price_trend_5d, 2),
            "flow_trend_5d": round(flow_trend_5d, 2),
            "divergence_score": round(signal_strength, 1),
            "details": {
                "price_change_pct": round(price_trend, 2),
                "main_fund_net": round(flow_trend, 2),
                "main_fund_net_5d": round(flow_trend_5d, 2),
                "persistence_days": persistence_days,
                "momentum_score": round(persistence_score, 1),
            },
        }

    def _calc_persistence_score(
        self, stock_daily: pd.DataFrame, stock_mf: pd.DataFrame, lookback: int
    ) -> float:
        """计算背离持续性评分 (0-100)。"""
        if stock_mf.empty or len(stock_mf) < 2:
            return 0

        recent = stock_mf.tail(lookback)
        inflow_days = 0
        total_days = len(recent)
        if total_days == 0:
            return 0

        for _, row in recent.iterrows():
            buy_lg = self._safe_val(row, "buy_lg_amount") or 0
            sell_lg = self._safe_val(row, "sell_lg_amount") or 0
            buy_elg = self._safe_val(row, "buy_elg_amount") or 0
            sell_elg = self._safe_val(row, "sell_elg_amount") or 0
            net = (buy_lg - sell_lg) + (buy_elg - sell_elg)
            if net > 0:
                inflow_days += 1

        # 取较高比例的方向作为持续天数
        outflow_days = total_days - inflow_days
        max_direction_days = max(inflow_days, outflow_days)

        return (max_direction_days / total_days) * 100

    def _count_persistence_days(self, stock_mf: pd.DataFrame, lookback: int) -> int:
        """计算资金流向一致方向的持续天数。"""
        if stock_mf.empty:
            return 0

        recent = stock_mf.tail(lookback)
        if len(recent) < 2:
            return 0

        # 从最近一天往前数，看连续同方向天数
        days = 0
        last_direction = None
        for _, row in recent.iloc[::-1].iterrows():
            buy_lg = self._safe_val(row, "buy_lg_amount") or 0
            sell_lg = self._safe_val(row, "sell_lg_amount") or 0
            buy_elg = self._safe_val(row, "buy_elg_amount") or 0
            sell_elg = self._safe_val(row, "sell_elg_amount") or 0
            net = (buy_lg - sell_lg) + (buy_elg - sell_elg)

            direction = "in" if net > 0 else "out"
            if last_direction is None:
                last_direction = direction
            if direction == last_direction:
                days += 1
            else:
                break

        return days

    def _calc_flow_momentum(self, stock_mf_lb: pd.DataFrame) -> Dict[str, Any]:
        """计算资金流量动量（加速/减速）。"""
        if stock_mf_lb.empty or len(stock_mf_lb) < 3:
            return {
                "acceleration": 1.0,
                "trend": "flat",
                "momentum_score": 50,
            }

        recent = stock_mf_lb.tail(len(stock_mf_lb))

        # 计算每日主力净流入
        flows = []
        for _, row in recent.iterrows():
            buy_lg = self._safe_val(row, "buy_lg_amount") or 0
            sell_lg = self._safe_val(row, "sell_lg_amount") or 0
            buy_elg = self._safe_val(row, "buy_elg_amount") or 0
            sell_elg = self._safe_val(row, "sell_elg_amount") or 0
            flows.append((buy_lg - sell_lg) + (buy_elg - sell_elg))

        if len(flows) < 2:
            return {"acceleration": 1.0, "trend": "flat", "momentum_score": 50}

        # 最近半段均值 vs 前半段均值
        mid = len(flows) // 2
        first_half = flows[:mid] if mid > 0 else flows[:1]
        second_half = flows[mid:]

        avg_first = sum(first_half) / len(first_half) if first_half else 0
        avg_second = sum(second_half) / len(second_half) if second_half else 0

        if avg_first != 0:
            acceleration = avg_second / avg_first if avg_first != 0 else 1.0
        else:
            acceleration = 2.0 if avg_second > 0 else 0.5

        # 加速方向
        if acceleration > 1.1:
            trend = "up"
        elif acceleration < 0.9:
            trend = "down"
        else:
            trend = "flat"

        # 动量评分
        momentum_score = min(100, max(0, 50 + (acceleration - 1) * 50))

        return {
            "acceleration": round(acceleration, 2),
            "trend": trend,
            "momentum_score": round(momentum_score, 1),
        }

    def _calc_flow_persistence(self, stock_mf_lb: pd.DataFrame) -> Dict[str, Any]:
        """计算资金流向持续性。"""
        if stock_mf_lb.empty:
            return {
                "inflow_days": 0,
                "outflow_days": 0,
                "persistence_score": 0,
            }

        inflow_days = 0
        outflow_days = 0

        for _, row in stock_mf_lb.iterrows():
            buy_lg = self._safe_val(row, "buy_lg_amount") or 0
            sell_lg = self._safe_val(row, "sell_lg_amount") or 0
            buy_elg = self._safe_val(row, "buy_elg_amount") or 0
            sell_elg = self._safe_val(row, "sell_elg_amount") or 0
            net = (buy_lg - sell_lg) + (buy_elg - sell_elg)
            if net > 0:
                inflow_days += 1
            else:
                outflow_days += 1

        total = inflow_days + outflow_days
        max_days = max(inflow_days, outflow_days)
        persistence_score = (max_days / total * 100) if total > 0 else 0

        return {
            "inflow_days": inflow_days,
            "outflow_days": outflow_days,
            "persistence_score": round(persistence_score, 1),
        }

    @staticmethod
    def _empty_result(trade_date, lookback_days, signal_type):
        return {
            "trade_date": trade_date,
            "lookback_days": lookback_days,
            "summary": {
                "total_scanned": 0,
                "bullish_divergence": 0,
                "bearish_divergence": 0,
                "strong_signals": 0,
            },
            "results": [],
            "signal_type": signal_type,
        }
