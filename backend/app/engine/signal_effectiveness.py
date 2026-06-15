"""策略信号有效性追踪器——分析信号质量趋势，生成信任度评分和暴露建议。"""

import logging
import math
from typing import Dict, Any, List, Optional
from collections import defaultdict

from ..models import SessionLocal, StrategyPerformance
from ..engine.registry import get_all_strategies, load_all_strategies

logger = logging.getLogger(__name__)


class SignalEffectivenessEngine:
    """策略信号有效性追踪器——分析信号质量趋势，生成信任度评分和暴露建议。"""

    def __init__(self, cache=None):
        self.cache = cache

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _get_trade_dates(self, lookback_days: int = 20, end_date: str = None) -> List[str]:
        """获取最近 N 个交易日（升序）。"""
        session = SessionLocal()
        try:
            if end_date:
                rows = (
                    session.query(StrategyPerformance.trade_date)
                    .filter(StrategyPerformance.trade_date <= end_date)
                    .distinct()
                    .order_by(StrategyPerformance.trade_date.desc())
                    .limit(lookback_days)
                    .all()
                )
            else:
                rows = (
                    session.query(StrategyPerformance.trade_date)
                    .distinct()
                    .order_by(StrategyPerformance.trade_date.desc())
                    .limit(lookback_days)
                    .all()
                )
            return sorted([r[0] for r in rows])
        except Exception as exc:
            logger.error("_get_trade_dates failed: %s", exc)
            return []
        finally:
            session.close()

    def _get_performance_data(
        self, trade_dates: List[str], strategy_name: str = None
    ) -> List[Dict]:
        """获取指定日期范围内的策略表现数据。"""
        if not trade_dates:
            return []
        session = SessionLocal()
        try:
            q = session.query(StrategyPerformance).filter(
                StrategyPerformance.trade_date.in_(trade_dates)
            )
            if strategy_name:
                q = q.filter(StrategyPerformance.strategy_name == strategy_name)
            rows = q.order_by(
                StrategyPerformance.trade_date.asc(),
                StrategyPerformance.strategy_name.asc(),
            ).all()
            return [
                {
                    "trade_date": r.trade_date,
                    "strategy_name": r.strategy_name,
                    "ts_code": r.ts_code,
                    "name": r.name,
                    "entry_score": r.entry_score or 0,
                    "entry_price": r.entry_price or 0,
                    "ret_1d": r.ret_1d,
                    "ret_3d": r.ret_3d,
                    "ret_5d": r.ret_5d,
                }
                for r in rows
            ]
        except Exception as exc:
            logger.error("_get_performance_data failed: %s", exc)
            return []
        finally:
            session.close()

    def _get_all_strategy_names(self) -> List[str]:
        """获取所有已注册策略名称列表。"""
        load_all_strategies()
        strategies = get_all_strategies()
        return list(strategies.keys()) if isinstance(strategies, dict) else list(strategies)

    def _get_strategy_meta(self) -> Dict[str, Dict]:
        """获取策略元信息（name → {category, icon, description}）。"""
        load_all_strategies()
        strategies = get_all_strategies()
        meta = {}
        for name, s in strategies.items():
            meta[name] = {
                "category": getattr(s, "category", "unknown"),
                "icon": getattr(s, "icon", ""),
                "description": getattr(s, "description", ""),
            }
        return meta

    @staticmethod
    def _pearson_correlation(xs: List[float], ys: List[float]) -> float:
        """计算 Pearson 相关系数。"""
        n = len(xs)
        if n < 3:
            return 0.0
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        std_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
        std_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
        if std_x == 0 or std_y == 0:
            return 0.0
        return round(cov / (std_x * std_y), 4)

    @staticmethod
    def _linear_slope(xs: List[float], ys: List[float]) -> float:
        """简单线性回归斜率。"""
        n = len(xs)
        if n < 2:
            return 0.0
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
        var_x = sum((x - mean_x) ** 2 for x in xs)
        if var_x == 0:
            return 0.0
        return round(cov / var_x, 6)

    @staticmethod
    def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
        return max(lo, min(hi, value))

    # ------------------------------------------------------------------
    # A) 信号质量分布
    # ------------------------------------------------------------------

    def get_signal_quality_distribution(
        self, trade_date: str = None, lookback_days: int = 20
    ) -> Dict:
        """信号质量分布——分析各策略的信号评分与实际收益的关系。"""
        trade_dates = self._get_trade_dates(lookback_days, trade_date)
        if not trade_dates:
            return {"strategies": [], "summary": {"total": 0}}

        perf_data = self._get_performance_data(trade_dates)
        meta = self._get_strategy_meta()

        # 按策略分组
        by_strategy: Dict[str, List[Dict]] = defaultdict(list)
        for row in perf_data:
            by_strategy[row["strategy_name"]].append(row)

        strategies = []
        total_strategies = 0
        excellent_count = 0
        good_count = 0
        fair_count = 0
        poor_count = 0

        for sname, picks in by_strategy.items():
            total_strategies += 1
            smeta = meta.get(sname, {"category": "unknown", "icon": "", "description": ""})

            # 按 entry_score 排序并分成 4 个分位数
            valid_picks = [p for p in picks if p["entry_score"] > 0]
            if len(valid_picks) < 4:
                # 数据太少，跳过分位数分析
                strategies.append({
                    "name": sname,
                    "category": smeta["category"],
                    "icon": smeta["icon"],
                    "description": smeta["description"],
                    "score_tiers": [],
                    "score_return_correlation": 0.0,
                    "consistency_score": 0.0,
                    "overall_quality": "insufficient_data",
                })
                continue

            valid_picks.sort(key=lambda p: p["entry_score"], reverse=True)
            quartile_size = max(1, len(valid_picks) // 4)
            tiers = []
            tier_labels = ["top_25%", "upper_mid", "lower_mid", "bottom_25%"]
            for i, label in enumerate(tier_labels):
                start = i * quartile_size
                end = start + quartile_size if i < 3 else len(valid_picks)
                tier_picks = valid_picks[start:end]
                if not tier_picks:
                    continue
                avg_score = round(
                    sum(p["entry_score"] for p in tier_picks) / len(tier_picks), 2
                )
                # 计算各周期平均收益（排除 None）
                for period, key in [("1d", "ret_1d"), ("3d", "ret_3d"), ("5d", "ret_5d")]:
                    vals = [p[key] for p in tier_picks if p[key] is not None]
                    avg_ret = round(sum(vals) / len(vals) * 100, 2) if vals else None

                tiers.append({
                    "tier": label,
                    "avg_score": avg_score,
                    "avg_ret_1d": _safe_avg_ret(tier_picks, "ret_1d"),
                    "avg_ret_3d": _safe_avg_ret(tier_picks, "ret_3d"),
                    "avg_ret_5d": _safe_avg_ret(tier_picks, "ret_5d"),
                    "count": len(tier_picks),
                })

            # 评分-收益相关性：用 entry_score vs ret_1d（有值的）
            valid_for_corr = [
                p for p in valid_picks if p["ret_1d"] is not None
            ]
            if len(valid_for_corr) >= 5:
                scores = [p["entry_score"] for p in valid_for_corr]
                rets = [p["ret_1d"] for p in valid_for_corr]
                correlation = self._pearson_correlation(scores, rets)
            else:
                correlation = 0.0

            # 一致性评分：按日期分组，计算每天 top_25% 是否优于 bottom_25%
            win_days = 0
            total_days = 0
            by_date: Dict[str, List[Dict]] = defaultdict(list)
            for p in valid_picks:
                by_date[p["trade_date"]].append(p)

            for td, day_picks in by_date.items():
                day_picks_sorted = sorted(day_picks, key=lambda p: p["entry_score"], reverse=True)
                mid = max(1, len(day_picks_sorted) // 2)
                top_half = day_picks_sorted[:mid]
                bot_half = day_picks_sorted[mid:]
                if not bot_half:
                    continue
                top_ret = _safe_avg_ret(top_half, "ret_1d")
                bot_ret = _safe_avg_ret(bot_half, "ret_1d")
                if top_ret is not None and bot_ret is not None:
                    total_days += 1
                    if top_ret > bot_ret:
                        win_days += 1

            consistency = round(win_days / total_days * 100, 1) if total_days > 0 else 0.0

            # 综合质量等级
            if correlation > 0.3 and consistency > 60:
                overall_quality = "excellent"
                excellent_count += 1
            elif correlation > 0.1 and consistency > 45:
                overall_quality = "good"
                good_count += 1
            elif correlation > -0.1 and consistency > 35:
                overall_quality = "fair"
                fair_count += 1
            else:
                overall_quality = "poor"
                poor_count += 1

            strategies.append({
                "name": sname,
                "category": smeta["category"],
                "icon": smeta["icon"],
                "description": smeta["description"],
                "score_tiers": tiers,
                "score_return_correlation": correlation,
                "consistency_score": consistency,
                "overall_quality": overall_quality,
            })

        strategies.sort(key=lambda s: s["score_return_correlation"], reverse=True)

        return {
            "strategies": strategies,
            "summary": {
                "total": total_strategies,
                "excellent": excellent_count,
                "good": good_count,
                "fair": fair_count,
                "poor": poor_count,
                "date_range": {
                    "start": trade_dates[0] if trade_dates else None,
                    "end": trade_dates[-1] if trade_dates else None,
                },
            },
        }

    # ------------------------------------------------------------------
    # B) 策略信任度评分
    # ------------------------------------------------------------------

    def get_strategy_trust_scores(self, lookback_days: int = 20) -> Dict:
        """策略信任度评分——综合多个维度计算每个策略的可信度。"""
        trade_dates = self._get_trade_dates(lookback_days)
        if not trade_dates:
            return {"strategies": [], "summary": {"avg_trust": 0, "strategies_by_grade": {}}}

        perf_data = self._get_performance_data(trade_dates)
        meta = self._get_strategy_meta()

        by_strategy: Dict[str, List[Dict]] = defaultdict(list)
        for row in perf_data:
            by_strategy[row["strategy_name"]].append(row)

        strategies = []

        for sname, picks in by_strategy.items():
            smeta = meta.get(sname, {"category": "unknown", "icon": "", "description": ""})
            valid_picks = [p for p in picks if p["entry_score"] > 0]

            if len(valid_picks) < 5:
                strategies.append({
                    "name": sname,
                    "category": smeta["category"],
                    "icon": smeta["icon"],
                    "trust_score": 0,
                    "trust_grade": "D",
                    "components": {
                        "signal_quality": 0,
                        "consistency": 0,
                        "trend": 0,
                        "sample_size": 0,
                    },
                    "recommendation": "avoid",
                    "rationale": "数据样本不足，无法评估",
                })
                continue

            # --- 维度1: 信号质量 (40%) ---
            valid_for_corr = [p for p in valid_picks if p["ret_1d"] is not None]
            if len(valid_for_corr) >= 5:
                scores = [p["entry_score"] for p in valid_for_corr]
                rets = [p["ret_1d"] for p in valid_for_corr]
                correlation = self._pearson_correlation(scores, rets)
            else:
                correlation = 0.0

            # tier spread: top_25% avg return vs bottom_25% avg return
            sorted_picks = sorted(valid_picks, key=lambda p: p["entry_score"], reverse=True)
            q_size = max(1, len(sorted_picks) // 4)
            top_q = sorted_picks[:q_size]
            bot_q = sorted_picks[-q_size:]
            top_ret = _safe_avg_ret(top_q, "ret_1d") or 0
            bot_ret = _safe_avg_ret(bot_q, "ret_1d") or 0
            tier_spread = top_ret - bot_ret  # positive = good

            # 信号质量归一化到 0-100
            sq_raw = correlation * 50 + tier_spread * 5  # heuristics
            signal_quality = self._clamp(sq_raw * 2, 0, 100)

            # --- 维度2: 一致性 (25%) ---
            by_date: Dict[str, List[Dict]] = defaultdict(list)
            for p in valid_picks:
                by_date[p["trade_date"]].append(p)
            win_days = 0
            total_days = 0
            for td, day_picks in by_date.items():
                day_sorted = sorted(day_picks, key=lambda p: p["entry_score"], reverse=True)
                mid = max(1, len(day_sorted) // 2)
                top_half = day_sorted[:mid]
                bot_half = day_sorted[mid:]
                if not bot_half:
                    continue
                top_ret_d = _safe_avg_ret(top_half, "ret_1d")
                bot_ret_d = _safe_avg_ret(bot_half, "ret_1d")
                if top_ret_d is not None and bot_ret_d is not None:
                    total_days += 1
                    if top_ret_d > bot_ret_d:
                        win_days += 1
            consistency = round(win_days / total_days * 100, 1) if total_days > 0 else 0.0

            # --- 维度3: 趋势 (20%) ---
            # 将日期分成前半和后半，比较两段的信号质量
            unique_dates = sorted(by_date.keys())
            half = len(unique_dates) // 2
            if half >= 2:
                recent_dates = set(unique_dates[half:])
                older_dates = set(unique_dates[:half])
                recent_picks = [p for p in valid_picks if p["trade_date"] in recent_dates]
                older_picks = [p for p in valid_picks if p["trade_date"] in older_dates]
                recent_corr = 0.0
                older_corr = 0.0
                if len(recent_picks) >= 5:
                    r_valid = [p for p in recent_picks if p["ret_1d"] is not None]
                    if len(r_valid) >= 5:
                        recent_corr = self._pearson_correlation(
                            [p["entry_score"] for p in r_valid],
                            [p["ret_1d"] for p in r_valid],
                        )
                if len(older_picks) >= 5:
                    o_valid = [p for p in older_picks if p["ret_1d"] is not None]
                    if len(o_valid) >= 5:
                        older_corr = self._pearson_correlation(
                            [p["entry_score"] for p in o_valid],
                            [p["ret_1d"] for p in o_valid],
                        )
                trend_diff = recent_corr - older_corr
                trend_score = self._clamp(50 + trend_diff * 100, 0, 100)
            else:
                trend_score = 50.0  # insufficient data, neutral

            # --- 维度4: 样本量 (15%) ---
            sample_count = len(valid_picks)
            # diminishing returns: log scale
            if sample_count > 0:
                sample_score = min(100, math.log(sample_count + 1) / math.log(200) * 100)
            else:
                sample_score = 0.0

            # --- 综合信任度 ---
            trust_score = round(
                signal_quality * 0.40
                + consistency * 0.25
                + trend_score * 0.20
                + sample_score * 0.15,
                1,
            )
            trust_score = self._clamp(trust_score)

            # 信任等级
            if trust_score >= 85:
                trust_grade = "A+"
            elif trust_score >= 75:
                trust_grade = "A"
            elif trust_score >= 65:
                trust_grade = "B+"
            elif trust_score >= 55:
                trust_grade = "B"
            elif trust_score >= 45:
                trust_grade = "C+"
            elif trust_score >= 35:
                trust_grade = "C"
            else:
                trust_grade = "D"

            # 暴露建议
            if trust_score >= 70 and trend_score >= 55:
                recommendation = "increase_exposure"
                rationale = f"信号质量高(相关性={correlation:.2f})，一致性好({consistency:.0f}%)，趋势向好"
            elif trust_score >= 50:
                recommendation = "maintain"
                rationale = f"信号质量中等(相关性={correlation:.2f})，一致性一般({consistency:.0f}%)"
            elif trust_score >= 30:
                recommendation = "decrease_exposure"
                rationale = f"信号质量较低(相关性={correlation:.2f})，建议减少暴露"
            else:
                recommendation = "avoid"
                rationale = f"信号不可靠(相关性={correlation:.2f}，一致性={consistency:.0f}%)，建议回避"

            strategies.append({
                "name": sname,
                "category": smeta["category"],
                "icon": smeta["icon"],
                "trust_score": trust_score,
                "trust_grade": trust_grade,
                "components": {
                    "signal_quality": round(signal_quality, 1),
                    "consistency": round(consistency, 1),
                    "trend": round(trend_score, 1),
                    "sample_size": round(sample_score, 1),
                },
                "recommendation": recommendation,
                "rationale": rationale,
            })

        strategies.sort(key=lambda s: s["trust_score"], reverse=True)

        # 统计等级分布
        grade_counts: Dict[str, int] = defaultdict(int)
        for s in strategies:
            grade_counts[s["trust_grade"]] += 1

        avg_trust = (
            round(sum(s["trust_score"] for s in strategies) / len(strategies), 1)
            if strategies else 0
        )

        return {
            "strategies": strategies,
            "summary": {
                "avg_trust": avg_trust,
                "strategies_by_grade": dict(grade_counts),
                "total": len(strategies),
            },
        }

    # ------------------------------------------------------------------
    # C) 信号有效性趋势
    # ------------------------------------------------------------------

    def get_effectiveness_trend(
        self, strategy_name: str = None, days: int = 30
    ) -> Dict:
        """信号有效性趋势——追踪策略信号质量随时间的变化。"""
        trade_dates = self._get_trade_dates(days)
        if not trade_dates:
            return {
                "strategy_name": strategy_name or "all",
                "trend_data": [],
                "trend_direction": "insufficient_data",
                "trend_slope": 0.0,
            }

        # 逐日计算
        trend_data = []
        correlations = []
        wins = []

        for td in trade_dates:
            day_perf = self._get_performance_data([td], strategy_name)
            valid_picks = [p for p in day_perf if p["entry_score"] > 0]

            avg_score = 0.0
            avg_ret_1d = None
            win_rate = 0.0
            corr = 0.0

            if valid_picks:
                avg_score = round(
                    sum(p["entry_score"] for p in valid_picks) / len(valid_picks), 2
                )

                rets_1d = [p["ret_1d"] for p in valid_picks if p["ret_1d"] is not None]
                if rets_1d:
                    avg_ret_1d = round(sum(rets_1d) / len(rets_1d) * 100, 2)

                # 胜率 (ret_1d > 0)
                positive = sum(1 for r in rets_1d if r > 0)
                win_rate = round(positive / len(rets_1d) * 100, 1) if rets_1d else 0.0

                # 当天评分-收益相关性
                valid_for_corr = [
                    p for p in valid_picks if p["ret_1d"] is not None
                ]
                if len(valid_for_corr) >= 3:
                    corr = self._pearson_correlation(
                        [p["entry_score"] for p in valid_for_corr],
                        [p["ret_1d"] for p in valid_for_corr],
                    )

            trend_data.append({
                "date": td,
                "avg_score": avg_score,
                "avg_ret_1d": avg_ret_1d,
                "win_rate": win_rate,
                "correlation": corr,
                "pick_count": len(valid_picks),
            })
            correlations.append(corr)

        # 趋势方向
        xs = list(range(len(correlations)))
        if len(correlations) >= 3:
            slope = self._linear_slope(xs, correlations)
            if slope > 0.005:
                trend_direction = "improving"
            elif slope < -0.005:
                trend_direction = "declining"
            else:
                trend_direction = "stable"
        else:
            slope = 0.0
            trend_direction = "insufficient_data"

        # 最佳/最差期间
        valid_trend = [t for t in trend_data if t["avg_ret_1d"] is not None]
        best_period = None
        worst_period = None
        if valid_trend:
            best = max(valid_trend, key=lambda t: t["avg_ret_1d"])
            worst = min(valid_trend, key=lambda t: t["avg_ret_1d"])
            best_period = {"date": best["date"], "avg_ret_1d": best["avg_ret_1d"]}
            worst_period = {"date": worst["date"], "avg_ret_1d": worst["avg_ret_1d"]}

        return {
            "strategy_name": strategy_name or "all",
            "trend_data": trend_data,
            "trend_direction": trend_direction,
            "trend_slope": slope,
            "best_period": best_period,
            "worst_period": worst_period,
        }

    # ------------------------------------------------------------------
    # D) 暴露调整建议
    # ------------------------------------------------------------------

    def get_rebalancing_recommendations(self, lookback_days: int = 20) -> Dict:
        """暴露调整建议——基于信号有效性推荐策略权重调整。"""
        trust_data = self.get_strategy_trust_scores(lookback_days)
        trend_data_all = self.get_effectiveness_trend(None, lookback_days)

        meta = self._get_strategy_meta()

        # 历史信任度（前半段 vs 后半段）
        trade_dates = self._get_trade_dates(lookback_days)
        half = len(trade_dates) // 2 if trade_dates else 0

        recent_trust = {}
        older_trust = {}
        if half >= 2:
            recent_dates = trade_dates[half:]
            older_dates = trade_dates[:half]
            for dates, store in [(recent_dates, recent_trust), (older_dates, older_trust)]:
                perf = self._get_performance_data(dates)
                by_s: Dict[str, List[Dict]] = defaultdict(list)
                for p in perf:
                    by_s[p["strategy_name"]].append(p)
                for sname, picks in by_s.items():
                    valid = [p for p in picks if p["entry_score"] > 0]
                    if len(valid) >= 3:
                        valid_c = [p for p in valid if p["ret_1d"] is not None]
                        if len(valid_c) >= 3:
                            corr = self._pearson_correlation(
                                [p["entry_score"] for p in valid_c],
                                [p["ret_1d"] for p in valid_c],
                            )
                        else:
                            corr = 0.0
                        store[sname] = corr

        # 策略分类汇总
        category_data: Dict[str, List[Dict]] = defaultdict(list)
        for s in trust_data["strategies"]:
            cat = s["category"]
            category_data[cat].append(s)

        category_summary = {}
        for cat, strats in category_data.items():
            category_summary[cat] = {
                "total": len(strats),
                "avg_trust": round(
                    sum(s["trust_score"] for s in strats) / len(strats), 1
                ) if strats else 0,
            }

        # 构建建议
        recommendations = []
        for s in trust_data["strategies"]:
            sname = s["name"]
            smeta = meta.get(sname, {"category": "unknown", "icon": "", "description": ""})
            trust_score = s["trust_score"]

            # 判断推荐暴露水平
            if trust_score >= 70:
                recommended = "increase"
                change_pct = round(min(20, (trust_score - 60) * 0.5), 1)
            elif trust_score >= 50:
                recommended = "standard"
                change_pct = 0.0
            elif trust_score >= 30:
                recommended = "decrease"
                change_pct = round(-min(30, (60 - trust_score) * 0.5), 1)
            else:
                recommended = "avoid"
                change_pct = -50.0

            # 趋势调整
            trend_info = trend_data_all.get("trend_direction", "stable")
            if trend_info == "improving" and recommended == "standard":
                recommended = "increase"
                change_pct = 5.0
            elif trend_info == "declining" and recommended == "increase":
                recommended = "standard"
                change_pct = 0.0

            # 信心等级
            if trust_score >= 60:
                confidence = "high"
            elif trust_score >= 35:
                confidence = "medium"
            else:
                confidence = "low"

            # 生成详细理由
            comp = s.get("components", {})
            rationale_parts = []
            if comp.get("signal_quality", 0) >= 60:
                rationale_parts.append(f"信号质量好({comp['signal_quality']:.0f})")
            elif comp.get("signal_quality", 0) < 30:
                rationale_parts.append(f"信号质量差({comp['signal_quality']:.0f})")
            if comp.get("consistency", 0) >= 60:
                rationale_parts.append(f"一致性高({comp['consistency']:.0f}%)")
            elif comp.get("consistency", 0) < 30:
                rationale_parts.append(f"一致性低({comp['consistency']:.0f}%)")
            if comp.get("trend", 0) >= 60:
                rationale_parts.append("趋势向好")
            elif comp.get("trend", 0) < 40:
                rationale_parts.append("趋势恶化")

            rationale = "；".join(rationale_parts) if rationale_parts else s.get("rationale", "")

            recommendations.append({
                "strategy_name": sname,
                "category": smeta.get("category", s["category"]),
                "icon": smeta.get("icon", s.get("icon", "")),
                "current_exposure": "standard",
                "recommended_exposure": recommended,
                "exposure_change_pct": change_pct,
                "rationale": rationale,
                "confidence": confidence,
            })

        recommendations.sort(key=lambda r: r["exposure_change_pct"], reverse=True)

        # 整体 regime alignment
        avg_trust = trust_data["summary"].get("avg_trust", 0)
        if avg_trust >= 60:
            regime_alignment = "aligned"
        elif avg_trust >= 40:
            regime_alignment = "partial"
        else:
            regime_alignment = "misaligned"

        return {
            "recommendations": recommendations,
            "category_summary": category_summary,
            "regime_alignment": regime_alignment,
            "summary": {
                "avg_trust": avg_trust,
                "total_strategies": len(recommendations),
                "increase_count": sum(1 for r in recommendations if r["recommended_exposure"] == "increase"),
                "decrease_count": sum(1 for r in recommendations if r["recommended_exposure"] == "decrease"),
                "avoid_count": sum(1 for r in recommendations if r["recommended_exposure"] == "avoid"),
            },
        }


# ------------------------------------------------------------------
# 辅助函数
# ------------------------------------------------------------------

def _safe_avg_ret(picks: List[Dict], key: str) -> Optional[float]:
    """安全计算平均收益率（百分比），返回 None 如果没有有效数据。"""
    vals = [p[key] for p in picks if p[key] is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals) * 100, 2)
