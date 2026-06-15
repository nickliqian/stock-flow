"""策略智能分析——追踪策略表现、计算置信度、推荐最佳策略。"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from sqlalchemy import text

from ..models import StrategySnapshot, StrategyPerformance, DailyPrice
from ..cache import CacheService
from ..engine.registry import get_all_strategies

logger = logging.getLogger(__name__)


class StrategyIntelligenceService:
    """策略智能分析服务。"""

    def __init__(self, loader=None):
        self.loader = loader

    # ------------------------------------------------------------------
    # Snapshot recording
    # ------------------------------------------------------------------
    def record_snapshot(self, trade_date: str, strategy_name: str, results: list, avg_score: float = 0, max_score: float = 0):
        """记录策略执行快照。"""
        cache = CacheService()
        with cache._session() as session:
            try:
                # Check if snapshot already exists
                existing = session.query(StrategySnapshot).filter_by(
                    trade_date=trade_date, strategy_name=strategy_name
                ).first()

                top_picks = json.dumps(
                    [{"ts_code": r.ts_code, "name": r.name, "score": round(r.score, 2), "reason": r.reason}
                     for r in results[:10]],
                    ensure_ascii=False
                )

                if existing:
                    existing.pick_count = len(results)
                    existing.top_picks = top_picks
                    existing.avg_score = round(avg_score, 2)
                    existing.max_score = round(max_score, 2)
                else:
                    snapshot = StrategySnapshot(
                        trade_date=trade_date,
                        strategy_name=strategy_name,
                        pick_count=len(results),
                        top_picks=top_picks,
                        avg_score=round(avg_score, 2),
                        max_score=round(max_score, 2),
                    )
                    session.add(snapshot)

                session.commit()
            except Exception as exc:
                session.rollback()
                logger.error("record_snapshot failed: %s", exc)

    def record_performance(self, trade_date: str, strategy_name: str, results: list):
        """记录策略推荐股票的后续表现（需要 daily_price 数据）。"""
        cache = CacheService()
        with cache._session() as session:
            try:
                # Get the list of trade dates after the recommendation date
                all_dates = session.query(DailyPrice.trade_date).filter(
                    DailyPrice.trade_date > trade_date
                ).distinct().order_by(DailyPrice.trade_date).all()
                all_dates = [d[0] for d in all_dates]

                if not all_dates:
                    return  # No future data available yet

                date_1d = all_dates[0] if len(all_dates) >= 1 else None
                date_3d = all_dates[2] if len(all_dates) >= 3 else None
                date_5d = all_dates[4] if len(all_dates) >= 5 else None

                top30 = results[:30]
                ts_codes = [r.ts_code for r in top30]

                # Batch query: all entry prices at once
                entry_rows = session.query(DailyPrice.ts_code, DailyPrice.close).filter(
                    DailyPrice.trade_date == trade_date,
                    DailyPrice.ts_code.in_(ts_codes),
                ).all()
                entry_map = {row.ts_code: row.close for row in entry_rows}

                # Batch query: all future prices at once
                future_dates = [d for d in [date_1d, date_3d, date_5d] if d is not None]
                future_prices = {}
                if future_dates:
                    price_rows = session.query(
                        DailyPrice.ts_code, DailyPrice.trade_date, DailyPrice.close
                    ).filter(
                        DailyPrice.trade_date.in_(future_dates),
                        DailyPrice.ts_code.in_(ts_codes),
                    ).all()
                    for row in price_rows:
                        future_prices.setdefault(row.ts_code, {})[row.trade_date] = row.close

                for r in top30:
                    entry_price = entry_map.get(r.ts_code)
                    if entry_price is None or entry_price == 0:
                        continue

                    # Calculate returns from pre-fetched data
                    stock_prices = future_prices.get(r.ts_code, {})
                    ret_1d = self._calc_return_from_map(entry_price, stock_prices, date_1d)
                    ret_3d = self._calc_return_from_map(entry_price, stock_prices, date_3d)
                    ret_5d = self._calc_return_from_map(entry_price, stock_prices, date_5d)

                    # Upsert performance record using INSERT OR REPLACE to
                    # handle the UniqueConstraint on (trade_date, strategy_name, ts_code).
                    session.execute(
                        text(
                            "INSERT OR REPLACE INTO strategy_performance "
                            "(trade_date, strategy_name, ts_code, name, "
                            " entry_score, entry_price, ret_1d, ret_3d, ret_5d) "
                            "VALUES (:trade_date, :strategy_name, :ts_code, :name, "
                            "        :entry_score, :entry_price, :ret_1d, :ret_3d, :ret_5d)"
                        ),
                        {
                            "trade_date": trade_date,
                            "strategy_name": strategy_name,
                            "ts_code": r.ts_code,
                            "name": r.name,
                            "entry_score": r.score,
                            "entry_price": entry_price,
                            "ret_1d": ret_1d,
                            "ret_3d": ret_3d,
                            "ret_5d": ret_5d,
                        },
                    )

                session.commit()
            except Exception as exc:
                session.rollback()
                logger.error("record_performance failed: %s", exc)

    def _calc_return_from_map(self, entry_price: float, prices: dict, target_date: str) -> Optional[float]:
        """从预加载的价格映射计算收益率（避免逐条查询）。"""
        if not target_date:
            return None
        close = prices.get(target_date)
        if close is None or close == 0:
            return None
        return round((close - entry_price) / entry_price * 100, 2)

    # ------------------------------------------------------------------
    # Intelligence queries
    # ------------------------------------------------------------------
    def get_strategy_health(self, lookback_days: int = 20) -> List[Dict]:
        """获取所有策略的健康度概览。"""
        cache = CacheService()
        with cache._session() as session:
            strategies = get_all_strategies()
            result = []

            # Get recent trade dates
            dates = session.query(StrategySnapshot.trade_date).distinct().order_by(
                StrategySnapshot.trade_date.desc()
            ).limit(lookback_days).all()
            dates = [d[0] for d in dates]

            if not dates:
                return [{"name": s.name, "description": s.description, "category": s.category, 
                         "icon": s.icon, "health_score": 0, "recent_picks": 0, "data_available": False}
                        for s in strategies.values()]

            for s in strategies.values():
                # Recent snapshots
                snapshots = session.query(StrategySnapshot).filter(
                    StrategySnapshot.strategy_name == s.name,
                    StrategySnapshot.trade_date.in_(dates)
                ).order_by(StrategySnapshot.trade_date.desc()).all()

                recent_picks = sum(sp.pick_count for sp in snapshots)
                avg_picks = recent_picks / max(len(snapshots), 1)

                # Performance stats
                perf_stats = self._get_perf_stats(session, s.name, dates)

                # Health score: combination of consistency and performance
                consistency = min(len(snapshots) / max(lookback_days, 1), 1.0)
                win_rate = perf_stats.get("win_rate_1d", 0)
                health_score = round((consistency * 40 + win_rate * 40 + min(avg_picks / 10, 1) * 20), 1)

                result.append({
                    "name": s.name,
                    "description": s.description,
                    "category": s.category,
                    "icon": s.icon,
                    "health_score": health_score,
                    "recent_picks": recent_picks,
                    "avg_picks_per_day": round(avg_picks, 1),
                    "snapshot_count": len(snapshots),
                    "last_active": snapshots[0].trade_date if snapshots else None,
                    **perf_stats,
                    "data_available": len(snapshots) > 0,
                })

            result.sort(key=lambda x: x["health_score"], reverse=True)
            return result

    def _get_perf_stats(self, session, strategy_name: str, dates: list) -> Dict:
        """计算策略的绩效统计。"""
        perfs = session.query(StrategyPerformance).filter(
            StrategyPerformance.strategy_name == strategy_name,
            StrategyPerformance.trade_date.in_(dates)
        ).all()

        if not perfs:
            return {"win_rate_1d": 0, "win_rate_3d": 0, "win_rate_5d": 0,
                    "avg_ret_1d": 0, "avg_ret_3d": 0, "avg_ret_5d": 0,
                    "total_tracked": 0}

        def calc_win_rate(vals):
            valid = [v for v in vals if v is not None]
            if not valid:
                return 0
            return round(sum(1 for v in valid if v > 0) / len(valid) * 100, 1)

        def calc_avg(vals):
            valid = [v for v in vals if v is not None]
            if not valid:
                return 0
            return round(sum(valid) / len(valid), 2)

        r1d = [p.ret_1d for p in perfs]
        r3d = [p.ret_3d for p in perfs]
        r5d = [p.ret_5d for p in perfs]

        return {
            "win_rate_1d": calc_win_rate(r1d),
            "win_rate_3d": calc_win_rate(r3d),
            "win_rate_5d": calc_win_rate(r5d),
            "avg_ret_1d": calc_avg(r1d),
            "avg_ret_3d": calc_avg(r3d),
            "avg_ret_5d": calc_avg(r5d),
            "total_tracked": len(perfs),
        }

    def get_performance_trend(self, strategy_name: str, days: int = 30) -> Dict:
        """获取策略胜率趋势数据（用于折线图）。"""
        cache = CacheService()
        with cache._session() as session:
            # Get snapshots for this strategy
            snapshots = session.query(StrategySnapshot).filter(
                StrategySnapshot.strategy_name == strategy_name
            ).order_by(StrategySnapshot.trade_date.desc()).limit(days).all()

            trend = []
            for sp in reversed(snapshots):  # chronological order
                # Get performance for this date
                perfs = session.query(StrategyPerformance).filter_by(
                    trade_date=sp.trade_date, strategy_name=strategy_name
                ).all()

                r1d = [p.ret_1d for p in perfs if p.ret_1d is not None]
                win_rate = round(sum(1 for v in r1d if v > 0) / len(r1d) * 100, 1) if r1d else 0
                avg_ret = round(sum(r1d) / len(r1d), 2) if r1d else 0

                trend.append({
                    "trade_date": sp.trade_date,
                    "pick_count": sp.pick_count,
                    "avg_score": sp.avg_score,
                    "win_rate_1d": win_rate,
                    "avg_return_1d": avg_ret,
                    "tracked_count": len(r1d),
                })

            return {"strategy_name": strategy_name, "trend": trend}

    def compare_strategies(self, strategy_names: list, days: int = 20) -> Dict:
        """对比多个策略的表现。"""
        cache = CacheService()
        with cache._session() as session:
            result = []
            for name in strategy_names:
                strategy = get_all_strategies().get(name)
                if not strategy:
                    continue

                dates = session.query(StrategySnapshot.trade_date).filter(
                    StrategySnapshot.strategy_name == name
                ).distinct().order_by(StrategySnapshot.trade_date.desc()).limit(days).all()
                dates = [d[0] for d in dates]

                stats = self._get_perf_stats(session, name, dates)
                snapshots = session.query(StrategySnapshot).filter(
                    StrategySnapshot.strategy_name == name,
                    StrategySnapshot.trade_date.in_(dates)
                ).all()

                result.append({
                    "name": strategy.name,
                    "description": strategy.description,
                    "category": strategy.category,
                    "icon": strategy.icon,
                    "snapshot_count": len(snapshots),
                    "avg_picks_per_day": round(sum(s.pick_count for s in snapshots) / max(len(snapshots), 1), 1),
                    **stats,
                })

            return {"strategies": result, "lookback_days": days}

    def get_recommendation(self) -> Dict:
        """基于历史表现推荐当前最值得信赖的策略。"""
        health = self.get_strategy_health(lookback_days=15)
        
        # Filter strategies with data
        active = [h for h in health if h.get("data_available") and h.get("snapshot_count", 0) >= 3]
        
        if not active:
            return {
                "recommendation": None,
                "message": "尚无足够的策略表现数据，建议先执行所有策略积累数据。",
                "strategies": health[:5],
            }

        # Score: health_score * 0.4 + win_rate_1d * 0.3 + avg_ret_1d * 0.3
        for s in active:
            s["trust_score"] = round(
                s["health_score"] * 0.4 + 
                s.get("win_rate_1d", 0) * 0.3 + 
                max(min(s.get("avg_ret_1d", 0) * 10, 100), 0) * 0.3,
                1
            )
        
        active.sort(key=lambda x: x["trust_score"], reverse=True)
        best = active[0]

        return {
            "recommendation": {
                "strategy": best["name"],
                "description": best["description"],
                "icon": best["icon"],
                "trust_score": best["trust_score"],
                "win_rate_1d": best.get("win_rate_1d", 0),
                "avg_ret_1d": best.get("avg_ret_1d", 0),
                "reason": f"近{best.get('snapshot_count', 0)}个交易日平均每日选{best.get('avg_picks_per_day', 0)}只，1日胜率{best.get('win_rate_1d', 0)}%",
            },
            "top_5": active[:5],
            "all_health": health,
        }
