"""市场宽度指标引擎 — 涨跌分布、市场温度、宽度趋势。"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from sqlalchemy import text

from ..models import SessionLocal

logger = logging.getLogger(__name__)


class MarketBreadthEngine:
    """市场宽度指标引擎。

    核心逻辑：
    1. 从 daily_basic / stk_factor / limit_list 获取全市场个股数据
    2. 计算涨跌分布、涨跌停统计、市场温度等宽度指标
    3. market_temperature 综合评分（0-100），权重：
       - 涨跌比 (30%)
       - 涨停率 (20%)
       - 跌停率 (20%)
       - 均线以上占比 (15%)
       - 换手率分布 (15%)
    """

    def __init__(self):
        pass

    def get_breadth(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """获取市场宽度指标。

        Args:
            trade_date: 交易日期 YYYYMMDD，None 则取最新

        Returns:
            包含 breadth_distribution, limit_stats, market_temperature 的完整结果
        """
        session = SessionLocal()
        try:
            # 获取目标交易日
            if trade_date is None:
                row = session.execute(
                    text("SELECT MAX(trade_date) FROM daily_basic")
                ).fetchone()
                if not row or not row[0]:
                    return {"error": "无可用数据"}
                trade_date = row[0]

            # 并行获取各指标
            breadth_dist = self._get_breadth_distribution(session, trade_date)
            limit_stats = self._get_limit_stats(session, trade_date)
            ma_stats = self._get_ma_breakout_stats(session, trade_date)
            turnover_dist = self._get_turnover_distribution(session, trade_date)
            advance_decline_history = self._get_advance_decline_history(session, trade_date, days=10)

            # 计算市场温度
            temperature = self._calculate_temperature(
                breadth_dist, limit_stats, ma_stats, turnover_dist
            )

            return {
                "trade_date": trade_date,
                "breadth_distribution": breadth_dist,
                "limit_stats": limit_stats,
                "ma_breakout": ma_stats,
                "turnover_distribution": turnover_dist,
                "advance_decline_history": advance_decline_history,
                "market_temperature": temperature,
            }
        except Exception as e:
            logger.error(f"市场宽度分析失败: {e}", exc_info=True)
            return {"error": str(e)}
        finally:
            session.close()

    def _get_breadth_distribution(self, session, trade_date: str) -> Dict[str, Any]:
        """涨跌分布：涨幅区间分组统计。"""
        try:
            rows = session.execute(
                text("""
                    SELECT
                        SUM(CASE WHEN pct_change > 9.5 THEN 1 ELSE 0 END) AS limit_up,
                        SUM(CASE WHEN pct_change > 5 AND pct_change <= 9.5 THEN 1 ELSE 0 END) AS up_5_9,
                        SUM(CASE WHEN pct_change > 3 AND pct_change <= 5 THEN 1 ELSE 0 END) AS up_3_5,
                        SUM(CASE WHEN pct_change > 1 AND pct_change <= 3 THEN 1 ELSE 0 END) AS up_1_3,
                        SUM(CASE WHEN pct_change > 0 AND pct_change <= 1 THEN 1 ELSE 0 END) AS up_0_1,
                        SUM(CASE WHEN pct_change = 0 THEN 1 ELSE 0 END) AS flat,
                        SUM(CASE WHEN pct_change < 0 AND pct_change >= -1 THEN 1 ELSE 0 END) AS down_0_1,
                        SUM(CASE WHEN pct_change < -1 AND pct_change >= -3 THEN 1 ELSE 0 END) AS down_1_3,
                        SUM(CASE WHEN pct_change < -3 AND pct_change >= -5 THEN 1 ELSE 0 END) AS down_3_5,
                        SUM(CASE WHEN pct_change < -5 AND pct_change >= -9.5 THEN 1 ELSE 0 END) AS down_5_9,
                        SUM(CASE WHEN pct_change < -9.5 THEN 1 ELSE 0 END) AS limit_down,
                        SUM(CASE WHEN pct_change > 0 THEN 1 ELSE 0 END) AS advance,
                        SUM(CASE WHEN pct_change < 0 THEN 1 ELSE 0 END) AS decline,
                        SUM(CASE WHEN pct_change = 0 THEN 1 ELSE 0 END) AS unchanged,
                        COUNT(*) AS total
                    FROM stk_factor
                    WHERE trade_date = :td
                """),
                {"td": trade_date},
            ).fetchone()

            if not rows:
                return {"error": "无涨跌数据"}

            # 安全转为 int
            def safe_int(v):
                return int(v) if v else 0

            advance = safe_int(rows[11])
            decline = safe_int(rows[12])
            total = safe_int(rows[14])

            return {
                "distribution": {
                    "limit_up": safe_int(rows[0]),
                    "up_5_9": safe_int(rows[1]),
                    "up_3_5": safe_int(rows[2]),
                    "up_1_3": safe_int(rows[3]),
                    "up_0_1": safe_int(rows[4]),
                    "flat": safe_int(rows[5]),
                    "down_0_1": safe_int(rows[6]),
                    "down_1_3": safe_int(rows[7]),
                    "down_3_5": safe_int(rows[8]),
                    "down_5_9": safe_int(rows[9]),
                    "limit_down": safe_int(rows[10]),
                },
                "advance": advance,
                "decline": decline,
                "unchanged": safe_int(rows[13]),
                "total": total,
                "advance_decline_ratio": round(advance / decline, 2) if decline > 0 else round(advance, 2),
            }
        except Exception as e:
            logger.error(f"涨跌分布查询失败: {e}", exc_info=True)
            return {"error": str(e)}

    def _get_limit_stats(self, session, trade_date: str) -> Dict[str, Any]:
        """涨跌停统计。"""
        try:
            rows = session.execute(
                text("""
                    SELECT
                        SUM(CASE WHEN limit_type = 'U' THEN 1 ELSE 0 END) AS limit_up_count,
                        SUM(CASE WHEN limit_type = 'D' THEN 1 ELSE 0 END) AS limit_down_count,
                        SUM(CASE WHEN limit_type = 'U' AND open_times = 0 THEN 1 ELSE 0 END) AS seal_up,
                        SUM(CASE WHEN limit_type = 'U' AND open_times > 0 THEN 1 ELSE 0 END) AS open_limit_up,
                        SUM(CASE WHEN limit_type = 'U' AND limit_times >= 2 THEN 1 ELSE 0 END) AS consecutive_up
                    FROM limit_list
                    WHERE trade_date = :td
                """),
                {"td": trade_date},
            ).fetchone()

            def safe_int(v):
                return int(v) if v else 0

            limit_up = safe_int(rows[0]) if rows else 0
            limit_down = safe_int(rows[1]) if rows else 0
            seal_up = safe_int(rows[2]) if rows else 0

            return {
                "limit_up_count": limit_up,
                "limit_down_count": limit_down,
                "seal_up_count": seal_up,
                "open_limit_up_count": safe_int(rows[3]) if rows else 0,
                "consecutive_up_count": safe_int(rows[4]) if rows else 0,
                "seal_ratio": round(seal_up / limit_up, 2) if limit_up > 0 else 0,
            }
        except Exception as e:
            logger.error(f"涨跌停统计查询失败: {e}", exc_info=True)
            return {"error": str(e)}

    def _get_ma_breakout_stats(self, session, trade_date: str) -> Dict[str, Any]:
        """均线突破统计：close > boll_mid 的占比。"""
        try:
            rows = session.execute(
                text("""
                    SELECT
                        SUM(CASE WHEN close > boll_mid THEN 1 ELSE 0 END) AS above_boll_mid,
                        COUNT(*) AS total
                    FROM stk_factor
                    WHERE trade_date = :td AND boll_mid IS NOT NULL
                """),
                {"td": trade_date},
            ).fetchone()

            def safe_int(v):
                return int(v) if v else 0

            above = safe_int(rows[0])
            total = safe_int(rows[1])

            return {
                "above_boll_mid": above,
                "total_with_boll": total,
                "above_ratio": round(above / total, 4) if total > 0 else 0,
            }
        except Exception as e:
            logger.error(f"均线突破统计失败: {e}", exc_info=True)
            return {"error": str(e)}

    def _get_turnover_distribution(self, session, trade_date: str) -> Dict[str, Any]:
        """换手率分布。"""
        try:
            rows = session.execute(
                text("""
                    SELECT
                        SUM(CASE WHEN turnover_rate_f > 10 THEN 1 ELSE 0 END) AS high_turnover,
                        SUM(CASE WHEN turnover_rate_f > 5 AND turnover_rate_f <= 10 THEN 1 ELSE 0 END) AS mid_turnover,
                        SUM(CASE WHEN turnover_rate_f > 2 AND turnover_rate_f <= 5 THEN 1 ELSE 0 END) AS normal_turnover,
                        SUM(CASE WHEN turnover_rate_f <= 2 THEN 1 ELSE 0 END) AS low_turnover,
                        AVG(turnover_rate_f) AS avg_turnover,
                        COUNT(*) AS total
                    FROM daily_basic
                    WHERE trade_date = :td AND turnover_rate_f IS NOT NULL
                """),
                {"td": trade_date},
            ).fetchone()

            def safe_int(v):
                return int(v) if v else 0

            def safe_float(v):
                return round(float(v), 2) if v else 0

            return {
                "high_turnover": safe_int(rows[0]),
                "mid_turnover": safe_int(rows[1]),
                "normal_turnover": safe_int(rows[2]),
                "low_turnover": safe_int(rows[3]),
                "avg_turnover_rate": safe_float(rows[4]),
                "total": safe_int(rows[5]),
            }
        except Exception as e:
            logger.error(f"换手率分布查询失败: {e}", exc_info=True)
            return {"error": str(e)}

    def _get_advance_decline_history(self, session, trade_date: str, days: int = 10) -> List[Dict]:
        """近 N 日涨跌家数历史。"""
        try:
            rows = session.execute(
                text("""
                    SELECT
                        trade_date,
                        SUM(CASE WHEN pct_change > 0 THEN 1 ELSE 0 END) AS advance,
                        SUM(CASE WHEN pct_change < 0 THEN 1 ELSE 0 END) AS decline,
                        SUM(CASE WHEN pct_change = 0 THEN 1 ELSE 0 END) AS unchanged
                    FROM stk_factor
                    WHERE trade_date <= :td
                    GROUP BY trade_date
                    ORDER BY trade_date DESC
                    LIMIT :days
                """),
                {"td": trade_date, "days": days},
            ).fetchall()

            result = []
            for r in reversed(rows):
                result.append({
                    "trade_date": r[0],
                    "advance": int(r[1]) if r[1] else 0,
                    "decline": int(r[2]) if r[2] else 0,
                    "unchanged": int(r[3]) if r[3] else 0,
                })
            return result
        except Exception as e:
            logger.error(f"涨跌历史查询失败: {e}", exc_info=True)
            return []

    def _calculate_temperature(
        self,
        breadth_dist: Dict,
        limit_stats: Dict,
        ma_stats: Dict,
        turnover_dist: Dict,
    ) -> Dict[str, Any]:
        """计算市场温度（0-100）。

        权重：
        - 涨跌比 30%
        - 涨停率 20%
        - 跌停率 20%
        - 均线以上占比 15%
        - 换手率分布 15%
        """
        try:
            # 1. 涨跌比分 (0-100)
            adr = breadth_dist.get("advance_decline_ratio", 1.0)
            # ADR 1.0 = 50分, ADR 2.0+ = 80分, ADR 0.5 = 20分
            if adr >= 2.0:
                score_adr = 80 + min((adr - 2.0) * 10, 20)
            elif adr >= 1.0:
                score_adr = 50 + (adr - 1.0) * 30
            else:
                score_adr = max(adr * 50, 0)
            score_adr = min(max(score_adr, 0), 100)

            # 2. 涨停率分 (0-100)
            total = breadth_dist.get("total", 1) or 1
            limit_up = limit_stats.get("limit_up_count", 0)
            limit_up_ratio = limit_up / total
            # 涨停率 3%+ = 80分，1% = 50分，0% = 10分
            score_limit_up = min(10 + limit_up_ratio * 2500, 100)
            score_limit_up = min(max(score_limit_up, 0), 100)

            # 3. 跌停率分 (0-100, 跊停越少分越高)
            limit_down = limit_stats.get("limit_down_count", 0)
            limit_down_ratio = limit_down / total
            # 跌停率 0% = 90分，3%+ = 10分
            score_limit_down = max(90 - limit_down_ratio * 2700, 0)
            score_limit_down = min(max(score_limit_down, 0), 100)

            # 4. 均线以上占比分 (0-100)
            above_ratio = ma_stats.get("above_ratio", 0.5)
            score_ma = above_ratio * 100
            score_ma = min(max(score_ma, 0), 100)

            # 5. 换手率分布分 (0-100)
            avg_turnover = turnover_dist.get("avg_turnover_rate", 3.0)
            high_turnover = turnover_dist.get("high_turnover", 0)
            low_turnover = turnover_dist.get("low_turnover", 0)
            # 适度换手率活跃度加分，过高过低减分
            # 平均换手率 3-8% = 最佳
            if 3 <= avg_turnover <= 8:
                score_turnover = 70 + (avg_turnover - 3) * 6
            elif avg_turnover > 8:
                score_turnover = max(100 - (avg_turnover - 8) * 5, 30)
            else:
                score_turnover = max(avg_turnover * 20, 10)
            score_turnover = min(max(score_turnover, 0), 100)

            # 加权合成
            temperature = (
                score_adr * 0.30
                + score_limit_up * 0.20
                + score_limit_down * 0.20
                + score_ma * 0.15
                + score_turnover * 0.15
            )
            temperature = round(min(max(temperature, 0), 100), 1)

            # 冷热判断
            if temperature >= 80:
                label = "极度贪婪"
            elif temperature >= 65:
                label = "贪婪"
            elif temperature >= 45:
                label = "中性"
            elif temperature >= 30:
                label = "恐惧"
            else:
                label = "极度恐惧"

            return {
                "temperature": temperature,
                "label": label,
                "components": {
                    "advance_decline": {"score": round(score_adr, 1), "weight": 0.30},
                    "limit_up_rate": {"score": round(score_limit_up, 1), "weight": 0.20},
                    "limit_down_rate": {"score": round(score_limit_down, 1), "weight": 0.20},
                    "ma_breakout": {"score": round(score_ma, 1), "weight": 0.15},
                    "turnover_activity": {"score": round(score_turnover, 1), "weight": 0.15},
                },
            }
        except Exception as e:
            logger.error(f"市场温度计算失败: {e}", exc_info=True)
            return {"temperature": 50, "label": "中性", "error": str(e)}

    def get_temperature_history(self, days: int = 30) -> List[Dict]:
        """获取近 N 日市场温度历史。

        使用批量查询（3 次 SQL）代替逐日查询（4×N 次 SQL），
        将数据库往返次数从 O(N) 降低到 O(1)。
        """
        session = SessionLocal()
        try:
            # 获取最近 N 个交易日
            dates_row = session.execute(
                text("""
                    SELECT DISTINCT trade_date FROM stk_factor
                    ORDER BY trade_date DESC
                    LIMIT :days
                """),
                {"days": days},
            ).fetchall()
            dates = [r[0] for r in dates_row]

            if not dates:
                return []

            # 一次性批量获取所有日期的数据（3 次 SQL）
            all_data = self._get_all_history_data(session, dates)

            history = []
            for td in reversed(dates):
                data = all_data.get(td, {})
                bd = data.get("breadth", {"error": "无涨跌数据"})
                ls = data.get("limits", {})
                ms = data.get("ma_breakout", {})
                td2 = data.get("turnover", {})
                temp = self._calculate_temperature(bd, ls, ms, td2)
                history.append({
                    "trade_date": td,
                    "temperature": temp.get("temperature", 50),
                    "label": temp.get("label", "中性"),
                })
            return history
        except Exception as e:
            logger.error(f"温度历史查询失败: {e}", exc_info=True)
            return []
        finally:
            session.close()

    def _get_all_history_data(self, session, dates: list) -> dict:
        """批量获取温度历史所需的所有原始数据（3 次 SQL 查询）。

        将 stk_factor（涨跌分布 + 布林带突破）、limit_list（涨跌停统计）、
        daily_basic（换手率分布）三张表的数据按 trade_date 分组聚合，
        代替原来对每个交易日分别执行 4 次查询。

        Returns:
            {trade_date: {"breadth": {...}, "limits": {...},
                          "ma_breakout": {...}, "turnover": {...}}}
        """
        if not dates:
            return {}

        placeholders = ", ".join([f":d{i}" for i in range(len(dates))])
        params = {f"d{i}": d for i, d in enumerate(dates)}

        def safe_int(v):
            return int(v) if v else 0

        def safe_float(v):
            return round(float(v), 2) if v else 0

        result = {d: {} for d in dates}

        # ── Query 1: stk_factor — 涨跌分布 + 布林带突破（合并为 1 次） ──
        sf_rows = session.execute(
            text(f"""
                SELECT
                    trade_date,
                    SUM(CASE WHEN pct_change > 9.5 THEN 1 ELSE 0 END) AS limit_up,
                    SUM(CASE WHEN pct_change > 5 AND pct_change <= 9.5 THEN 1 ELSE 0 END) AS up_5_9,
                    SUM(CASE WHEN pct_change > 3 AND pct_change <= 5 THEN 1 ELSE 0 END) AS up_3_5,
                    SUM(CASE WHEN pct_change > 1 AND pct_change <= 3 THEN 1 ELSE 0 END) AS up_1_3,
                    SUM(CASE WHEN pct_change > 0 AND pct_change <= 1 THEN 1 ELSE 0 END) AS up_0_1,
                    SUM(CASE WHEN pct_change = 0 THEN 1 ELSE 0 END) AS flat,
                    SUM(CASE WHEN pct_change < 0 AND pct_change >= -1 THEN 1 ELSE 0 END) AS down_0_1,
                    SUM(CASE WHEN pct_change < -1 AND pct_change >= -3 THEN 1 ELSE 0 END) AS down_1_3,
                    SUM(CASE WHEN pct_change < -3 AND pct_change >= -5 THEN 1 ELSE 0 END) AS down_3_5,
                    SUM(CASE WHEN pct_change < -5 AND pct_change >= -9.5 THEN 1 ELSE 0 END) AS down_5_9,
                    SUM(CASE WHEN pct_change < -9.5 THEN 1 ELSE 0 END) AS limit_down,
                    SUM(CASE WHEN pct_change > 0 THEN 1 ELSE 0 END) AS advance,
                    SUM(CASE WHEN pct_change < 0 THEN 1 ELSE 0 END) AS decline,
                    COUNT(*) AS total,
                    SUM(CASE WHEN close > boll_mid AND boll_mid IS NOT NULL THEN 1 ELSE 0 END) AS above_boll_mid,
                    SUM(CASE WHEN boll_mid IS NOT NULL THEN 1 ELSE 0 END) AS total_with_boll
                FROM stk_factor
                WHERE trade_date IN ({placeholders})
                GROUP BY trade_date
            """),
            params,
        ).fetchall()

        for r in sf_rows:
            td = r[0]
            advance = safe_int(r[12])
            decline = safe_int(r[13])
            total = safe_int(r[14])
            above = safe_int(r[15])
            total_boll = safe_int(r[16])
            result[td]["breadth"] = {
                "distribution": {
                    "limit_up": safe_int(r[1]),
                    "up_5_9": safe_int(r[2]),
                    "up_3_5": safe_int(r[3]),
                    "up_1_3": safe_int(r[4]),
                    "up_0_1": safe_int(r[5]),
                    "flat": safe_int(r[6]),
                    "down_0_1": safe_int(r[7]),
                    "down_1_3": safe_int(r[8]),
                    "down_3_5": safe_int(r[9]),
                    "down_5_9": safe_int(r[10]),
                    "limit_down": safe_int(r[11]),
                },
                "advance": advance,
                "decline": decline,
                "unchanged": safe_int(r[6]),
                "total": total,
                "advance_decline_ratio": round(advance / decline, 2) if decline > 0 else round(advance, 2),
            }
            result[td]["ma_breakout"] = {
                "above_boll_mid": above,
                "total_with_boll": total_boll,
                "above_ratio": round(above / total_boll, 4) if total_boll > 0 else 0,
            }

        # ── Query 2: limit_list — 涨跌停统计 ──
        ll_rows = session.execute(
            text(f"""
                SELECT
                    trade_date,
                    SUM(CASE WHEN limit_type = 'U' THEN 1 ELSE 0 END) AS limit_up_count,
                    SUM(CASE WHEN limit_type = 'D' THEN 1 ELSE 0 END) AS limit_down_count,
                    SUM(CASE WHEN limit_type = 'U' AND open_times = 0 THEN 1 ELSE 0 END) AS seal_up,
                    SUM(CASE WHEN limit_type = 'U' AND open_times > 0 THEN 1 ELSE 0 END) AS open_limit_up,
                    SUM(CASE WHEN limit_type = 'U' AND limit_times >= 2 THEN 1 ELSE 0 END) AS consecutive_up
                FROM limit_list
                WHERE trade_date IN ({placeholders})
                GROUP BY trade_date
            """),
            params,
        ).fetchall()

        for r in ll_rows:
            td = r[0]
            limit_up = safe_int(r[1])
            seal_up = safe_int(r[3])
            result[td]["limits"] = {
                "limit_up_count": limit_up,
                "limit_down_count": safe_int(r[2]),
                "seal_up_count": seal_up,
                "open_limit_up_count": safe_int(r[4]),
                "consecutive_up_count": safe_int(r[5]),
                "seal_ratio": round(seal_up / limit_up, 2) if limit_up > 0 else 0,
            }

        # ── Query 3: daily_basic — 换手率分布 ──
        db_rows = session.execute(
            text(f"""
                SELECT
                    trade_date,
                    SUM(CASE WHEN turnover_rate_f > 10 THEN 1 ELSE 0 END) AS high_turnover,
                    SUM(CASE WHEN turnover_rate_f > 5 AND turnover_rate_f <= 10 THEN 1 ELSE 0 END) AS mid_turnover,
                    SUM(CASE WHEN turnover_rate_f > 2 AND turnover_rate_f <= 5 THEN 1 ELSE 0 END) AS normal_turnover,
                    SUM(CASE WHEN turnover_rate_f <= 2 THEN 1 ELSE 0 END) AS low_turnover,
                    AVG(turnover_rate_f) AS avg_turnover,
                    COUNT(*) AS total
                FROM daily_basic
                WHERE trade_date IN ({placeholders}) AND turnover_rate_f IS NOT NULL
                GROUP BY trade_date
            """),
            params,
        ).fetchall()

        for r in db_rows:
            td = r[0]
            result[td]["turnover"] = {
                "high_turnover": safe_int(r[1]),
                "mid_turnover": safe_int(r[2]),
                "normal_turnover": safe_int(r[3]),
                "low_turnover": safe_int(r[4]),
                "avg_turnover_rate": safe_float(r[5]),
                "total": safe_int(r[6]),
            }

        return result
