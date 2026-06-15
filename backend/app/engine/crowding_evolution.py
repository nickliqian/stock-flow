"""策略拥挤度演进引擎——追踪策略选股宽度变化、检测拥挤与退潮、计算多样性指数。"""

import logging
import json
import math
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..models import SessionLocal, StrategySnapshot
from ..engine.registry import get_all_strategies, load_all_strategies

logger = logging.getLogger(__name__)


class StrategyCrowdingEvolutionEngine:
    """策略拥挤度演进引擎：追踪策略拥挤变化、检测拥挤退潮、多样性指数。"""

    def __init__(self, cache=None):
        self.cache = cache

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    def _get_trade_dates(self, lookback_days: int = 30, end_date: str = None) -> List[str]:
        """获取最近 N 个交易日（升序），用于滚动窗口计算。"""
        session = SessionLocal()
        try:
            if end_date:
                rows = (
                    session.query(StrategySnapshot.trade_date)
                    .filter(StrategySnapshot.trade_date <= end_date)
                    .distinct()
                    .order_by(StrategySnapshot.trade_date.desc())
                    .limit(lookback_days)
                    .all()
                )
            else:
                rows = (
                    session.query(StrategySnapshot.trade_date)
                    .distinct()
                    .order_by(StrategySnapshot.trade_date.desc())
                    .limit(lookback_days)
                    .all()
                )
            dates = sorted([r[0] for r in rows])
            return dates
        except Exception as exc:
            logger.error("_get_trade_dates failed: %s", exc)
            return []
        finally:
            session.close()

    def _get_snapshots_by_date(self, trade_dates: List[str]) -> Dict[str, List[Dict]]:
        """按日期分组获取所有快照数据。"""
        if not trade_dates:
            return {}
        session = SessionLocal()
        try:
            rows = (
                session.query(StrategySnapshot)
                .filter(StrategySnapshot.trade_date.in_(trade_dates))
                .order_by(StrategySnapshot.trade_date.asc(), StrategySnapshot.strategy_name.asc())
                .all()
            )
            result: Dict[str, List[Dict]] = {}
            for row in rows:
                td = row.trade_date
                if td not in result:
                    result[td] = []
                result[td].append({
                    "strategy_name": row.strategy_name,
                    "pick_count": row.pick_count or 0,
                    "top_picks": row.top_picks or "",
                    "avg_score": row.avg_score or 0,
                    "max_score": row.max_score or 0,
                })
            return result
        except Exception as exc:
            logger.error("_get_snapshots_by_date failed: %s", exc)
            return {}
        finally:
            session.close()

    def _get_all_strategy_names(self) -> List[str]:
        """获取所有已注册策略名称列表。"""
        load_all_strategies()
        strategies = get_all_strategies()
        return list(strategies.keys()) if isinstance(strategies, dict) else list(strategies)

    def _parse_top_picks(self, top_picks_str: str) -> List[str]:
        """从 top_picks JSON 字符串中提取 ts_code 列表。"""
        if not top_picks_str:
            return []
        try:
            picks = json.loads(top_picks_str)
            if isinstance(picks, list):
                return [p.get("ts_code", "") for p in picks if p.get("ts_code")]
        except (json.JSONDecodeError, TypeError):
            pass
        return []

    @staticmethod
    def _rolling_stats(values: List[float], window: int = 7) -> Dict[str, float]:
        """计算滚动均值和标准差（基于最近 window 个值）。"""
        if not values:
            return {"avg": 0, "std": 0}
        recent = values[-window:]
        avg = sum(recent) / len(recent)
        if len(recent) < 2:
            return {"avg": round(avg, 2), "std": 0}
        variance = sum((v - avg) ** 2 for v in recent) / (len(recent) - 1)
        std = math.sqrt(variance)
        return {"avg": round(avg, 2), "std": round(std, 2)}

    # ------------------------------------------------------------------
    # A) 策略拥挤度演进
    # ------------------------------------------------------------------

    def get_crowding_evolution(self, trade_date: str = None, lookback_days: int = 30) -> Dict:
        """获取所有策略的拥挤度演进趋势。

        计算每个策略的当前选股数、滚动均值(7日)、滚动标准差、拥挤比率。
        crowding_ratio > 1.5 标记为"overcrowded"。
        """
        trade_dates = self._get_trade_dates(lookback_days + 7, trade_date)
        if not trade_dates:
            return {
                "success": True,
                "data": {
                    "trade_date": trade_date,
                    "strategies": [],
                    "summary": {"total": 0, "overcrowded": 0, "warning": 0, "normal": 0},
                },
            }

        snapshots = self._get_snapshots_by_date(trade_dates)
        strategy_names = self._get_all_strategy_names()

        target_date = trade_dates[-1] if trade_dates else trade_date
        strategies = []
        overcrowded_count = 0
        warning_count = 0
        normal_count = 0

        for name in strategy_names:
            # 收集该策略在所有日期上的 pick_count
            pick_history = []
            for td in trade_dates:
                day_snaps = snapshots.get(td, [])
                match = next((s for s in day_snaps if s["strategy_name"] == name), None)
                pick_history.append(match["pick_count"] if match else 0)

            current_picks = pick_history[-1] if pick_history else 0
            rolling = self._rolling_stats(pick_history[:-1], window=7)  # 不含当天
            rolling_avg = rolling["avg"]
            rolling_std = rolling["std"]

            # 拥挤比率
            if rolling_avg > 0:
                crowding_ratio = round(current_picks / rolling_avg, 2)
            else:
                crowding_ratio = round(current_picks, 2) if current_picks > 0 else 1.0

            # 状态判定
            if crowding_ratio > 1.5:
                status = "overcrowded"
                overcrowded_count += 1
            elif crowding_ratio > 1.2:
                status = "warning"
                warning_count += 1
            else:
                status = "normal"
                normal_count += 1

            # 近期趋势
            recent_3 = pick_history[-3:] if len(pick_history) >= 3 else pick_history
            trend = "stable"
            if len(recent_3) >= 2:
                if recent_3[-1] > recent_3[0] * 1.3:
                    trend = "rising"
                elif recent_3[-1] < recent_3[0] * 0.7:
                    trend = "falling"

            strategies.append({
                "strategy_name": name,
                "current_picks": current_picks,
                "rolling_avg": rolling_avg,
                "rolling_std": rolling_std,
                "crowding_ratio": crowding_ratio,
                "status": status,
                "trend": trend,
                "history": [{"date": td, "picks": p} for td, p in zip(trade_dates, pick_history)],
            })

        strategies.sort(key=lambda x: x["crowding_ratio"], reverse=True)

        return {
            "success": True,
            "data": {
                "trade_date": target_date,
                "lookback_days": lookback_days,
                "strategies": strategies,
                "summary": {
                    "total": len(strategies),
                    "overcrowded": overcrowded_count,
                    "warning": warning_count,
                    "normal": normal_count,
                },
            },
        }

    # ------------------------------------------------------------------
    # B) 拥挤告警
    # ------------------------------------------------------------------

    def get_crowding_alerts(self, trade_date: str = None) -> Dict:
        """获取当前拥挤度告警。

        检测：1) 当天 overcrowded 的策略 2) 拥挤度急剧上升 3) 拥挤后退潮信号。
        """
        trade_dates = self._get_trade_dates(15, trade_date)
        if not trade_dates:
            return {"success": True, "data": {"alerts": [], "count": 0}}

        snapshots = self._get_snapshots_by_date(trade_dates)
        strategy_names = self._get_all_strategy_names()
        target_date = trade_dates[-1]

        alerts = []

        for name in strategy_names:
            pick_history = []
            for td in trade_dates:
                day_snaps = snapshots.get(td, [])
                match = next((s for s in day_snaps if s["strategy_name"] == name), None)
                pick_history.append(match["pick_count"] if match else 0)

            if len(pick_history) < 3:
                continue

            # 滚动统计
            rolling = self._rolling_stats(pick_history[:-1], window=7)
            rolling_avg = rolling["avg"]
            current = pick_history[-1]

            if rolling_avg <= 0:
                continue

            ratio = current / rolling_avg

            # 告警1: 当天 overcrowded
            if ratio > 1.5:
                alerts.append({
                    "strategy_name": name,
                    "alert_type": "overcrowded",
                    "severity": "high",
                    "message": f"策略 {name} 当前选股数({current})是滚动均值({rolling_avg})的{ratio:.1f}倍，已达到拥挤",
                    "crowding_ratio": round(ratio, 2),
                    "current_picks": current,
                    "rolling_avg": rolling_avg,
                    "trade_date": target_date,
                })

            # 告警2: 拥挤度急剧上升（连续2天 ratio > 1.3 且上升）
            if len(pick_history) >= 3:
                prev_ratio_1 = pick_history[-2] / rolling_avg if rolling_avg > 0 else 0
                prev_ratio_2 = pick_history[-3] / rolling_avg if rolling_avg > 0 else 0
                if ratio > 1.3 and prev_ratio_1 > 1.3 and ratio > prev_ratio_1:
                    alerts.append({
                        "strategy_name": name,
                        "alert_type": "surging",
                        "severity": "high",
                        "message": f"策略 {name} 拥挤度持续上升: {prev_ratio_2:.1f} → {prev_ratio_1:.1f} → {ratio:.1f}",
                        "crowding_ratio": round(ratio, 2),
                        "current_picks": current,
                        "rolling_avg": rolling_avg,
                        "trade_date": target_date,
                    })

            # 告警3: 拥挤后退潮（昨天 overcrowded，今天大幅下降）
            if len(pick_history) >= 2:
                prev_ratio = pick_history[-2] / rolling_avg if rolling_avg > 0 else 0
                if prev_ratio > 1.5 and ratio < 1.0:
                    alerts.append({
                        "strategy_name": name,
                        "alert_type": "cooling_off",
                        "severity": "medium",
                        "message": f"策略 {name} 拥挤后退潮: 比率从 {prev_ratio:.1f} 降至 {ratio:.1f}",
                        "crowding_ratio": round(ratio, 2),
                        "prev_crowding_ratio": round(prev_ratio, 2),
                        "current_picks": current,
                        "rolling_avg": rolling_avg,
                        "trade_date": target_date,
                    })

            # 告警4: 中度拥挤
            if 1.2 < ratio <= 1.5:
                alerts.append({
                    "strategy_name": name,
                    "alert_type": "warning",
                    "severity": "low",
                    "message": f"策略 {name} 接近拥挤区间，比率={ratio:.1f}",
                    "crowding_ratio": round(ratio, 2),
                    "current_picks": current,
                    "rolling_avg": rolling_avg,
                    "trade_date": target_date,
                })

        # 按严重程度排序
        severity_order = {"high": 0, "medium": 1, "low": 2}
        alerts.sort(key=lambda x: severity_order.get(x["severity"], 3))

        return {
            "success": True,
            "data": {
                "trade_date": target_date,
                "alerts": alerts,
                "count": len(alerts),
                "high_count": sum(1 for a in alerts if a["severity"] == "high"),
                "medium_count": sum(1 for a in alerts if a["severity"] == "medium"),
                "low_count": sum(1 for a in alerts if a["severity"] == "low"),
            },
        }

    # ------------------------------------------------------------------
    # C) 策略多样性指数
    # ------------------------------------------------------------------

    def get_diversity_index(self, trade_date: str = None, lookback_days: int = 30) -> Dict:
        """计算策略多样性指数。

        多样性指数 = 当日活跃策略数 / 总策略数。
        同时追踪每天的多样性指数变化趋势。
        低多样性 = 市场由少数因子驱动（高风险）。
        """
        trade_dates = self._get_trade_dates(lookback_days, trade_date)
        if not trade_dates:
            return {
                "success": True,
                "data": {"diversity_history": [], "current_index": 0, "total_strategies": 0},
            }

        snapshots = self._get_snapshots_by_date(trade_dates)
        strategy_names = self._get_all_strategy_names()
        total = len(strategy_names)

        diversity_history = []
        active_counts = []

        for td in trade_dates:
            day_snaps = snapshots.get(td, [])
            active_strategies = {s["strategy_name"] for s in day_snaps if s["pick_count"] > 0}
            active_count = len(active_strategies)
            index = round(active_count / total, 4) if total > 0 else 0

            # 同时计算每日总选股数和平均选股数
            total_picks = sum(s["pick_count"] for s in day_snaps)
            avg_picks = round(total_picks / len(day_snaps), 1) if day_snaps else 0

            # 活跃策略的选股集中度（Herfindahl 指数的简化版）
            pick_counts = [s["pick_count"] for s in day_snaps if s["pick_count"] > 0]
            if pick_counts and total_picks > 0:
                hhi = sum((p / total_picks) ** 2 for p in pick_counts)
            else:
                hhi = 0

            diversity_history.append({
                "trade_date": td,
                "active_count": active_count,
                "total_strategies": total,
                "diversity_index": index,
                "total_picks": total_picks,
                "avg_picks_per_strategy": avg_picks,
                "concentration_hhi": round(hhi, 4),
            })
            active_counts.append(active_count)

        current = diversity_history[-1] if diversity_history else {}

        # 计算多样性趋势
        if len(active_counts) >= 5:
            recent_avg = sum(active_counts[-5:]) / 5
            older_avg = sum(active_counts[:-5]) / max(1, len(active_counts) - 5) if len(active_counts) > 5 else recent_avg
            if recent_avg > older_avg * 1.1:
                trend = "expanding"
            elif recent_avg < older_avg * 0.9:
                trend = "contracting"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        return {
            "success": True,
            "data": {
                "trade_date": trade_dates[-1] if trade_dates else trade_date,
                "current_index": current.get("diversity_index", 0),
                "active_strategies": current.get("active_count", 0),
                "total_strategies": total,
                "trend": trend,
                "diversity_history": diversity_history,
            },
        }

    # ------------------------------------------------------------------
    # D) 跨策略拥挤相关性
    # ------------------------------------------------------------------

    def get_cross_crowding(self, trade_date: str = None) -> Dict:
        """分析跨策略选股重叠（cross-crowding）。

        当多个策略选中相同的股票时，该股票处于"跨策略拥挤"状态。
        使用 top_picks JSON 找出重叠股票。
        """
        # 只需最新一天的快照
        trade_dates = self._get_trade_dates(1, trade_date)
        if not trade_dates:
            return {
                "success": True,
                "data": {"overlapping_stocks": [], "cross_crowding_score": 0, "pairs": []},
            }

        target_date = trade_dates[-1]
        session = SessionLocal()
        try:
            rows = (
                session.query(StrategySnapshot)
                .filter(StrategySnapshot.trade_date == target_date)
                .all()
            )

            # 构建 strategy → set(ts_code) 映射
            strategy_picks: Dict[str, set] = {}
            strategy_pick_counts: Dict[str, int] = {}
            for row in rows:
                codes = set(self._parse_top_picks(row.top_picks))
                strategy_picks[row.strategy_name] = codes
                strategy_pick_counts[row.strategy_name] = row.pick_count or 0

            # 找出被多个策略选中的股票
            stock_to_strategies: Dict[str, List[str]] = {}
            for strat_name, codes in strategy_picks.items():
                for code in codes:
                    if code not in stock_to_strategies:
                        stock_to_strategies[code] = []
                    stock_to_strategies[code].append(strat_name)

            # 过滤出被 2 个以上策略选中的股票
            overlapping_stocks = []
            for code, strats in stock_to_strategies.items():
                if len(strats) >= 2:
                    overlapping_stocks.append({
                        "ts_code": code,
                        "strategy_count": len(strats),
                        "strategies": strats,
                    })
            overlapping_stocks.sort(key=lambda x: x["strategy_count"], reverse=True)

            # 计算策略对之间的重叠度（Jaccard 系数）
            strategy_list = list(strategy_picks.keys())
            pairs = []
            for i in range(len(strategy_list)):
                for j in range(i + 1, len(strategy_list)):
                    s1, s2 = strategy_list[i], strategy_list[j]
                    set1, set2 = strategy_picks[s1], strategy_picks[s2]
                    if not set1 or not set2:
                        continue
                    intersection = len(set1 & set2)
                    union = len(set1 | set2)
                    if union > 0:
                        jaccard = round(intersection / union, 4)
                        if jaccard > 0:
                            pairs.append({
                                "strategy_a": s1,
                                "strategy_b": s2,
                                "overlap_count": intersection,
                                "jaccard": jaccard,
                            })
            pairs.sort(key=lambda x: x["jaccard"], reverse=True)

            # 跨策略拥挤分数 = 被多策略选中的股票数 / 总策略数
            high_overlap = sum(1 for s in overlapping_stocks if s["strategy_count"] >= 3)
            cross_crowding_score = round(
                high_overlap / max(1, len(strategy_list)) * 100, 1
            )

            return {
                "success": True,
                "data": {
                    "trade_date": target_date,
                    "overlapping_stocks": overlapping_stocks,
                    "overlapping_count": len(overlapping_stocks),
                    "high_overlap_count": high_overlap,
                    "cross_crowding_score": cross_crowding_score,
                    "total_strategies_with_picks": len(strategy_list),
                    "top_pairs": pairs[:20],
                },
            }
        except Exception as exc:
            logger.error("get_cross_crowding failed: %s", exc)
            return {"success": True, "data": {"error": str(exc)}}
        finally:
            session.close()
