"""策略信号告警引擎——执行所有策略并记录信号，检测高置信度告警。"""

import json
import logging
from typing import Dict, Any, List, Optional
from collections import defaultdict

from sqlalchemy import text, func
from ..models import SessionLocal, StrategySignal

logger = logging.getLogger(__name__)


class SignalAlertEngine:
    """策略信号告警引擎：执行策略→记录信号→检测告警。"""

    def __init__(self, loader, cache):
        self.loader = loader
        self.cache = cache

    # ------------------------------------------------------------------
    # public
    # ------------------------------------------------------------------
    def generate_signals(self, trade_date: str) -> Dict[str, Any]:
        """执行所有策略，将每只股票的信号写入 strategy_signal 表。

        Returns:
            {"success": True, "data": {"trade_date": ..., "total_signals": ..., "strategies": ...}}
        """
        from .registry import load_all_strategies, get_all_strategies

        load_all_strategies()
        strategies = get_all_strategies()
        if not strategies:
            return {"success": True, "data": {"trade_date": trade_date, "total_signals": 0, "strategies": 0}}

        # 汇总所有策略所需数据键
        all_keys: set = set()
        for s in strategies.values():
            all_keys.update(s.required_data())
        data = self.loader.load(trade_date, list(all_keys))

        # 去重：先删除该日期的旧信号
        session = SessionLocal()
        try:
            session.execute(
                text("DELETE FROM strategy_signal WHERE trade_date = :td"),
                {"td": trade_date},
            )
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.error("Failed to clear old signals for %s: %s", trade_date, exc)
            return {"success": False, "error": str(exc)}
        finally:
            session.close()

        # 执行每个策略，收集信号
        total_signals = 0
        strategy_stats: Dict[str, int] = {}
        signals_to_insert: List[Dict[str, Any]] = []

        for name, strategy in strategies.items():
            try:
                results = strategy.check(data)
                strategy_stats[name] = len(results)

                for r in results:
                    # 判断信号类型
                    signal_type = "bullish" if r.score >= 60 else ("bearish" if r.score < 30 else "neutral")
                    details_dict = {
                        "reason": r.reason,
                        "signals": {k: v for k, v in (r.signals or {}).items()
                                    if not isinstance(v, (dict, list)) or (isinstance(v, list) and len(v) < 10)},
                    }
                    signals_to_insert.append({
                        "trade_date": trade_date,
                        "ts_code": r.ts_code,
                        "name": r.name,
                        "strategy_name": name,
                        "score": round(r.score, 2),
                        "signal_type": signal_type,
                        "details": json.dumps(details_dict, ensure_ascii=False)[:512],
                    })
                total_signals += len(results)
            except Exception as exc:
                logger.error("Strategy '%s' failed during signal generation: %s", name, exc)
                strategy_stats[name] = 0

        # 批量插入
        if signals_to_insert:
            session = SessionLocal()
            try:
                # 使用 exec_values 批量插入（SQLite 不支持 on_conflict，直接 insert）
                for sig in signals_to_insert:
                    stmt = text(
                        "INSERT INTO strategy_signal "
                        "(trade_date, ts_code, name, strategy_name, score, signal_type, details, created_at) "
                        "VALUES (:trade_date, :ts_code, :name, :strategy_name, :score, :signal_type, :details, datetime('now'))"
                    )
                    session.execute(stmt, sig)
                session.commit()
            except Exception as exc:
                session.rollback()
                logger.error("Failed to insert signals: %s", exc)
                return {"success": False, "error": str(exc)}
            finally:
                session.close()

        return {
            "success": True,
            "data": {
                "trade_date": trade_date,
                "total_signals": total_signals,
                "strategies": len(strategies),
                "strategy_stats": strategy_stats,
            },
        }

    def get_alerts(self, trade_date: str, min_strategies: int = 3) -> Dict[str, Any]:
        """获取被 min_strategies 个以上策略同时选中的股票。

        Returns:
            {"success": True, "data": {"trade_date": ..., "alerts": [...], "total": ...}}
        """
        session = SessionLocal()
        try:
            # 按 stock 聚合：统计策略数 + 总分
            query = text("""
                SELECT trade_date, ts_code, name,
                       COUNT(DISTINCT strategy_name) AS strategy_count,
                       SUM(score) AS total_score,
                       AVG(score) AS avg_score,
                       MAX(score) AS max_score
                FROM strategy_signal
                WHERE trade_date = :td
                GROUP BY trade_date, ts_code, name
                HAVING COUNT(DISTINCT strategy_name) >= :min_s
                ORDER BY strategy_count DESC, total_score DESC
            """)
            rows = session.execute(query, {"td": trade_date, "min_s": min_strategies}).fetchall()

            alerts = []
            for row in rows:
                # 获取该股票的具体策略信号
                detail_query = text("""
                    SELECT strategy_name, score, signal_type, details
                    FROM strategy_signal
                    WHERE trade_date = :td AND ts_code = :code
                    ORDER BY score DESC
                """)
                details = session.execute(detail_query, {"td": trade_date, "code": row.ts_code}).fetchall()
                strategy_details = []
                for d in details:
                    strategy_details.append({
                        "strategy_name": d.strategy_name,
                        "score": d.score,
                        "signal_type": d.signal_type,
                        "details": d.details,
                    })

                alerts.append({
                    "trade_date": row.trade_date,
                    "ts_code": row.ts_code,
                    "name": row.name,
                    "strategy_count": row.strategy_count,
                    "total_score": round(row.total_score, 2),
                    "avg_score": round(row.avg_score, 2),
                    "max_score": round(row.max_score, 2),
                    "strategies": strategy_details,
                })

            return {
                "success": True,
                "data": {
                    "trade_date": trade_date,
                    "min_strategies": min_strategies,
                    "alerts": alerts,
                    "total": len(alerts),
                },
            }
        finally:
            session.close()

    def get_signal_history(self, ts_code: str, days: int = 20) -> Dict[str, Any]:
        """获取某只股票最近 N 天的信号历史。"""
        session = SessionLocal()
        try:
            # 获取最近 N 个不同的交易日
            dates_query = text("""
                SELECT DISTINCT trade_date
                FROM strategy_signal
                WHERE ts_code = :code
                ORDER BY trade_date DESC
                LIMIT :days
            """)
            date_rows = session.execute(dates_query, {"code": ts_code, "days": days}).fetchall()
            if not date_rows:
                return {
                    "success": True,
                    "data": {"ts_code": ts_code, "history": [], "total_days": 0},
                }

            dates = [r.trade_date for r in date_rows]

            history = []
            for d in dates:
                signals_query = text("""
                    SELECT strategy_name, score, signal_type, details
                    FROM strategy_signal
                    WHERE trade_date = :td AND ts_code = :code
                    ORDER BY score DESC
                """)
                sig_rows = session.execute(signals_query, {"td": d, "code": ts_code}).fetchall()

                strategies = []
                for s in sig_rows:
                    strategies.append({
                        "strategy_name": s.strategy_name,
                        "score": s.score,
                        "signal_type": s.signal_type,
                        "details": s.details,
                    })

                history.append({
                    "trade_date": d,
                    "strategy_count": len(strategies),
                    "total_score": round(sum(s.score for s in sig_rows), 2),
                    "strategies": strategies,
                })

            return {
                "success": True,
                "data": {
                    "ts_code": ts_code,
                    "history": history,
                    "total_days": len(history),
                },
            }
        finally:
            session.close()

    def get_alert_summary(self, trade_date: str) -> Dict[str, Any]:
        """获取告警汇总统计。"""
        session = SessionLocal()
        try:
            # 总信号数
            total_q = text("SELECT COUNT(*) FROM strategy_signal WHERE trade_date = :td")
            total_signals = session.execute(total_q, {"td": trade_date}).scalar() or 0

            # 被选中股票数（去重）
            stocks_q = text("SELECT COUNT(DISTINCT ts_code) FROM strategy_signal WHERE trade_date = :td")
            total_stocks = session.execute(stocks_q, {"td": trade_date}).scalar() or 0

            # 策略数量
            strat_q = text("SELECT COUNT(DISTINCT strategy_name) FROM strategy_signal WHERE trade_date = :td")
            total_strategies = session.execute(strat_q, {"td": trade_date}).scalar() or 0

            # 各策略产生信号数
            strat_stats_q = text("""
                SELECT strategy_name, COUNT(*) AS cnt, AVG(score) AS avg_s
                FROM strategy_signal WHERE trade_date = :td
                GROUP BY strategy_name ORDER BY cnt DESC
            """)
            strat_rows = session.execute(strat_stats_q, {"td": trade_date}).fetchall()
            strategy_contribution = [
                {"strategy_name": r.strategy_name, "count": r.cnt, "avg_score": round(r.avg_s, 2)}
                for r in strat_rows
            ]

            # 按策略数分布
            dist_q = text("""
                SELECT strategy_count, COUNT(*) AS stock_count
                FROM (
                    SELECT ts_code, COUNT(DISTINCT strategy_name) AS strategy_count
                    FROM strategy_signal WHERE trade_date = :td
                    GROUP BY ts_code
                ) sub
                GROUP BY strategy_count ORDER BY strategy_count
            """)
            dist_rows = session.execute(dist_q, {"td": trade_date}).fetchall()
            distribution = [
                {"strategy_count": r.strategy_count, "stock_count": r.stock_count}
                for r in dist_rows
            ]

            # 强信号股票（4+ 策略）
            strong_q = text("""
                SELECT COUNT(*) FROM (
                    SELECT ts_code FROM strategy_signal WHERE trade_date = :td
                    GROUP BY ts_code
                    HAVING COUNT(DISTINCT strategy_name) >= 4
                )
            """)
            strong_count = session.execute(strong_q, {"td": trade_date}).scalar() or 0

            # 极强信号（5+ 策略）
            very_strong_q = text("""
                SELECT COUNT(*) FROM (
                    SELECT ts_code FROM strategy_signal WHERE trade_date = :td
                    GROUP BY ts_code
                    HAVING COUNT(DISTINCT strategy_name) >= 5
                )
            """)
            very_strong_count = session.execute(very_strong_q, {"td": trade_date}).scalar() or 0

            # TOP 信号强度股票
            top_q = text("""
                SELECT ts_code, name,
                       COUNT(DISTINCT strategy_name) AS strategy_count,
                       SUM(score) AS total_score
                FROM strategy_signal
                WHERE trade_date = :td
                GROUP BY ts_code, name
                ORDER BY strategy_count DESC, total_score DESC
                LIMIT 10
            """)
            top_rows = session.execute(top_q, {"td": trade_date}).fetchall()
            top_stocks = [
                {"ts_code": r.ts_code, "name": r.name,
                 "strategy_count": r.strategy_count, "total_score": round(r.total_score, 2)}
                for r in top_rows
            ]

            # 信号类型分布
            type_q = text("""
                SELECT signal_type, COUNT(*) AS cnt
                FROM strategy_signal WHERE trade_date = :td
                GROUP BY signal_type
            """)
            type_rows = session.execute(type_q, {"td": trade_date}).fetchall()
            signal_type_dist = {r.signal_type: r.cnt for r in type_rows}

            return {
                "success": True,
                "data": {
                    "trade_date": trade_date,
                    "total_signals": total_signals,
                    "total_stocks": total_stocks,
                    "total_strategies": total_strategies,
                    "strong_alerts": strong_count,
                    "very_strong_alerts": very_strong_count,
                    "strategy_contribution": strategy_contribution,
                    "distribution": distribution,
                    "top_stocks": top_stocks,
                    "signal_type_dist": signal_type_dist,
                },
            }
        finally:
            session.close()
