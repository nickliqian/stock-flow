"""行业轮动与资金流向智能引擎——检测行业级别的资金流转和轮动信号。

核心逻辑：
1. 从 moneyflow_dc 汇总各行业每日净流入
2. 对比近半段 vs 远半段资金流向，计算轮动得分
3. 生成 ROTATION_IN / ROTATION_OUT / ACCELERATION / DECELERATION / NEUTRAL 信号
"""

import logging
from typing import Dict, Any, List, Optional
from collections import defaultdict

from sqlalchemy import text

from ..models import SessionLocal

logger = logging.getLogger(__name__)


class IndustryRotationEngine:
    """行业轮动与资金流向智能引擎。

    核心逻辑：
    1. 从 moneyflow_dc 获取个股净流入，按 stock_basic 的 industry 字段分组聚合
    2. 计算 N 日滚动行业净流入，拆分为近期段 vs 远期段
    3. rotation_score = (近期净流入 - 远期净流入) / max(abs(远期净流入), 1)
    4. 根据 rotation_score 阈值生成轮动信号
    """

    # 信号阈值
    THRESHOLD_ROTATION_IN = 0.3
    THRESHOLD_ACCELERATION = 0.8
    THRESHOLD_ROTATION_OUT = -0.3
    THRESHOLD_DECELERATION = -0.8
    MIN_STOCKS_PER_INDUSTRY = 3

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------
    def get_industry_flow_summary(
        self, trade_date: Optional[str] = None, lookback_days: int = 10
    ) -> Dict[str, Any]:
        """获取行业资金流向汇总——聚合各行业在 lookback 天内的净流入趋势。

        Args:
            trade_date: 交易日期 YYYYMMDD，None 则取最新
            lookback_days: 回看天数（拆分为近半段和远半段）

        Returns:
            {
                "trade_date": "20250613",
                "lookback_days": 10,
                "summary": { "total_industries": N, "rotation_in": N, ... },
                "industries": [ { "industry": "银行", "stock_count": N,
                    "recent_flow": ..., "older_flow": ..., "rotation_score": ...,
                    "signal": "ROTATION_IN", "daily_flow": [...] }, ... ]
            }
        """
        session = SessionLocal()
        try:
            if trade_date is None:
                trade_date = self._get_latest_trade_date(session)
                if not trade_date:
                    return {"success": False, "error": "无可用数据"}

            # 获取回看交易日列表
            trade_dates = self._get_trade_dates(session, trade_date, lookback_days)
            if len(trade_dates) < 2:
                return {
                    "success": True,
                    "data": {
                        "trade_date": trade_date,
                        "lookback_days": lookback_days,
                        "summary": {
                            "total_industries": 0,
                            "rotation_in": 0,
                            "acceleration": 0,
                            "rotation_out": 0,
                            "deceleration": 0,
                            "neutral": 0,
                        },
                        "industries": [],
                    },
                }

            # 获取行业名称映射
            industry_map = self._get_industry_map(session)

            # 查询回看区间内的资金流向
            flow_rows = self._query_industry_flow(session, trade_dates)

            # 按行业按日聚合
            industry_daily = self._aggregate_by_industry(flow_rows, industry_map)

            # 拆分近期 vs 远期并计算轮动得分
            half = max(len(trade_dates) // 2, 1)
            recent_dates = set(trade_dates[half:])
            older_dates = set(trade_dates[:half])

            industries = []
            for industry, daily_map in industry_daily.items():
                stock_count = self._count_unique_stocks(flow_rows, industry, industry_map)
                if stock_count < self.MIN_STOCKS_PER_INDUSTRY:
                    continue

                recent_flow = sum(daily_map.get(d, 0) for d in recent_dates)
                older_flow = sum(daily_map.get(d, 0) for d in older_dates)
                rotation_score = self._calc_rotation_score(recent_flow, older_flow)

                # 近期日均流
                recent_avg = recent_flow / max(len(recent_dates), 1)
                older_avg = older_flow / max(len(older_dates), 1)
                signal = self._classify_signal(rotation_score)

                # 按日列出
                daily_flow = [
                    {"trade_date": d, "net_amount": round(daily_map.get(d, 0), 2)}
                    for d in sorted(trade_dates)
                    if d in daily_map
                ]

                industries.append({
                    "industry": industry,
                    "stock_count": stock_count,
                    "recent_flow": round(recent_flow, 2),
                    "older_flow": round(older_flow, 2),
                    "recent_avg": round(recent_avg, 2),
                    "older_avg": round(older_avg, 2),
                    "rotation_score": round(rotation_score, 4),
                    "signal": signal,
                    "daily_flow": daily_flow,
                })

            # 按 rotation_score 降序
            industries.sort(key=lambda x: x["rotation_score"], reverse=True)

            # 汇总统计
            summary = {
                "total_industries": len(industries),
                "rotation_in": sum(1 for i in industries if i["signal"] == "ROTATION_IN"),
                "acceleration": sum(1 for i in industries if i["signal"] == "ACCELERATION"),
                "rotation_out": sum(1 for i in industries if i["signal"] == "ROTATION_OUT"),
                "deceleration": sum(1 for i in industries if i["signal"] == "DECELERATION"),
                "neutral": sum(1 for i in industries if i["signal"] == "NEUTRAL"),
            }

            return {
                "success": True,
                "data": {
                    "trade_date": trade_date,
                    "lookback_days": lookback_days,
                    "summary": summary,
                    "industries": industries,
                },
            }
        except Exception as exc:
            logger.error("get_industry_flow_summary failed: %s", exc)
            return {"success": False, "error": str(exc)}
        finally:
            session.close()

    def get_rotation_signals(
        self, trade_date: Optional[str] = None, lookback_days: int = 10
    ) -> Dict[str, Any]:
        """检测行业轮动信号——仅返回有明确信号的行业。

        信号类型：
        - ROTATION_IN: score > 0.3 （资金正在流入）
        - ACCELERATION: score > 0.8 （加速流入）
        - ROTATION_OUT: score < -0.3 （资金正在流出）
        - DECELERATION: score < -0.8 （加速流出）
        - NEUTRAL: 其他

        Returns:
            {
                "trade_date": "...",
                "signals": [
                    { "industry": "银行", "signal": "ROTATION_IN",
                      "rotation_score": 0.45, ... }, ...
                ],
                "summary": { ... }
            }
        """
        try:
            result = self.get_industry_flow_summary(trade_date, lookback_days)
            if not result.get("success"):
                return result

            data = result["data"]
            all_industries = data.get("industries", [])

            # 过滤：仅保留非 NEUTRAL 信号
            signals = [ind for ind in all_industries if ind["signal"] != "NEUTRAL"]

            summary = {
                "total_industries": data["summary"]["total_industries"],
                "signaling": len(signals),
                "rotation_in": data["summary"]["rotation_in"],
                "acceleration": data["summary"]["acceleration"],
                "rotation_out": data["summary"]["rotation_out"],
                "deceleration": data["summary"]["deceleration"],
            }

            return {
                "success": True,
                "data": {
                    "trade_date": data["trade_date"],
                    "lookback_days": lookback_days,
                    "summary": summary,
                    "signals": signals,
                },
            }
        except Exception as exc:
            logger.error("get_rotation_signals failed: %s", exc)
            return {"success": False, "error": str(exc)}

    def get_industry_detail(
        self, trade_date: Optional[str] = None, industry: str = ""
    ) -> Dict[str, Any]:
        """获取单个行业的详细视图——包括个股资金流向和基本面指标。

        Returns:
            {
                "industry": "银行",
                "trade_date": "...",
                "summary": { "stock_count": N, "total_net_flow": ..., ... },
                "stocks": [ { "ts_code": "600036.SH", "name": "招商银行",
                    "net_amount": ..., "pe_ttm": ..., "pb": ..., ... }, ... ]
            }
        """
        session = SessionLocal()
        try:
            if not industry:
                return {"success": False, "error": "行业名称不能为空"}

            if trade_date is None:
                trade_date = self._get_latest_trade_date(session)
                if not trade_date:
                    return {"success": False, "error": "无可用数据"}

            # 1) 获取该行业的所有股票
            stock_rows = session.execute(
                text("""
                    SELECT ts_code, name
                    FROM stock_basic
                    WHERE industry = :industry
                """),
                {"industry": industry},
            ).fetchall()

            if not stock_rows:
                return {
                    "success": True,
                    "data": {
                        "industry": industry,
                        "trade_date": trade_date,
                        "summary": {"stock_count": 0},
                        "stocks": [],
                    },
                }

            ts_codes = [r[0] for r in stock_rows]
            name_map = {r[0]: r[1] for r in stock_rows}

            # 2) 查询当日资金流向
            placeholders = ", ".join([f":tc{i}" for i in range(len(ts_codes))])
            mf_params = {f"tc{i}": tc for i, tc in enumerate(ts_codes)}
            mf_params["td"] = trade_date

            mf_rows = session.execute(
                text(f"""
                    SELECT
                        ts_code,
                        net_amount,
                        net_amount_rate,
                        buy_elg_amount,
                        buy_lg_amount,
                        buy_md_amount,
                        buy_sm_amount,
                        close,
                        pct_change
                    FROM moneyflow_dc
                    WHERE trade_date = :td
                      AND ts_code IN ({placeholders})
                """),
                mf_params,
            ).fetchall()

            # 3) 查询当日基本面
            db_rows = session.execute(
                text(f"""
                    SELECT
                        ts_code,
                        pe_ttm,
                        pb,
                        turnover_rate,
                        total_mv,
                        circ_mv
                    FROM daily_basic
                    WHERE trade_date = :td
                      AND ts_code IN ({placeholders})
                """),
                mf_params,
            ).fetchall()

            basic_map = {}
            for r in db_rows:
                basic_map[r[0]] = {
                    "pe_ttm": round(float(r[1] or 0), 2),
                    "pb": round(float(r[2] or 0), 2),
                    "turnover_rate": round(float(r[3] or 0), 2),
                    "total_mv_yi": round(float(r[4] or 0) / 10000, 2),
                    "circ_mv_yi": round(float(r[5] or 0) / 10000, 2),
                }

            stocks = []
            total_net = 0.0
            total_buy_lg = 0.0
            total_buy_elg = 0.0

            for r in mf_rows:
                ts_code = r[0]
                net_amt = float(r[1] or 0)
                buy_elg = float(r[3] or 0)
                buy_lg = float(r[4] or 0)
                main_fund_net = buy_elg + buy_lg  # 主力资金净流入(超大单+大单买入)

                total_net += net_amt
                total_buy_lg += buy_lg
                total_buy_elg += buy_elg

                stock_info = {
                    "ts_code": ts_code,
                    "name": name_map.get(ts_code, ""),
                    "close": round(float(r[7] or 0), 2),
                    "pct_change": round(float(r[8] or 0), 2),
                    "net_amount": round(net_amt, 2),
                    "net_amount_rate": round(float(r[2] or 0), 2),
                    "buy_elg_amount": round(buy_elg, 2),
                    "buy_lg_amount": round(buy_lg, 2),
                    "main_fund_net": round(main_fund_net, 2),
                }
                stock_info.update(basic_map.get(ts_code, {
                    "pe_ttm": 0, "pb": 0, "turnover_rate": 0,
                    "total_mv_yi": 0, "circ_mv_yi": 0,
                }))
                stocks.append(stock_info)

            # 按净流入降序
            stocks.sort(key=lambda x: x["net_amount"], reverse=True)

            stock_count = len(stocks)

            # 近日净流入趋势 (5日)
            recent_flow = self._get_industry_recent_flow(
                session, ts_codes, trade_date, days=5
            )

            summary = {
                "stock_count": stock_count,
                "total_net_flow": round(total_net, 2),
                "total_buy_elg": round(total_buy_elg, 2),
                "total_buy_lg": round(total_buy_lg, 2),
                "avg_net_flow": round(total_net / stock_count, 2) if stock_count else 0,
                "net_flow_5d": round(recent_flow, 2),
                "inflow_count": sum(1 for s in stocks if s["net_amount"] > 0),
                "outflow_count": sum(1 for s in stocks if s["net_amount"] < 0),
            }

            return {
                "success": True,
                "data": {
                    "industry": industry,
                    "trade_date": trade_date,
                    "summary": summary,
                    "stocks": stocks,
                },
            }
        except Exception as exc:
            logger.error("get_industry_detail failed for %s: %s", industry, exc)
            return {"success": False, "error": str(exc)}
        finally:
            session.close()

    # ------------------------------------------------------------------
    # 内部辅助方法
    # ------------------------------------------------------------------
    @staticmethod
    def _get_latest_trade_date(session) -> Optional[str]:
        """获取数据库中最新的交易日期。"""
        try:
            row = session.execute(
                text("SELECT MAX(trade_date) FROM moneyflow_dc")
            ).fetchone()
            if row and row[0]:
                return row[0]
        except Exception:
            pass
        return None

    @staticmethod
    def _get_trade_dates(session, end_date: str, n: int) -> List[str]:
        """从数据库获取最近 N 个交易日（升序）。"""
        rows = session.execute(
            text("""
                SELECT DISTINCT trade_date
                FROM moneyflow_dc
                WHERE trade_date <= :end_date
                ORDER BY trade_date DESC
                LIMIT :n
            """),
            {"end_date": end_date, "n": n},
        ).fetchall()
        return sorted([r[0] for r in rows])

    @staticmethod
    def _get_industry_map(session) -> Dict[str, str]:
        """构建 ts_code → industry 映射。"""
        rows = session.execute(
            text("SELECT ts_code, industry FROM stock_basic")
        ).fetchall()
        return {r[0]: r[1] or "" for r in rows}

    @staticmethod
    def _query_industry_flow(session, trade_dates: List[str]) -> List[tuple]:
        """批量查询回看区间内所有资金流向记录。

        Returns:
            [(trade_date, ts_code, net_amount, buy_elg_amount, buy_lg_amount), ...]
        """
        placeholders = ", ".join([f":td{i}" for i in range(len(trade_dates))])
        params = {f"td{i}": d for i, d in enumerate(trade_dates)}

        rows = session.execute(
            text(f"""
                SELECT
                    trade_date,
                    ts_code,
                    COALESCE(net_amount, 0),
                    COALESCE(buy_elg_amount, 0),
                    COALESCE(buy_lg_amount, 0)
                FROM moneyflow_dc
                WHERE trade_date IN ({placeholders})
            """),
            params,
        ).fetchall()
        return rows

    @staticmethod
    def _aggregate_by_industry(
        flow_rows: List[tuple], industry_map: Dict[str, str]
    ) -> Dict[str, Dict[str, float]]:
        """按行业按日聚合净流入。

        Returns:
            {industry: {trade_date: total_net_amount, ...}, ...}
        """
        result: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for trade_date, ts_code, net_amount, _buy_elg, _buy_lg in flow_rows:
            industry = industry_map.get(ts_code, "")
            if not industry:
                continue
            result[industry][trade_date] += net_amount
        return result

    @staticmethod
    def _count_unique_stocks(
        flow_rows: List[tuple], industry: str, industry_map: Dict[str, str]
    ) -> int:
        """统计某行业在 flow_rows 中的不重复股票数量。"""
        codes = set()
        for _, ts_code, *_ in flow_rows:
            if industry_map.get(ts_code, "") == industry:
                codes.add(ts_code)
        return len(codes)

    @staticmethod
    def _calc_rotation_score(recent_flow: float, older_flow: float) -> float:
        """计算轮动得分。

        rotation_score = (recent_flow - older_flow) / max(abs(older_flow), 1)
        """
        return (recent_flow - older_flow) / max(abs(older_flow), 1.0)

    @staticmethod
    def _classify_signal(score: float) -> str:
        """根据轮动得分分类信号。"""
        if score > 0.8:
            return "ACCELERATION"
        elif score > 0.3:
            return "ROTATION_IN"
        elif score < -0.8:
            return "DECELERATION"
        elif score < -0.3:
            return "ROTATION_OUT"
        else:
            return "NEUTRAL"

    @staticmethod
    def _get_industry_recent_flow(
        session, ts_codes: List[str], end_date: str, days: int = 5
    ) -> float:
        """获取行业最近 N 日的累计净流入。"""
        if not ts_codes:
            return 0.0

        placeholders = ", ".join([f":tc{i}" for i in range(len(ts_codes))])
        params = {f"tc{i}": tc for i, tc in enumerate(ts_codes)}
        params["end_date"] = end_date
        params["n"] = days

        row = session.execute(
            text(f"""
                SELECT SUM(COALESCE(net_amount, 0))
                FROM (
                    SELECT trade_date, ts_code, net_amount
                    FROM moneyflow_dc
                    WHERE ts_code IN ({placeholders})
                      AND trade_date <= :end_date
                    ORDER BY trade_date DESC
                    LIMIT :n
                )
            """),
            params,
        ).fetchone()

        return float(row[0] or 0) if row else 0.0
