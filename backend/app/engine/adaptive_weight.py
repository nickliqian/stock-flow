"""自适应策略权重引擎——根据多维因子动态调整策略权重。"""

import json
import logging
import math
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from sqlalchemy import text

from ..models import SessionLocal, StrategySnapshot, StrategyPerformance
from ..cache import CacheService
from .registry import get_all_strategies, load_all_strategies
from .regime import (
    MarketRegimeDetector,
    REGIME_STRATEGY_MAP,
    MOMENTUM_STRATEGIES,
    VALUE_STRATEGIES,
    FLOW_STRATEGIES,
)
from .base import STRATEGY_CATEGORIES, BaseStrategy, StrategyResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 权重分量权重
# ---------------------------------------------------------------------------
W_PERFORMANCE = 0.40
W_CONSISTENCY = 0.25
W_REGIME_FIT = 0.20
W_CORRELATION = 0.15


class AdaptiveWeightEngine:
    """自适应策略权重引擎。"""

    def __init__(self, cache: Optional[CacheService] = None):
        self.cache = cache or CacheService()
        load_all_strategies()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def calculate_weights(
        self, trade_date: Optional[str] = None, lookback_days: int = 20
    ) -> Dict[str, Any]:
        """计算当前交易日各策略的自适应权重。

        返回:
            {
                trade_date, regime, weights: {name: {weight, performance_score, ...}},
                total_strategies, ...
            }
        """
        session = SessionLocal()
        try:
            if not trade_date:
                trade_date = self._get_latest_trade_date(session)

            all_strategies = get_all_strategies()
            if not all_strategies:
                return {"success": True, "data": {"weights": {}, "trade_date": trade_date,
                                                   "regime": "unknown", "total_strategies": 0}}

            # 1. 获取市场状态
            regime_data = self._detect_regime()
            regime = regime_data.get("regime", "sideways")

            # 2. 计算每个策略的各维度分数
            strategies_data: Dict[str, Dict] = {}
            for name, strat in all_strategies.items():
                strategies_data[name] = {
                    "strategy_name": name,
                    "description": strat.description,
                    "category": strat.category,
                    "icon": strat.icon,
                }

            # 计算各维度分数
            perf_scores = self._calc_performance_scores(session, trade_date, lookback_days)
            consistency_scores = self._calc_consistency_scores(session, trade_date, lookback_days)
            regime_scores = self._calc_regime_fit_scores(regime, all_strategies)
            corr_penalties = self._calc_correlation_penalties(session, trade_date)

            # 3. 归一化各维度分数到 [0, 1]
            perf_norm = self._normalize_scores(perf_scores)
            cons_norm = self._normalize_scores(consistency_scores)
            regime_norm = self._normalize_scores(regime_scores)
            corr_norm = self._normalize_penalties(corr_penalties)

            # 4. 计算综合加权分数
            raw_weights: Dict[str, float] = {}
            weight_details: Dict[str, Dict] = {}

            for name in all_strategies:
                p = perf_norm.get(name, 0.5)
                c = cons_norm.get(name, 0.5)
                r = regime_norm.get(name, 0.5)
                cp = corr_norm.get(name, 0.0)

                combined = (
                    p * W_PERFORMANCE
                    + c * W_CONSISTENCY
                    + r * W_REGIME_FIT
                    - cp * W_CORRELATION
                )
                # 确保权重为正
                raw_weights[name] = max(combined, 0.01)
                weight_details[name] = {
                    "strategy_name": name,
                    "description": all_strategies[name].description,
                    "category": all_strategies[name].category,
                    "icon": all_strategies[name].icon,
                    "weight": 0.0,  # 后面归一化后填入
                    "raw_score": round(combined, 4),
                    "performance_score": round(perf_scores.get(name, 0), 4),
                    "consistency_score": round(consistency_scores.get(name, 0), 4),
                    "regime_fit_score": round(regime_scores.get(name, 0), 4),
                    "correlation_penalty": round(corr_penalties.get(name, 0), 4),
                    "perf_norm": round(p, 4),
                    "cons_norm": round(c, 4),
                    "regime_norm": round(r, 4),
                    "corr_norm": round(cp, 4),
                }

            # 5. 归一化使得权重之和为 1.0
            total_raw = sum(raw_weights.values())
            if total_raw > 0:
                for name in raw_weights:
                    raw_weights[name] /= total_raw
                    weight_details[name]["weight"] = round(raw_weights[name], 6)

            # 6. 记录权重历史
            self._save_weight_history(session, trade_date, weight_details)

            result = {
                "trade_date": trade_date,
                "regime": regime,
                "regime_label": self._get_regime_label(regime),
                "weights": weight_details,
                "total_strategies": len(all_strategies),
                "factor_weights": {
                    "performance": W_PERFORMANCE,
                    "consistency": W_CONSISTENCY,
                    "regime_fit": W_REGIME_FIT,
                    "correlation": W_CORRELATION,
                },
            }

            return {"success": True, "data": result}

        except Exception as exc:
            logger.error("AdaptiveWeightEngine.calculate_weights failed: %s", exc)
            return {"success": False, "error": str(exc)}
        finally:
            session.close()

    def execute_adaptive(
        self, trade_date: Optional[str] = None, limit: int = 50
    ) -> Dict[str, Any]:
        """执行自适应加权策略选股。

        运行所有策略，然后按加权得分排序选出最终组合。
        """
        from .data_loader import StrategyDataLoader
        from ..services.base import get_global_client, get_global_cache

        try:
            client = get_global_client()
        except Exception:
            client = None
        try:
            cache_svc = get_global_cache()
        except Exception:
            cache_svc = self.cache

        loader = StrategyDataLoader(client, cache_svc)

        session = SessionLocal()
        try:
            if not trade_date:
                trade_date = self._get_latest_trade_date(session)

            # 1. 获取权重
            weight_result = self.calculate_weights(trade_date)
            if not weight_result.get("success"):
                return weight_result

            weights = weight_result["data"]["weights"]
            regime = weight_result["data"]["regime"]

            # 2. 执行所有策略
            all_strategies = get_all_strategies()
            all_keys: set = set()
            for s in all_strategies.values():
                all_keys.update(s.required_data())

            data = loader.load(trade_date, list(all_keys))

            # 收集所有策略结果：{ts_code: [(strategy_name, score), ...]}
            stock_scores: Dict[str, List[Tuple[str, float]]] = {}
            strategy_results: Dict[str, List[Dict]] = {}

            for name, strategy in all_strategies.items():
                try:
                    results = strategy.check(data)
                    results.sort(key=lambda r: r.score, reverse=True)
                    strategy_results[name] = [r.to_dict() for r in results[:30]]

                    weight = weights.get(name, {}).get("weight", 1.0 / len(all_strategies))
                    for r in results:
                        if r.ts_code not in stock_scores:
                            stock_scores[r.ts_code] = []
                        stock_scores[r.ts_code].append((name, r.score * weight))
                except Exception as exc:
                    logger.warning("Strategy '%s' failed during adaptive execute: %s", name, exc)

            # 3. 计算加权总分
            final_picks = []
            for ts_code, scored_list in stock_scores.items():
                weighted_score = sum(w_score for _, w_score in scored_list)
                contributing_strategies = [s_name for s_name, _ in scored_list]
                # 获取股票名称（从第一个策略结果中获取）
                stock_name = ""
                for s_name in contributing_strategies:
                    for r in strategy_results.get(s_name, []):
                        if r.get("ts_code") == ts_code:
                            stock_name = r.get("name", "")
                            break
                    if stock_name:
                        break

                final_picks.append({
                    "ts_code": ts_code,
                    "name": stock_name,
                    "weighted_score": round(weighted_score, 4),
                    "strategy_count": len(contributing_strategies),
                    "strategies": contributing_strategies,
                })

            final_picks.sort(key=lambda x: x["weighted_score"], reverse=True)
            final_picks = final_picks[:limit]

            result = {
                "trade_date": trade_date,
                "regime": regime,
                "regime_label": self._get_regime_label(regime),
                "total_picks": len(final_picks),
                "picks": final_picks,
                "strategy_summary": {
                    name: {
                        "pick_count": len(strategy_results.get(name, [])),
                        "weight": weights.get(name, {}).get("weight", 0),
                        "category": all_strategies[name].category,
                    }
                    for name in all_strategies
                },
            }

            return {"success": True, "data": result}

        except Exception as exc:
            logger.error("AdaptiveWeightEngine.execute_adaptive failed: %s", exc)
            return {"success": False, "error": str(exc)}
        finally:
            session.close()

    def get_weight_history(
        self, strategy_name: Optional[str] = None, days: int = 30
    ) -> Dict[str, Any]:
        """获取策略权重历史趋势。"""
        records = self.cache.get_weight_history(strategy_name, days)

        if not records:
            return {"success": True, "data": {"history": [], "strategies": [], "dates": []}}

        # 转为按日期正序排列
        records.reverse()

        # 按日期分组
        dates = sorted(set(r["trade_date"] for r in records))
        strategies = sorted(set(r["strategy_name"] for r in records))

        # 构建每日权重映射
        weight_by_date: Dict[str, Dict[str, float]] = {}
        for r in records:
            td = r["trade_date"]
            sn = r["strategy_name"]
            if td not in weight_by_date:
                weight_by_date[td] = {}
            weight_by_date[td][sn] = r["weight"]

        # 构建时间序列数据
        timeline = []
        for td in dates:
            point = {"trade_date": td}
            for sn in strategies:
                point[sn] = weight_by_date.get(td, {}).get(sn, 0)
            timeline.append(point)

        return {
            "success": True,
            "data": {
                "history": records,
                "timeline": timeline,
                "strategies": strategies,
                "dates": dates,
            },
        }

    def get_summary(self) -> Dict[str, Any]:
        """自适应权重综合仪表板数据。"""
        try:
            # 获取最新权重
            weight_result = self.calculate_weights()
            if not weight_result.get("success"):
                return weight_result

            data = weight_result["data"]
            weights = data["weights"]

            # 统计
            weight_values = [w["weight"] for w in weights.values()]
            avg_weight = sum(weight_values) / len(weight_values) if weight_values else 0
            max_weight = max(weight_values) if weight_values else 0
            min_weight = min(weight_values) if weight_values else 0
            max_strategy = max(weights.items(), key=lambda x: x[1]["weight"])[0] if weights else ""
            min_strategy = min(weights.items(), key=lambda x: x[1]["weight"])[0] if weights else ""

            # 按分类汇总
            category_weights: Dict[str, float] = {}
            category_counts: Dict[str, int] = {}
            for name, w in weights.items():
                cat = w.get("category", "other")
                category_weights[cat] = category_weights.get(cat, 0) + w["weight"]
                category_counts[cat] = category_counts.get(cat, 0) + 1

            # 获取历史权重变化
            history_result = self.get_weight_history(days=10)

            summary = {
                "trade_date": data["trade_date"],
                "regime": data["regime"],
                "regime_label": data["regime_label"],
                "total_strategies": data["total_strategies"],
                "avg_weight": round(avg_weight, 4),
                "max_weight": round(max_weight, 4),
                "min_weight": round(min_weight, 4),
                "max_weight_strategy": max_strategy,
                "min_weight_strategy": min_strategy,
                "category_weights": {
                    cat: {
                        "total_weight": round(w, 4),
                        "count": category_counts.get(cat, 0),
                        "avg_weight": round(w / category_counts[cat], 4) if category_counts.get(cat, 0) > 0 else 0,
                    }
                    for cat, w in category_weights.items()
                },
                "factor_weights": data["factor_weights"],
                "weights": weights,
                "history_timeline": history_result.get("data", {}).get("timeline", []),
                "history_strategies": history_result.get("data", {}).get("strategies", []),
            }

            return {"success": True, "data": summary}

        except Exception as exc:
            logger.error("AdaptiveWeightEngine.get_summary failed: %s", exc)
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # 内部方法：分数计算
    # ------------------------------------------------------------------

    def _calc_performance_scores(
        self, session, trade_date: str, lookback_days: int
    ) -> Dict[str, float]:
        """计算策略表现分数 (40%)。

        最近5天权重2x，其余15天权重1x。
        基于胜率和平均收益率。
        """
        try:
            # 获取最近N个交易日有表现数据的日期
            rows = session.execute(
                text("""
                    SELECT DISTINCT trade_date FROM strategy_performance
                    WHERE ret_1d IS NOT NULL
                    ORDER BY trade_date DESC
                    LIMIT :limit
                """),
                {"limit": lookback_days},
            ).fetchall()

            if not rows:
                return {}

            all_dates = [r[0] for r in rows]
            recent_5 = set(all_dates[:5])

            # 获取所有策略在这些日期的表现
            placeholders = ", ".join([f":td{i}" for i in range(len(all_dates))])
            params = {}
            for i, td in enumerate(all_dates):
                params[f"td{i}"] = td

            perf_rows = session.execute(
                text(f"""
                    SELECT strategy_name, trade_date, ret_1d
                    FROM strategy_performance
                    WHERE trade_date IN ({placeholders}) AND ret_1d IS NOT NULL
                """),
                params,
            ).fetchall()

            # 按策略聚合
            strategy_stats: Dict[str, Dict] = {}
            for row in perf_rows:
                name = row[0]
                td = row[1]
                ret = float(row[2]) if row[2] is not None else 0

                if name not in strategy_stats:
                    strategy_stats[name] = {
                        "recent_wins": 0, "recent_total": 0,
                        "old_wins": 0, "old_total": 0,
                        "recent_ret_sum": 0, "old_ret_sum": 0,
                    }

                is_recent = td in recent_5
                stats = strategy_stats[name]

                if is_recent:
                    stats["recent_total"] += 1
                    stats["recent_ret_sum"] += ret
                    if ret > 0:
                        stats["recent_wins"] += 1
                else:
                    stats["old_total"] += 1
                    stats["old_ret_sum"] += ret
                    if ret > 0:
                        stats["old_wins"] += 1

            # 计算加权分数
            scores: Dict[str, float] = {}
            for name, stats in strategy_stats.items():
                # 最近5天胜率 (2x权重)
                recent_wr = (stats["recent_wins"] / stats["recent_total"] * 100) if stats["recent_total"] > 0 else 50
                recent_avg_ret = (stats["recent_ret_sum"] / stats["recent_total"]) if stats["recent_total"] > 0 else 0

                # 较早15天胜率 (1x权重)
                old_wr = (stats["old_wins"] / stats["old_total"] * 100) if stats["old_total"] > 0 else 50
                old_avg_ret = (stats["old_ret_sum"] / stats["old_total"]) if stats["old_total"] > 0 else 0

                # 加权胜率
                weighted_wr = (recent_wr * 2 + old_wr) / 3
                # 加权平均收益
                weighted_ret = (recent_avg_ret * 2 + old_avg_ret) / 3

                # 分数 = 胜率贡献 * 0.6 + 收益贡献 * 0.4 (归一化到0-1)
                wr_score = weighted_wr / 100
                # 平均收益归一化: 假设 [-5%, +5%] 映射到 [0, 1]
                ret_score = max(0, min(1, (weighted_ret + 5) / 10))

                scores[name] = wr_score * 0.6 + ret_score * 0.4

            return scores

        except Exception as exc:
            logger.warning("_calc_performance_scores failed: %s", exc)
            return {}

    def _calc_consistency_scores(
        self, session, trade_date: str, lookback_days: int
    ) -> Dict[str, float]:
        """计算策略一致性分数 (25%)。

        低标准差 = 高一致性 = 高分数。
        """
        try:
            # 获取最近N个交易日的日期
            rows = session.execute(
                text("""
                    SELECT DISTINCT trade_date FROM strategy_performance
                    WHERE ret_1d IS NOT NULL
                    ORDER BY trade_date DESC
                    LIMIT :limit
                """),
                {"limit": lookback_days},
            ).fetchall()

            if not rows:
                return {}

            all_dates = [r[0] for r in rows]
            placeholders = ", ".join([f":td{i}" for i in range(len(all_dates))])
            params = {}
            for i, td in enumerate(all_dates):
                params[f"td{i}"] = td

            perf_rows = session.execute(
                text(f"""
                    SELECT strategy_name, ret_1d
                    FROM strategy_performance
                    WHERE trade_date IN ({placeholders}) AND ret_1d IS NOT NULL
                """),
                params,
            ).fetchall()

            # 按策略收集日收益率
            strategy_returns: Dict[str, List[float]] = {}
            for row in perf_rows:
                name = row[0]
                ret = float(row[1]) if row[1] is not None else 0
                if name not in strategy_returns:
                    strategy_returns[name] = []
                strategy_returns[name].append(ret)

            # 计算标准差并归一化
            scores: Dict[str, float] = {}
            for name, returns in strategy_returns.items():
                if len(returns) < 2:
                    scores[name] = 0.5  # 数据不足给中等分
                    continue

                mean = sum(returns) / len(returns)
                variance = sum((r - mean) ** 2 for r in returns) / len(returns)
                std_dev = math.sqrt(variance)

                # 标准差归一化: 0%~5% 映射到 1.0~0.0
                # 低波动 = 高分数
                consistency = max(0, min(1, 1 - std_dev / 5))
                scores[name] = consistency

            return scores

        except Exception as exc:
            logger.warning("_calc_consistency_scores failed: %s", exc)
            return {}

    def _calc_regime_fit_scores(
        self, regime: str, all_strategies: Dict[str, BaseStrategy]
    ) -> Dict[str, float]:
        """计算策略与市场状态的匹配分数 (20%)。"""
        mapping = REGIME_STRATEGY_MAP.get(regime, {})
        best = set(mapping.get("best", []))
        good = set(mapping.get("good", []))
        avoid = set(mapping.get("avoid", []))

        scores: Dict[str, float] = {}
        for name, strat in all_strategies.items():
            if name in best:
                scores[name] = 1.0
            elif name in good:
                scores[name] = 0.7
            elif name in avoid:
                scores[name] = 0.1
            else:
                scores[name] = 0.5  # 未列出的策略给中等分

        return scores

    def _calc_correlation_penalties(
        self, session, trade_date: str
    ) -> Dict[str, float]:
        """计算策略相关性惩罚 (15%)。

        同类别策略的选股重叠越高，惩罚越大。
        不同类别的策略无惩罚。
        """
        try:
            # 获取最新交易日的快照
            latest = session.execute(
                text("""
                    SELECT trade_date FROM strategy_snapshot
                    ORDER BY trade_date DESC LIMIT 1
                """),
            ).fetchone()

            if not latest:
                return {}

            td = latest[0]

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
                return {}

            # 解析每个策略的选股集合
            strategy_picks: Dict[str, set] = {}
            for row in snapshots:
                name = row[0]
                try:
                    picks = json.loads(row[1])
                    codes = set(p.get("ts_code", "") for p in picks if p.get("ts_code"))
                    strategy_picks[name] = codes
                except (json.JSONDecodeError, TypeError):
                    continue

            # 构建策略类别映射
            name_to_category: Dict[str, str] = {}
            for cat, names in STRATEGY_CATEGORIES.items():
                for n in names:
                    name_to_category[n] = cat

            # 计算同类策略间的重叠惩罚
            penalties: Dict[str, float] = {}
            all_names = list(strategy_picks.keys())

            for name in all_names:
                if name not in name_to_category:
                    penalties[name] = 0.0
                    continue

                my_cat = name_to_category[name]
                my_picks = strategy_picks.get(name, set())
                if not my_picks:
                    penalties[name] = 0.0
                    continue

                # 找到同类别策略
                same_cat_count = 0
                overlap_sum = 0.0

                for other_name in all_names:
                    if other_name == name:
                        continue
                    other_cat = name_to_category.get(other_name, "")
                    if other_cat == my_cat:
                        other_picks = strategy_picks.get(other_name, set())
                        if other_picks:
                            # Jaccard 相似系数
                            intersection = len(my_picks & other_picks)
                            union = len(my_picks | other_picks)
                            if union > 0:
                                overlap_sum += intersection / union
                            same_cat_count += 1

                if same_cat_count > 0:
                    avg_overlap = overlap_sum / same_cat_count
                    penalties[name] = avg_overlap  # 0~1
                else:
                    penalties[name] = 0.0

            # 不同类别策略加分（奖励多样性）
            # 这里通过惩罚为0来体现，已经在加权公式中通过 -penalty * W_CORRELATION 实现

            return penalties

        except Exception as exc:
            logger.warning("_calc_correlation_penalties failed: %s", exc)
            return {}

    # ------------------------------------------------------------------
    # 内部方法：归一化和工具
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_scores(scores: Dict[str, float]) -> Dict[str, float]:
        """归一化分数到 [0, 1]。"""
        if not scores:
            return {}

        values = list(scores.values())
        min_v = min(values)
        max_v = max(values)
        range_v = max_v - min_v

        if range_v < 1e-8:
            return {k: 0.5 for k in scores}

        return {k: (v - min_v) / range_v for k, v in scores.items()}

    @staticmethod
    def _normalize_penalties(penalties: Dict[str, float]) -> Dict[str, float]:
        """惩罚分数已经是 [0, 1]，直接返回。"""
        return penalties

    def _save_weight_history(
        self, session, trade_date: str, weight_details: Dict[str, Dict]
    ):
        """保存权重历史到数据库。"""
        try:
            records = []
            for name, detail in weight_details.items():
                records.append({
                    "strategy_name": name,
                    "weight": detail["weight"],
                    "performance_score": detail["performance_score"],
                    "consistency_score": detail["consistency_score"],
                    "regime_fit_score": detail["regime_fit_score"],
                    "correlation_penalty": detail["correlation_penalty"],
                })

            # 先删除当天已有数据
            session.execute(
                text("DELETE FROM strategy_weight_history WHERE trade_date = :td"),
                {"td": trade_date},
            )
            session.commit()

            # 使用 cache 的 upsert 方法
            self.cache.upsert_weight_history(records, trade_date)

        except Exception as exc:
            logger.warning("_save_weight_history failed: %s", exc)
            try:
                session.rollback()
            except Exception:
                pass

    def _detect_regime(self) -> Dict[str, Any]:
        """检测市场状态。"""
        try:
            detector = MarketRegimeDetector(self.cache)
            result = detector.detect()
            if result.get("success"):
                return result["data"]
        except Exception as exc:
            logger.warning("_detect_regime failed: %s", exc)
        return {"regime": "sideways", "confidence": 0.5}

    @staticmethod
    def _get_regime_label(regime: str) -> str:
        labels = {"bull": "牛市", "bear": "熊市", "sideways": "震荡", "extreme": "极端"}
        return labels.get(regime, "未知")

    @staticmethod
    def _get_latest_trade_date(session) -> str:
        result = session.execute(
            text("SELECT MAX(trade_date) FROM strategy_snapshot WHERE strategy_name != '_regime_snapshot'"),
        ).fetchone()
        if result and result[0]:
            return result[0]
        result = session.execute(
            text("SELECT MAX(trade_date) FROM strategy_performance"),
        ).fetchone()
        if result and result[0]:
            return result[0]
        # Fallback to today
        return datetime.now().strftime("%Y%m%d")
