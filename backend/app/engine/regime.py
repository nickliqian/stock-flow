"""市场状态检测模块——分析多个信号确定当前市场状态并推荐最佳策略。"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from collections import Counter

from sqlalchemy import text

from ..models import SessionLocal, StrategySnapshot, StrategyPerformance, IndexDaily
from ..cache import CacheService
from ..engine.registry import get_all_strategies
from ..utils import get_last_n_trade_dates

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 市场状态到策略的映射
# ---------------------------------------------------------------------------
REGIME_STRATEGY_MAP = {
    "bull": {
        "best": ["volume_breakthrough", "ma_alignment", "trend_volume_resonance",
                 "kdj_oversold_rebound", "volume_anomaly"],
        "good": ["main_fund_inflow", "consecutive_limit_up", "limit_up_reseal",
                 "margin_fund_convergence", "smart_money_tracker"],
        "avoid": ["high_dividend", "low_valuation_gold", "broken_net_gold"],
        "compose_preset": {"strategies": ["volume_breakthrough", "ma_alignment"], "operator": "AND"},
        "risk_level": "moderate",
        "advice_template": "市场处于上升趋势，建议重点关注动量类策略（放量突破、均线多头排列），资金驱动类策略次之。",
    },
    "bear": {
        "best": ["high_dividend", "low_valuation_gold", "broken_net_gold"],
        "good": ["value_fund_resonance", "main_fund_inflow", "margin_fund_convergence"],
        "avoid": ["volume_breakthrough", "ma_alignment", "trend_volume_resonance", "consecutive_limit_up"],
        "compose_preset": {"strategies": ["high_dividend", "low_valuation_gold"], "operator": "OR"},
        "risk_level": "high",
        "advice_template": "市场处于下降趋势，建议重点关注价值类策略（高股息、低估值），控制仓位。",
    },
    "sideways": {
        "best": ["value_fund_resonance", "main_fund_inflow", "broken_net_gold",
                 "margin_fund_convergence"],
        "good": ["low_valuation_gold", "high_dividend", "oversold_bounce",
                 "smart_money_tracker"],
        "avoid": ["volume_breakthrough", "ma_alignment"],
        "compose_preset": {"strategies": ["value_fund_resonance", "main_fund_inflow"], "operator": "AND"},
        "risk_level": "moderate",
        "advice_template": "市场处于震荡区间，建议关注价值+资金共振类策略，精选个股。",
    },
    "extreme": {
        "best": ["high_dividend", "low_valuation_gold"],
        "good": ["broken_net_gold", "oversold_bounce", "margin_fund_convergence"],
        "avoid": ["volume_breakthrough", "ma_alignment", "consecutive_limit_up", "trend_volume_resonance"],
        "compose_preset": {"strategies": ["high_dividend", "broken_net_gold"], "operator": "OR"},
        "risk_level": "extreme",
        "advice_template": "市场出现极端信号，建议高度防御，持有高股息低估值品种，控制仓位。",
    },
}

# 中文标签
REGIME_LABELS = {
    "bull": "牛市",
    "bear": "熊市",
    "sideways": "震荡",
    "extreme": "极端",
}

# 动量类策略名
MOMENTUM_STRATEGIES = {
    "volume_breakthrough", "ma_alignment", "trend_volume_resonance",
    "volume_anomaly", "kdj_oversold_rebound", "macd_golden_cross",
    "consecutive_limit_up", "limit_up_reseal",
}

# 价值类策略名
VALUE_STRATEGIES = {
    "high_dividend", "low_valuation_gold", "broken_net_gold",
    "value_fund_resonance",
}

# 资金类策略名
FLOW_STRATEGIES = {
    "main_fund_inflow", "margin_growth",
    "margin_fund_convergence", "smart_money_tracker",
}

# 主要指数
INDEX_CODES = [
    ("000001.SH", "上证指数"),
    ("399001.SZ", "深证成指"),
    ("399006.SZ", "创业板指"),
]


class MarketRegimeDetector:
    """市场状态检测器——分析多个信号确定当前市场状态。"""

    def __init__(self, cache: Optional[CacheService] = None):
        self.cache = cache or CacheService()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def detect(self) -> Dict[str, Any]:
        """检测当前市场状态，返回完整的状态分析结果。"""
        session = SessionLocal()
        try:
            # 1. 计算各信号分数
            index_score = self._calc_index_trend_score(session)
            perf_score = self._calc_strategy_performance_score(session)
            breadth_score = self._calc_breadth_score(session)
            confluence_score = self._calc_confluence_score(session)

            # 2. 综合加权计算
            total_score = (
                index_score["score"] * 0.30 +
                perf_score["score"] * 0.30 +
                breadth_score["score"] * 0.20 +
                confluence_score["score"] * 0.20
            )

            # 3. 确定市场状态
            regime = self._score_to_regime(total_score, confluence_score["score"])

            # 4. 计算置信度
            confidence = self._calc_confidence(
                index_score["score"], perf_score["score"],
                breadth_score["score"], confluence_score["score"],
                total_score
            )

            # 5. 获取推荐
            recommendations = self._build_recommendations(regime, total_score)

            # 6. 获取最近10个交易日的状态历史
            history = self._get_regime_history(session, limit=10)

            result = {
                "regime": regime,
                "confidence": round(confidence, 2),
                "label": REGIME_LABELS[regime],
                "description": self._generate_description(regime, total_score),
                "total_score": round(total_score, 1),
                "signals": {
                    "index_trend": index_score,
                    "strategy_performance": perf_score,
                    "breadth": breadth_score,
                    "confluence": confluence_score,
                },
                "regime_history": history,
                "recommendations": recommendations,
            }

            # 7. 保存当前状态到历史（方便下次查询历史）
            self._save_regime_snapshot(session, regime, confidence)

            return {"success": True, "data": result}
        except Exception as exc:
            logger.error("MarketRegimeDetector.detect failed: %s", exc)
            return {"success": False, "error": str(exc)}
        finally:
            session.close()

    def get_history(self, limit: int = 20) -> Dict[str, Any]:
        """获取最近N个交易日的市场状态历史。"""
        session = SessionLocal()
        try:
            history = self._get_regime_history(session, limit=limit)
            return {"success": True, "data": {"history": history, "total": len(history)}}
        finally:
            session.close()

    def get_recommendations(self) -> Dict[str, Any]:
        """获取当前市场状态下的策略推荐。"""
        result = self.detect()
        if not result.get("success"):
            return result
        return {"success": True, "data": result["data"]["recommendations"]}

    # ------------------------------------------------------------------
    # 信号计算
    # ------------------------------------------------------------------

    def _calc_index_trend_score(self, session) -> Dict[str, Any]:
        """指数趋势信号（权重30%）。

        基于三大指数的MA5/MA20交叉、20日涨跌幅、近期波动率。
        返回 {score, detail}，score范围 -200 ~ +200。
        """
        all_scores = []
        detail_parts = []

        for ts_code, name in INDEX_CODES:
            try:
                # 获取最近20个交易日的指数数据
                rows = session.execute(
                    text("""
                        SELECT trade_date, close, pct_chg, vol
                        FROM index_daily
                        WHERE ts_code = :tc
                        ORDER BY trade_date DESC
                        LIMIT 20
                    """),
                    {"tc": ts_code},
                ).fetchall()

                if not rows or len(rows) < 5:
                    continue

                # 转为按日期升序排列
                rows = list(reversed(rows))
                closes = [float(r[1]) for r in rows if r[1]]
                pct_chgs = [float(r[2]) for r in rows if r[2] is not None]

                if not closes:
                    continue

                # MA5 / MA20
                ma5 = sum(closes[-5:]) / min(5, len(closes[-5:])) if closes else 0
                ma20 = sum(closes) / len(closes) if closes else 0

                # 20日涨跌幅
                if len(closes) >= 2:
                    ret_20d = (closes[-1] - closes[0]) / closes[0] * 100
                else:
                    ret_20d = 0

                # 近5日涨跌幅
                if len(closes) >= 5:
                    ret_5d = (closes[-1] - closes[-5]) / closes[-5] * 100
                else:
                    ret_5d = 0

                # MA5 vs MA20 交叉信号 (-100 ~ +100)
                if ma5 > 0 and ma20 > 0:
                    ma_ratio = (ma5 - ma20) / ma20 * 100
                    crossover_score = max(-100, min(100, ma_ratio * 20))
                else:
                    crossover_score = 0

                # 涨跌幅信号 (-100 ~ +100)
                ret_score = max(-100, min(100, ret_20d * 10))

                # 综合分数
                idx_score = (crossover_score * 0.5 + ret_score * 0.3 +
                             max(-100, min(100, ret_5d * 5)) * 0.2)
                all_scores.append(idx_score)

                detail_parts.append(f"{name}20日涨幅{ret_20d:+.1f}%，MA{'多头' if ma5 > ma20 else '空头'}排列")

            except Exception as exc:
                logger.warning("_calc_index_trend_score: %s failed: %s", ts_code, exc)

        if not all_scores:
            return {"score": 0, "detail": "无指数数据可用"}

        avg_score = sum(all_scores) / len(all_scores)
        return {
            "score": round(max(-200, min(200, avg_score * 2)), 1),
            "detail": "；".join(detail_parts),
        }

    def _calc_strategy_performance_score(self, session) -> Dict[str, Any]:
        """策略表现信号（权重30%）。

        对比动量策略 vs 价值策略在最近5个交易日的表现。
        动量胜 → 看多，价值胜 → 看空。
        返回 {score, detail}，score范围 -200 ~ +200。
        """
        try:
            # 获取最近5个交易日的策略表现
            recent_dates = session.execute(
                text("""
                    SELECT DISTINCT trade_date
                    FROM strategy_performance
                    WHERE ret_1d IS NOT NULL
                    ORDER BY trade_date DESC
                    LIMIT 10
                """),
            ).fetchall()

            if not recent_dates:
                return {"score": 0, "detail": "无策略表现数据可用"}

            dates = [r[0] for r in recent_dates[:5]]

            # 计算动量策略胜率
            momentum_perfs = session.execute(
                text("""
                    SELECT strategy_name, ret_1d
                    FROM strategy_performance
                    WHERE trade_date IN :dates
                    AND ret_1d IS NOT NULL
                """),
                {"dates": tuple(dates)},
            ).fetchall()

            momentum_wins = 0
            momentum_total = 0
            value_wins = 0
            value_total = 0

            for row in momentum_perfs:
                strat_name, ret_1d = row
                ret_val = float(ret_1d) if ret_1d is not None else 0
                if strat_name in MOMENTUM_STRATEGIES:
                    momentum_total += 1
                    if ret_val > 0:
                        momentum_wins += 1
                elif strat_name in VALUE_STRATEGIES:
                    value_total += 1
                    if ret_val > 0:
                        value_wins += 1

            momentum_wr = (momentum_wins / momentum_total * 100) if momentum_total > 0 else 50
            value_wr = (value_wins / value_total * 100) if value_total > 0 else 50

            # 动量策略优势 → 看多（+200），价值优势 → 看空（-200）
            wr_diff = momentum_wr - value_wr
            score = max(-200, min(200, wr_diff * 5))

            detail = (f"动量策略近5日胜率{momentum_wr:.0f}%（{momentum_wins}/{momentum_total}），"
                      f"价值策略胜率{value_wr:.0f}%（{value_wins}/{value_total}）")

            return {"score": round(score, 1), "detail": detail}

        except Exception as exc:
            logger.warning("_calc_strategy_performance_score failed: %s", exc)
            return {"score": 0, "detail": "策略表现数据异常"}

    def _calc_breadth_score(self, session) -> Dict[str, Any]:
        """市场广度信号（权重20%）。

        基于最新策略快照的选中股票数量判断市场参与度。
        高选中数 → 广泛参与（看多），低选中数 → 狭窄市场（看空）。
        返回 {score, detail}，score范围 -200 ~ +200。
        """
        try:
            # 获取最新交易日的快照
            latest_date = session.execute(
                text("""
                    SELECT trade_date FROM strategy_snapshot
                    ORDER BY trade_date DESC LIMIT 1
                """),
            ).fetchone()

            if not latest_date:
                return {"score": 0, "detail": "无策略快照数据"}

            td = latest_date[0]

            snapshots = session.execute(
                text("""
                    SELECT strategy_name, pick_count, avg_score, max_score
                    FROM strategy_snapshot
                    WHERE trade_date = :td
                    AND strategy_name != '_regime_snapshot'
                """),
                {"td": td},
            ).fetchall()

            if not snapshots:
                return {"score": 0, "detail": f"日期{td}无策略快照"}

            total_picks = sum(r[1] for r in snapshots)
            avg_picks = total_picks / len(snapshots) if snapshots else 0
            num_strategies = len(snapshots)

            # 广度评分：基于平均选中数
            # 通常一个策略选中 5-30 只为正常范围
            # 20+ 说明市场广泛参与（看多），5 以下说明市场狭窄（看空）
            if avg_picks > 0:
                if avg_picks >= 20:
                    breadth = min(150, (avg_picks - 20) * 5 + 50)
                elif avg_picks >= 10:
                    breadth = (avg_picks - 10) * 5  # -50 to +50
                else:
                    breadth = max(-150, (avg_picks - 10) * 10)  # -150 to -50
            else:
                breadth = -200

            detail = (f"{num_strategies}个策略共选中{total_picks}只股票，"
                      f"平均每策略{avg_picks:.0f}只")

            return {"score": round(breadth, 1), "detail": detail}

        except Exception as exc:
            logger.warning("_calc_breadth_score failed: %s", exc)
            return {"score": 0, "detail": "市场广度数据异常"}

    def _calc_confluence_score(self, session) -> Dict[str, Any]:
        """策略共振信号（权重20%）。

        检查有多少股票被3+策略同时选中。
        非常高的共振 → 可能是狂热（极端）
        非常低的共振 → 可能是恐慌（极端）
        返回 {score, detail}，score范围 -200 ~ +200。
        """
        try:
            # 获取最新交易日的快照
            latest_date = session.execute(
                text("""
                    SELECT trade_date FROM strategy_snapshot
                    ORDER BY trade_date DESC LIMIT 1
                """),
            ).fetchone()

            if not latest_date:
                return {"score": 0, "detail": "无策略快照数据"}

            td = latest_date[0]

            # 获取所有快照的 top_picks
            snapshots = session.execute(
                text("""
                    SELECT strategy_name, top_picks
                    FROM strategy_snapshot
                    WHERE trade_date = :td AND top_picks != '' AND top_picks IS NOT NULL
                    AND strategy_name != '_regime_snapshot'
                """),
                {"td": td},
            ).fetchall()

            if not snapshots:
                return {"score": 0, "detail": f"日期{td}无共振数据"}

            # 统计每只股票被多少策略选中
            stock_counts: Dict[str, int] = Counter()
            for row in snapshots:
                try:
                    picks = json.loads(row[1])
                    for pick in picks:
                        tc = pick.get("ts_code", "")
                        if tc:
                            stock_counts[tc] += 1
                except (json.JSONDecodeError, TypeError):
                    continue

            # 统计3+策略共振的股票数
            high_confluence = sum(1 for c in stock_counts.values() if c >= 3)
            very_high = sum(1 for c in stock_counts.values() if c >= 5)
            total_stocks = len(stock_counts)

            # 共振评分：适中的共振为最佳
            # 太多（狂热）或太少（恐慌）都是极端信号
            # 用非线性函数：在中间区域为正，两端为负（极端）
            if total_stocks > 0:
                ratio = high_confluence / total_stocks
                # 理想共振比例约 5-15%
                if ratio < 0.03:
                    # 太少共振 → 看空
                    score = -50 + (ratio / 0.03) * 50  # -50 到 0
                elif ratio < 0.15:
                    # 正常范围 → 看多
                    score = (ratio - 0.03) / 0.12 * 100  # 0 到 +100
                elif ratio < 0.30:
                    # 偏高 → 可能过热
                    score = 100 - (ratio - 0.15) / 0.15 * 100  # +100 到 0
                else:
                    # 极高共振 → 极端狂热
                    score = -((ratio - 0.30) / 0.70 * 200)  # 0 到 -200
            else:
                score = 0

            detail = (f"{total_stocks}只股票被策略选中，"
                      f"其中{high_confluence}只命中3+策略，"
                      f"{very_high}只命中5+策略")

            return {"score": round(max(-200, min(200, score)), 1), "detail": detail}

        except Exception as exc:
            logger.warning("_calc_confluence_score failed: %s", exc)
            return {"score": 0, "detail": "策略共振数据异常"}

    # ------------------------------------------------------------------
    # 状态判定与推荐
    # ------------------------------------------------------------------

    def _score_to_regime(self, total_score: float, confluence_score: float) -> str:
        """根据综合分数和共振分数判定市场状态。"""
        # 极端状态：共振分数极端 或 综合分数极端
        if abs(confluence_score) > 150 or abs(total_score) > 150:
            return "extreme"

        # 牛市：综合分数显著偏正
        if total_score > 40:
            return "bull"

        # 熊市：综合分数显著偏负
        if total_score < -40:
            return "bear"

        # 震荡：分数接近0
        return "sideways"

    def _calc_confidence(self, idx_s: float, perf_s: float,
                         br_s: float, conf_s: float, total: float) -> float:
        """计算置信度（0.0 - 1.0）。

        基于信号一致性和强度。
        """
        scores = [idx_s, perf_s, br_s, conf_s]

        # 信号方向一致性
        signs = [1 if s > 0 else (-1 if s < 0 else 0) for s in scores]
        non_zero = [s for s in signs if s != 0]
        if non_zero:
            agreement = abs(sum(non_zero)) / len(non_zero)
        else:
            agreement = 0

        # 分数强度
        strength = min(abs(total) / 100, 1.0)

        # 置信度 = 方向一致性 * 0.5 + 分数强度 * 0.3 + 数据可用性 * 0.2
        confidence = agreement * 0.5 + strength * 0.3 + 0.2  # 基础0.2（数据存在）
        return max(0.1, min(0.95, confidence))

    def _generate_description(self, regime: str, total_score: float) -> str:
        """生成市场状态描述。"""
        descriptions = {
            "bull": f"市场处于上升趋势，综合信号评分{total_score:+.0f}。"
                    "指数多头排列，动量策略表现良好，市场参与度较高。",
            "bear": f"市场处于下降趋势，综合信号评分{total_score:+.0f}。"
                    "指数空头排列，价值/防御策略表现相对较好。",
            "sideways": f"市场处于震荡区间，综合信号评分{total_score:+.0f}。"
                        "多空信号交织，缺乏明确方向。",
            "extreme": f"市场出现极端信号，综合信号评分{total_score:+.0f}。"
                       "可能处于恐慌抛售或极度狂热状态。",
        }
        return descriptions.get(regime, "市场状态未知")

    def _build_recommendations(self, regime: str, total_score: float) -> Dict[str, Any]:
        """构建策略推荐。"""
        mapping = REGIME_STRATEGY_MAP[regime]

        # 获取所有策略列表
        all_strategies = get_all_strategies()
        available_names = set(all_strategies.keys()) if all_strategies else set()

        # 过滤出系统中实际存在的策略
        best = [s for s in mapping["best"] if s in available_names]
        good = [s for s in mapping["good"] if s in available_names]
        avoid = [s for s in mapping["avoid"] if s in available_names]

        return {
            "best_strategies": best,
            "good_strategies": good,
            "avoid_strategies": avoid,
            "suggested_compose": {
                **mapping["compose_preset"],
                "reason": mapping["advice_template"],
            },
            "risk_level": mapping["risk_level"],
            "advice": mapping["advice_template"],
        }

    # ------------------------------------------------------------------
    # 历史记录
    # ------------------------------------------------------------------

    def _get_regime_history(self, session, limit: int = 10) -> List[Dict]:
        """获取最近N个交易日的市场状态历史。"""
        try:
            rows = session.execute(
                text("""
                    SELECT trade_date, top_picks
                    FROM strategy_snapshot
                    WHERE strategy_name = '_regime_snapshot'
                    ORDER BY trade_date DESC
                    LIMIT :limit
                """),
                {"limit": limit},
            ).fetchall()

            history = []
            for row in reversed(rows):
                try:
                    trade_date = row[0]
                    top_picks_raw = row[1]
                    if not top_picks_raw:
                        continue
                    # top_picks 存储完整 JSON: {"regime": ..., "confidence": ...}
                    regime_data = json.loads(top_picks_raw)
                    history.append({
                        "trade_date": str(trade_date),
                        "regime": regime_data.get("regime", "unknown"),
                        "confidence": regime_data.get("confidence", 0.0),
                    })
                except Exception:
                    continue

            # 如果没有保存的状态记录，返回空
            return history

        except Exception:
            return []

    def _save_regime_snapshot(self, session, regime: str, confidence: float):
        """保存当前市场状态到快照表，用于历史查询。"""
        try:
            from ..utils import get_last_n_trade_dates

            # 获取最新交易日
            latest = session.execute(
                text("SELECT MAX(trade_date) FROM strategy_snapshot WHERE strategy_name != '_regime_snapshot'"),
            ).fetchone()

            if not latest or not latest[0]:
                return

            td = latest[0]

            # 检查是否已存在
            existing = session.execute(
                text("""
                    SELECT id FROM strategy_snapshot
                    WHERE trade_date = :td AND strategy_name = '_regime_snapshot'
                """),
                {"td": td},
            ).fetchone()

            regime_data = json.dumps({
                "regime": regime,
                "confidence": confidence,
            }, ensure_ascii=False)

            if existing:
                session.execute(
                    text("""
                        UPDATE strategy_snapshot
                        SET top_picks = :data, pick_count = :pc
                        WHERE trade_date = :td AND strategy_name = '_regime_snapshot'
                    """),
                    {"data": regime_data, "pc": hash(regime) % 10000, "td": td},
                )
            else:
                session.execute(
                    text("""
                        INSERT INTO strategy_snapshot
                        (trade_date, strategy_name, pick_count, top_picks, avg_score, max_score)
                        VALUES (:td, '_regime_snapshot', :pc, :data, 0, 0)
                    """),
                    {"td": td, "pc": hash(regime) % 10000, "data": regime_data},
                )
            session.commit()
        except Exception as exc:
            logger.warning("_save_regime_snapshot failed: %s", exc)
            session.rollback()
