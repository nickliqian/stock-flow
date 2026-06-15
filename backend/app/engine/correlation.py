"""策略相关性分析与智能配置引擎。

计算策略间的选股重叠度、收益率相关性，
并基于均值方差优化和市场状态提供策略配置建议。
"""

import json
import logging
import math
from typing import Dict, Any, List, Optional, Tuple

from ..models import SessionLocal, StrategySnapshot, StrategyPerformance
from ..engine.registry import get_all_strategies, load_all_strategies
from ..engine.base import STRATEGY_CATEGORIES
from ..utils import get_latest_trade_date

logger = logging.getLogger(__name__)

# 策略分类映射：从 STRATEGY_CATEGORIES（category → [strategies]）反转为（strategy → category）
# combo 是跨类别标记，不算作独立分类，跳过以保留策略的主分类
CATEGORY_MAP = {}
for _cat, _strategies in STRATEGY_CATEGORIES.items():
    if _cat == "combo":
        continue
    for _s in _strategies:
        CATEGORY_MAP.setdefault(_s, _cat)

# 体制→分类权重映射（使用 base.py 中定义的分类名 "flow"）
REGIME_CATEGORY_WEIGHTS = {
    "bull": {"value": 0.15, "momentum": 0.40, "event": 0.15, "flow": 0.20, "combo": 0.10},
    "bear": {"value": 0.35, "momentum": 0.10, "event": 0.10, "flow": 0.25, "combo": 0.20},
    "sideways": {"value": 0.25, "momentum": 0.20, "event": 0.15, "flow": 0.25, "combo": 0.15},
    "extreme": {"value": 0.20, "momentum": 0.20, "event": 0.15, "flow": 0.25, "combo": 0.20},
}


class StrategyCorrelationEngine:
    """策略相关性分析与智能配置引擎。"""

    def __init__(self, cache=None):
        self.cache = cache

    # ------------------------------------------------------------------
    # 选股重叠分析 (Jaccard Similarity)
    # ------------------------------------------------------------------
    def get_overlap_matrix(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """计算策略间的选股重叠度（Jaccard 相似系数）。"""
        session = SessionLocal()
        try:
            if not trade_date:
                trade_date = get_latest_trade_date(self.cache) if self.cache else None
            if not trade_date:
                # Fallback: use latest snapshot date
                latest = session.query(StrategySnapshot.trade_date).order_by(
                    StrategySnapshot.trade_date.desc()
                ).first()
                if not latest:
                    return {"strategies": [], "matrix": [], "overlap_details": [], "error": "暂无策略快照数据"}
                trade_date = latest[0]

            # Get all snapshots for this date
            snapshots = session.query(StrategySnapshot).filter_by(trade_date=trade_date).all()
            if len(snapshots) < 2:
                return {"strategies": [], "matrix": [], "overlap_details": [], "trade_date": trade_date, "error": "需要至少2个策略有快照数据"}

            # Parse stock picks for each strategy
            strategy_picks: Dict[str, set] = {}
            for snap in snapshots:
                if snap.top_picks:
                    try:
                        picks = json.loads(snap.top_picks)
                        if isinstance(picks, list):
                            ts_codes = {p.get("ts_code") for p in picks if isinstance(p, dict) and p.get("ts_code")}
                            if ts_codes:
                                strategy_picks[snap.strategy_name] = ts_codes
                    except (json.JSONDecodeError, TypeError):
                        pass

            names = sorted(strategy_picks.keys())
            if len(names) < 2:
                return {"strategies": [], "matrix": [], "overlap_details": [], "trade_date": trade_date, "error": "有效策略数据不足"}

            # Compute Jaccard similarity matrix
            n = len(names)
            matrix = [[0.0] * n for _ in range(n)]
            overlap_details = []

            for i in range(n):
                for j in range(n):
                    if i == j:
                        matrix[i][j] = 1.0
                    else:
                        set_a = strategy_picks[names[i]]
                        set_b = strategy_picks[names[j]]
                        intersection = set_a & set_b
                        union = set_a | set_b
                        jaccard = len(intersection) / len(union) if union else 0.0
                        matrix[i][j] = round(jaccard, 4)
                        if i < j and intersection:
                            overlap_details.append({
                                "pair": [names[i], names[j]],
                                "similarity": round(jaccard, 4),
                                "intersection_count": len(intersection),
                                "union_count": len(union),
                                "shared_stocks": sorted(intersection)[:10],
                            })

            # Sort by similarity descending
            overlap_details.sort(key=lambda x: x["similarity"], reverse=True)

            return {
                "strategies": names,
                "matrix": matrix,
                "overlap_details": overlap_details[:30],  # Top 30 pairs
                "trade_date": trade_date,
            }
        except Exception as exc:
            logger.error("get_overlap_matrix failed: %s", exc)
            return {"strategies": [], "matrix": [], "overlap_details": [], "error": str(exc)}
        finally:
            session.close()

    # ------------------------------------------------------------------
    # 收益率相关性 (Pearson Correlation)
    # ------------------------------------------------------------------
    def get_correlation_matrix(self, days: int = 20) -> Dict[str, Any]:
        """计算策略间的收益率相关性（基于 strategy_performance 表）。"""
        session = SessionLocal()
        try:
            # Get distinct strategies with performance data
            all_strategies = session.query(
                StrategyPerformance.strategy_name
            ).distinct().all()
            strategy_names = sorted([s[0] for s in all_strategies])

            if len(strategy_names) < 2:
                return {"strategies": [], "matrix": [], "period": 0, "error": "需要至少2个策略有表现数据"}

            # Get performance data grouped by (trade_date, strategy_name)
            # Each row's avg return_1d = mean of all picks' return_1d
            from sqlalchemy import func
            rows = session.query(
                StrategyPerformance.trade_date,
                StrategyPerformance.strategy_name,
                func.avg(StrategyPerformance.ret_1d).label("avg_return"),
            ).filter(
                StrategyPerformance.ret_1d.isnot(None)
            ).group_by(
                StrategyPerformance.trade_date,
                StrategyPerformance.strategy_name
            ).order_by(
                StrategyPerformance.trade_date.desc()
            ).limit(days * len(strategy_names)).all()

            # Build return series per strategy
            returns_by_strategy: Dict[str, List[float]] = {name: [] for name in strategy_names}
            dates_by_strategy: Dict[str, List[str]] = {name: [] for name in strategy_names}
            for trade_date, strat_name, avg_return in rows:
                if strat_name in returns_by_strategy and avg_return is not None:
                    returns_by_strategy[strat_name].append(float(avg_return))
                    dates_by_strategy[strat_name].append(trade_date)

            # Find strategies with enough data (at least 3 data points)
            valid_strategies = [n for n in strategy_names if len(returns_by_strategy[n]) >= 3]
            if len(valid_strategies) < 2:
                return {"strategies": [], "matrix": [], "period": 0, "error": "策略收益数据不足（需要至少3个交易日数据）"}

            n = len(valid_strategies)
            # Compute Pearson correlation matrix
            matrix = [[0.0] * n for _ in range(n)]

            for i in range(n):
                for j in range(n):
                    if i == j:
                        matrix[i][j] = 1.0
                    else:
                        ri = returns_by_strategy[valid_strategies[i]]
                        rj = returns_by_strategy[valid_strategies[valid_strategies[j]]]
                        # Align by date
                        di = dates_by_strategy[valid_strategies[i]]
                        dj = dates_by_strategy[valid_strategies[j]]
                        common_dates = set(di) & set(dj)
                        if len(common_dates) < 3:
                            matrix[i][j] = 0.0
                            continue

                        # Build aligned series
                        ai = [ri[di.index(d)] for d in sorted(common_dates)]
                        aj = [rj[dj.index(d)] for d in sorted(common_dates)]

                        corr = _pearson_correlation(ai, aj)
                        matrix[i][j] = round(corr, 4)

            # Count data period
            all_dates = set()
            for dlist in dates_by_strategy.values():
                all_dates.update(dlist)

            return {
                "strategies": valid_strategies,
                "matrix": matrix,
                "period": len(all_dates),
                "data_points": {s: len(returns_by_strategy[s]) for s in valid_strategies},
            }
        except Exception as exc:
            logger.error("get_correlation_matrix failed: %s", exc)
            return {"strategies": [], "matrix": [], "period": 0, "error": str(exc)}
        finally:
            session.close()

    # ------------------------------------------------------------------
    # 均值方差优化 (Mean-Variance Optimization)
    # ------------------------------------------------------------------
    def optimize_allocation(self, days: int = 20) -> Dict[str, Any]:
        """基于均值方差分析的策略配置优化。"""
        session = SessionLocal()
        try:
            from sqlalchemy import func

            # Get strategy returns
            rows = session.query(
                StrategyPerformance.trade_date,
                StrategyPerformance.strategy_name,
                func.avg(StrategyPerformance.ret_1d).label("avg_return"),
            ).filter(
                StrategyPerformance.ret_1d.isnot(None)
            ).group_by(
                StrategyPerformance.trade_date,
                StrategyPerformance.strategy_name
            ).order_by(
                StrategyPerformance.trade_date.desc()
            ).limit(days * 50).all()

            returns_by_strategy: Dict[str, List[float]] = {}
            for trade_date, strat_name, avg_return in rows:
                if avg_return is not None:
                    if strat_name not in returns_by_strategy:
                        returns_by_strategy[strat_name] = []
                    returns_by_strategy[strat_name].append(float(avg_return))

            # Filter strategies with enough data
            valid = {k: v for k, v in returns_by_strategy.items() if len(v) >= 3}
            if len(valid) < 2:
                return {
                    "strategies": [],
                    "equal_weight": {},
                    "risk_parity": {},
                    "min_variance": {},
                    "expected_returns": {},
                    "risk": {},
                    "error": "策略收益数据不足",
                }

            names = sorted(valid.keys())
            n = len(names)

            # Compute expected returns and covariance matrix
            exp_returns = {}
            risks = {}
            for name in names:
                r = valid[name]
                exp_returns[name] = sum(r) / len(r)
                mean = exp_returns[name]
                variance = sum((x - mean) ** 2 for x in r) / max(len(r) - 1, 1)
                risks[name] = math.sqrt(variance)

            # Equal weight
            equal_weight = {name: round(1.0 / n, 4) for name in names}

            # Risk parity: weight inversely proportional to volatility
            total_inv_vol = sum(1.0 / max(risks[name], 1e-8) for name in names)
            risk_parity = {name: round((1.0 / max(risks[name], 1e-8)) / total_inv_vol, 4) for name in names}

            # Minimum variance (simplified: inverse variance weighting)
            total_inv_var = sum(1.0 / max(risks[name] ** 2, 1e-12) for name in names)
            min_variance = {name: round((1.0 / max(risks[name] ** 2, 1e-12)) / total_inv_var, 4) for name in names}

            # Sharpe-like score for each strategy (return/risk)
            sharpe_scores = {name: round(exp_returns[name] / max(risks[name], 1e-8), 4) for name in names}

            # Sharpe-weighted allocation
            total_sharpe = sum(max(s, 0.01) for s in sharpe_scores.values())
            sharpe_weighted = {name: round(max(s, 0.01) / total_sharpe, 4) for name, s in sharpe_scores.items()}

            return {
                "strategies": names,
                "equal_weight": equal_weight,
                "risk_parity": risk_parity,
                "min_variance": min_variance,
                "sharpe_weighted": sharpe_weighted,
                "expected_returns": {name: round(v, 6) for name, v in exp_returns.items()},
                "risk": {name: round(v, 6) for name, v in risks.items()},
                "sharpe_scores": sharpe_scores,
                "days_analyzed": max(len(v) for v in valid.values()),
            }
        except Exception as exc:
            logger.error("optimize_allocation failed: %s", exc)
            return {"strategies": [], "error": str(exc)}
        finally:
            session.close()

    # ------------------------------------------------------------------
    # 体制自适应配置 (Regime-Adaptive Allocation)
    # ------------------------------------------------------------------
    def get_regime_allocation(self) -> Dict[str, Any]:
        """根据市场状态动态调整策略配置权重。"""
        try:
            from .regime import MarketRegimeDetector
            detector = MarketRegimeDetector(self.cache)
            regime_result = detector.detect()

            if not regime_result.get("success", True) and regime_result.get("error"):
                return {"error": regime_result.get("error")}

            regime = regime_result.get("regime", "sideways")
            confidence = regime_result.get("confidence", 0.5)

            # Get category weights for current regime
            cat_weights = REGIME_CATEGORY_WEIGHTS.get(regime, REGIME_CATEGORY_WEIGHTS["sideways"])

            # Get all strategies and their categories
            load_all_strategies()
            all_strats = get_all_strategies()

            # Build per-strategy weights
            category_counts: Dict[str, int] = {}
            strategy_weights: Dict[str, float] = {}
            strategy_categories: Dict[str, str] = {}

            for name in all_strats:
                cat = CATEGORY_MAP.get(name, "combo")
                strategy_categories[name] = cat
                category_counts[cat] = category_counts.get(cat, 0) + 1

            for name in all_strats:
                cat = strategy_categories[name]
                count = category_counts.get(cat, 1)
                strategy_weights[name] = round(cat_weights.get(cat, 0.1) / count, 4)

            # Normalize to sum to 1
            total = sum(strategy_weights.values())
            if total > 0:
                strategy_weights = {k: round(v / total, 4) for k, v in strategy_weights.items()}

            # Risk assessment
            risk_map = {
                "bull": "低",
                "bear": "高",
                "sideways": "中",
                "extreme": "极高",
            }

            return {
                "success": True,
                "regime": regime,
                "regime_label": {"bull": "牛市🟢", "bear": "熊市🔴", "sideways": "震荡🟡", "extreme": "极端🟣"}.get(regime, "未知"),
                "confidence": confidence,
                "category_weights": cat_weights,
                "strategy_weights": strategy_weights,
                "strategy_categories": strategy_categories,
                "category_counts": category_counts,
                "risk_level": risk_map.get(regime, "中"),
                "recommendation": self._get_regime_recommendation(regime),
            }
        except Exception as exc:
            logger.error("get_regime_allocation failed: %s", exc)
            return {"error": str(exc)}

    def _get_regime_recommendation(self, regime: str) -> str:
        """根据市场状态生成配置建议。"""
        recommendations = {
            "bull": "🟢 牛市环境下，建议偏重动量类策略（40%），捕捉趋势延续机会。价值类策略配置较低（15%），避免追高。资金流入策略可辅助确认趋势。",
            "bear": "🔴 熊市环境下，建议偏重价值类策略（35%），寻找被错杀的低估值股。资金类策略（25%）追踪聪明钱逆向布局。动量策略谨慎使用。",
            "sideways": "🟡 震荡市环境下，建议均衡配置：价值（25%）+ 资金（25%）+ 动量（20%）。事件驱动策略（15%）捕捉短期机会。组合策略（15%）提供多维确认。",
            "extreme": "🟣 极端行情下，建议以防守为主：资金类（25%）追踪机构动向，组合策略（20%）要求多策略共振，价值类（20%）寻找安全边际。控制仓位，降低风险。",
        }
        return recommendations.get(regime, "建议均衡配置各类策略。")

    # ------------------------------------------------------------------
    # 综合仪表板
    # ------------------------------------------------------------------
    def get_portfolio_summary(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """综合分析摘要：重叠 + 相关性 + 配置 + 体制。"""
        try:
            # 1. Overlap analysis
            overlap = self.get_overlap_matrix(trade_date)

            # 2. Correlation analysis
            correlation = self.get_correlation_matrix()

            # 3. Optimization
            allocation = self.optimize_allocation()

            # 4. Regime-adaptive allocation
            regime_alloc = self.get_regime_allocation()

            # Generate insights
            insights = []

            # Overlap insights
            if overlap.get("overlap_details"):
                top_overlap = overlap["overlap_details"][0]
                insights.append({
                    "type": "overlap",
                    "title": "最高选股重叠",
                    "detail": f"{top_overlap['pair'][0]} 与 {top_overlap['pair'][1]} 共享 {top_overlap['intersection_count']} 只股票，重叠度 {top_overlap['similarity']:.1%}",
                    "level": "info" if top_overlap["similarity"] < 0.5 else "warning",
                })

            # Correlation insights
            if correlation.get("matrix") and len(correlation.get("matrix", [])) > 1:
                strategies = correlation["strategies"]
                matrix = correlation["matrix"]
                # Find highest positive and negative correlations
                max_corr = -2
                min_corr = 2
                max_pair = None
                min_pair = None
                for i in range(len(strategies)):
                    for j in range(i + 1, len(strategies)):
                        if matrix[i][j] > max_corr:
                            max_corr = matrix[i][j]
                            max_pair = (strategies[i], strategies[j])
                        if matrix[i][j] < min_corr:
                            min_corr = matrix[i][j]
                            min_pair = (strategies[i], strategies[j])

                if max_pair:
                    insights.append({
                        "type": "correlation",
                        "title": "最高正相关",
                        "detail": f"{max_pair[0]} 与 {max_pair[1]} 相关系数 {max_corr:.3f}，选股权高度重叠",
                        "level": "warning" if max_corr > 0.7 else "info",
                    })
                if min_pair and min_corr < 0:
                    insights.append({
                        "type": "correlation",
                        "title": "最佳对冲组合",
                        "detail": f"{min_pair[0]} 与 {min_pair[1]} 相关系数 {min_corr:.3f}，适合作为对冲组合",
                        "level": "success",
                    })

            # Allocation insights
            if allocation.get("sharpe_weighted"):
                best_sharpe = max(allocation["sharpe_scores"].items(), key=lambda x: x[1])
                insights.append({
                    "type": "allocation",
                    "title": "最优风险调整策略",
                    "detail": f"{best_sharpe[0]} 夏普比 {best_sharpe[1]:.3f}，建议配置 {allocation['sharpe_weighted'][best_sharpe[0]]:.1%}",
                    "level": "success",
                })

            # Regime insights
            if regime_alloc.get("success"):
                insights.append({
                    "type": "regime",
                    "title": f"当前市场状态：{regime_alloc.get('regime_label', '未知')}",
                    "detail": regime_alloc.get("recommendation", ""),
                    "level": "info",
                })

            return {
                "success": True,
                "overlap": overlap,
                "correlation": correlation,
                "allocation": allocation,
                "regime_allocation": regime_alloc,
                "insights": insights,
            }
        except Exception as exc:
            logger.error("get_portfolio_summary failed: %s", exc)
            return {"success": False, "error": str(exc)}


# ------------------------------------------------------------------
# Utility functions
# ------------------------------------------------------------------

def _pearson_correlation(x: List[float], y: List[float]) -> float:
    """计算两组数据的 Pearson 相关系数。"""
    n = len(x)
    if n < 2:
        return 0.0

    mean_x = sum(x) / n
    mean_y = sum(y) / n

    cov_xy = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    var_x = sum((xi - mean_x) ** 2 for xi in x)
    var_y = sum((yi - mean_y) ** 2 for yi in y)

    if var_x == 0 or var_y == 0:
        return 0.0

    return cov_xy / math.sqrt(var_x * var_y)
