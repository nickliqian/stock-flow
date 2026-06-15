"""事件日历引擎——限售解禁日历 + 回购信号分析。

分析维度:
1. 限售解禁日历 — 追踪即将到来的限售股解禁事件，评估解禁压力
2. 回购信号分析 — 跟踪公司回购公告，评估管理层信心
3. 综合事件评分 — 联合解禁压力+回购信心，给出事件驱动信号
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import pandas as pd

from ..clients.tushare import TuShareClient
from ..cache import CacheService
from ..utils import get_latest_trade_date

logger = logging.getLogger(__name__)


class EventCalendarEngine:
    """事件日历引擎——限售解禁日历 + 回购信号分析。"""

    def __init__(self, client: TuShareClient, cache: CacheService):
        self.client = client
        self.cache = cache

    # ------------------------------------------------------------------
    # 1. 限售解禁日历
    # ------------------------------------------------------------------
    def get_unlock_calendar(
        self,
        start_date: str = None,
        end_date: str = None,
        min_unlock_ratio: float = 0.01,
    ) -> Dict[str, Any]:
        """获取限售解禁日历。

        使用 Tushare share_float API 获取限售股解禁数据，
        计算解禁压力评分并按日期排序返回。
        """
        today = get_latest_trade_date(self.cache)

        if not start_date:
            start_date = today
        if not end_date:
            dt = datetime.strptime(start_date, "%Y%m%d")
            end_dt = dt + timedelta(days=90)
            end_date = end_dt.strftime("%Y%m%d")

        try:
            df = self.client._call_with_retry(
                self.client.pro.share_float,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as exc:
            logger.warning("share_float load failed: %s", exc)
            df = None

        if df is None or df.empty:
            return {
                "data": [],
                "summary": {
                    "total_events": 0,
                    "high_pressure_count": 0,
                    "total_unlock_shares": 0,
                    "avg_pressure_score": 0,
                },
                "period": {"start_date": start_date, "end_date": end_date},
            }

        today_dt = datetime.strptime(today, "%Y%m%d")

        events = []
        for _, row in df.iterrows():
            ts_code = str(row.get("ts_code", ""))
            float_date = str(row.get("float_date", ""))
            float_share = self._safe_float(row, "float_share") or 0
            float_ratio = self._safe_float(row, "float_ratio") or 0
            holder_name = str(row.get("holder_name", ""))
            holder_type = str(row.get("holder_type", ""))
            float_reason = str(row.get("float_reason", ""))

            # 过滤解禁比例
            if float_ratio < min_unlock_ratio:
                continue

            # 计算距今天数
            days_until = 0
            if float_date and len(float_date) == 8:
                try:
                    fd_dt = datetime.strptime(float_date, "%Y%m%d")
                    days_until = (fd_dt - today_dt).days
                except ValueError:
                    days_until = 0

            # 计算解禁压力评分 (0-100)
            pressure_score = self._calc_unlock_pressure(
                float_ratio, days_until
            )

            events.append({
                "ts_code": ts_code,
                "float_date": float_date,
                "float_share": round(float_share, 2),
                "float_ratio": round(float_ratio, 4),
                "holder_name": holder_name,
                "holder_type": holder_type,
                "float_reason": float_reason,
                "days_until": days_until,
                "pressure_score": round(pressure_score, 1),
            })

        # 按日期升序排序
        events.sort(key=lambda x: x.get("float_date", ""))

        high_pressure = sum(1 for e in events if e["pressure_score"] >= 50)
        total_shares = sum(e["float_share"] for e in events)
        avg_pressure = (
            sum(e["pressure_score"] for e in events) / len(events)
            if events else 0
        )

        return {
            "data": events[:300],
            "summary": {
                "total_events": len(events),
                "high_pressure_count": high_pressure,
                "total_unlock_shares": round(total_shares, 2),
                "avg_pressure_score": round(avg_pressure, 1),
            },
            "period": {"start_date": start_date, "end_date": end_date},
        }

    # ------------------------------------------------------------------
    # 2. 回购信号分析
    # ------------------------------------------------------------------
    def get_buyback_signals(
        self,
        start_date: str = None,
        end_date: str = None,
        min_amount: float = 0,
    ) -> Dict[str, Any]:
        """获取股票回购信号。

        使用 Tushare repurchase API 获取回购数据，
        计算回购信心评分并返回。
        """
        today = get_latest_trade_date(self.cache)

        if not end_date:
            end_date = today
        if not start_date:
            dt = datetime.strptime(end_date, "%Y%m%d")
            start_dt = dt - timedelta(days=90)
            start_date = start_dt.strftime("%Y%m%d")

        try:
            df = self.client._call_with_retry(
                self.client.pro.repurchase,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as exc:
            logger.warning("repurchase load failed: %s", exc)
            df = None

        if df is None or df.empty:
            return {
                "data": [],
                "summary": {
                    "total_announcements": 0,
                    "total_buyback_amount": 0,
                    "avg_confidence_score": 0,
                    "active_buyback_count": 0,
                },
                "period": {"start_date": start_date, "end_date": end_date},
            }

        today_dt = datetime.strptime(today, "%Y%m%d")

        signals = []
        for _, row in df.iterrows():
            ts_code = str(row.get("ts_code", ""))
            ann_date = str(row.get("ann_date", ""))
            exp_date = str(row.get("exp_date", ""))
            vol = self._safe_float(row, "vol") or 0
            high_limit = self._safe_float(row, "high_limit") or 0
            low_limit = self._safe_float(row, "low_limit") or 0
            amount = self._safe_float(row, "amount") or 0
            reason = str(row.get("reason", ""))

            # 过滤最小回购金额
            if amount < min_amount:
                continue

            # 计算距今天数
            days_since = 0
            if ann_date and len(ann_date) == 8:
                try:
                    ad_dt = datetime.strptime(ann_date, "%Y%m%d")
                    days_since = (today_dt - ad_dt).days
                except ValueError:
                    days_since = 0

            # 是否仍在进行中（未过期或无到期日）
            is_active = True
            if exp_date and len(exp_date) == 8:
                try:
                    exp_dt = datetime.strptime(exp_date, "%Y%m%d")
                    is_active = exp_dt >= today_dt
                except ValueError:
                    is_active = True

            # 计算回购信心评分 (0-100)
            confidence_score = self._calc_buyback_confidence(
                amount, vol, days_since
            )

            signals.append({
                "ts_code": ts_code,
                "ann_date": ann_date,
                "exp_date": exp_date,
                "vol": round(vol, 2),
                "high_limit": round(high_limit, 2),
                "low_limit": round(low_limit, 2),
                "amount": round(amount, 2),
                "reason": reason,
                "days_since": days_since,
                "is_active": is_active,
                "confidence_score": round(confidence_score, 1),
            })

        # 按公告日期降序排序
        signals.sort(key=lambda x: x.get("ann_date", ""), reverse=True)

        total_amount = sum(s["amount"] for s in signals)
        avg_confidence = (
            sum(s["confidence_score"] for s in signals) / len(signals)
            if signals else 0
        )
        active_count = sum(1 for s in signals if s["is_active"])

        return {
            "data": signals[:300],
            "summary": {
                "total_announcements": len(signals),
                "total_buyback_amount": round(total_amount, 2),
                "avg_confidence_score": round(avg_confidence, 1),
                "active_buyback_count": active_count,
            },
            "period": {"start_date": start_date, "end_date": end_date},
        }

    # ------------------------------------------------------------------
    # 3. 事件热力图 — 联合解禁+回购综合视图
    # ------------------------------------------------------------------
    def get_event_heatmap(
        self,
        trade_date: str = None,
        lookforward_days: int = 30,
        lookback_days: int = 30,
    ) -> Dict[str, Any]:
        """综合事件热力图——联合解禁压力+回购信心。

        - upcoming_unlocks: 未来 N 天的解禁事件
        - recent_buybacks: 最近 N 天的回购事件
        - risk_stocks: 高解禁压力且无回购的股票
        - opportunity_stocks: 有回购且低解禁压力的股票
        """
        if not trade_date:
            trade_date = get_latest_trade_date(self.cache)

        today_dt = datetime.strptime(trade_date, "%Y%m%d")

        # 未来解禁数据
        uf_end = (today_dt + timedelta(days=lookforward_days)).strftime("%Y%m%d")
        unlock_result = self.get_unlock_calendar(
            start_date=trade_date,
            end_date=uf_end,
            min_unlock_ratio=0.005,
        )

        # 最近回购数据
        rb_start = (today_dt - timedelta(days=lookback_days)).strftime("%Y%m%d")
        buyback_result = self.get_buyback_signals(
            start_date=rb_start,
            end_date=trade_date,
            min_amount=0,
        )

        upcoming_unlocks = unlock_result.get("data", [])
        recent_buybacks = buyback_result.get("data", [])

        # 按股票聚合解禁压力
        unlock_by_code: Dict[str, float] = {}
        unlock_count_by_code: Dict[str, int] = {}
        for ev in upcoming_unlocks:
            code = ev["ts_code"]
            unlock_by_code[code] = unlock_by_code.get(code, 0) + ev["pressure_score"]
            unlock_count_by_code[code] = unlock_count_by_code.get(code, 0) + 1

        # 按股票聚合回购信心
        buyback_by_code: Dict[str, float] = {}
        buyback_count_by_code: Dict[str, int] = {}
        for bb in recent_buybacks:
            code = bb["ts_code"]
            buyback_by_code[code] = buyback_by_code.get(code, 0) + bb["confidence_score"]
            buyback_count_by_code[code] = buyback_count_by_code.get(code, 0) + 1

        all_codes = set(list(unlock_by_code.keys()) + list(buyback_by_code.keys()))

        risk_stocks = []
        opportunity_stocks = []

        for code in all_codes:
            up = unlock_by_code.get(code, 0)
            bb = buyback_by_code.get(code, 0)

            if up > 50 and bb == 0:
                risk_stocks.append({
                    "ts_code": code,
                    "unlock_pressure": round(up, 1),
                    "unlock_count": unlock_count_by_code.get(code, 0),
                    "buyback_confidence": 0,
                    "buyback_count": 0,
                    "risk_level": "high" if up >= 80 else "medium",
                })
            elif bb > 0 and up < 30:
                opportunity_stocks.append({
                    "ts_code": code,
                    "unlock_pressure": round(up, 1),
                    "unlock_count": unlock_count_by_code.get(code, 0),
                    "buyback_confidence": round(bb, 1),
                    "buyback_count": buyback_count_by_code.get(code, 0),
                    "opportunity_level": "high" if bb >= 80 else "medium",
                })

        risk_stocks.sort(key=lambda x: x["unlock_pressure"], reverse=True)
        opportunity_stocks.sort(key=lambda x: x["buyback_confidence"], reverse=True)

        # 计算综合指标
        total_unlock_pressure = sum(e["pressure_score"] for e in upcoming_unlocks)
        total_buyback_confidence = sum(s["confidence_score"] for s in recent_buybacks)
        net_signal = total_buyback_confidence - total_unlock_pressure

        if net_signal > 20:
            overall_signal = "bullish"
            overall_label = "偏多（回购信心>解禁压力）"
        elif net_signal < -20:
            overall_signal = "bearish"
            overall_label = "偏空（解禁压力>回购信心）"
        else:
            overall_signal = "neutral"
            overall_label = "中性（压力与信心平衡）"

        # 事件活跃度指数 (0-100)
        event_count = len(upcoming_unlocks) + len(recent_buybacks)
        activity_index = min(100, event_count * 2)

        return {
            "upcoming_unlocks": upcoming_unlocks[:100],
            "recent_buybacks": recent_buybacks[:100],
            "risk_stocks": risk_stocks[:50],
            "opportunity_stocks": opportunity_stocks[:50],
            "summary": {
                "upcoming_unlock_count": len(upcoming_unlocks),
                "recent_buyback_count": len(recent_buybacks),
                "risk_stock_count": len(risk_stocks),
                "opportunity_stock_count": len(opportunity_stocks),
                "total_unlock_pressure": round(total_unlock_pressure, 1),
                "total_buyback_confidence": round(total_buyback_confidence, 1),
                "net_signal": round(net_signal, 1),
                "overall_signal": overall_signal,
                "overall_label": overall_label,
                "activity_index": activity_index,
            },
            "period": {
                "trade_date": trade_date,
                "lookforward_days": lookforward_days,
                "lookback_days": lookback_days,
            },
        }

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _calc_unlock_pressure(float_ratio: float, days_until: int) -> float:
        """计算限售解禁压力评分 (0-100)。

        - float_ratio 越大 → 压力越大 (权重 50%)
        - days_until 越小 → 越紧迫 (权重 30%)
        - 时间衰减因子 (权重 20%)
        """
        # 解禁比例得分: 1% → 30分, 5% → 60分, 10% → 80分, 20%+ → 95分
        if float_ratio >= 0.20:
            ratio_score = 95
        elif float_ratio >= 0.10:
            ratio_score = 80
        elif float_ratio >= 0.05:
            ratio_score = 60
        elif float_ratio >= 0.02:
            ratio_score = 40
        elif float_ratio >= 0.01:
            ratio_score = 25
        else:
            ratio_score = 10

        # 临近度得分: 0天 → 100, 7天 → 70, 30天 → 30, 90天 → 5
        if days_until <= 0:
            urgency_score = 100
        elif days_until <= 7:
            urgency_score = 100 - days_until * 4
        elif days_until <= 30:
            urgency_score = 72 - (days_until - 7) * (42 / 23)
        elif days_until <= 90:
            urgency_score = 30 - (days_until - 30) * (25 / 60)
        else:
            urgency_score = 5

        # 综合评分
        score = ratio_score * 0.5 + urgency_score * 0.3 + urgency_score * 0.2
        return max(0, min(100, score))

    @staticmethod
    def _calc_buyback_confidence(
        amount: float, vol: float, days_since: int
    ) -> float:
        """计算回购信心评分 (0-100)。

        - amount 越大 → 信心越强 (权重 50%)
        - 回购数量越多 → 信心越强 (权重 20%)
        - 越近期的公告 → 信心越强 (权重 30%)
        """
        # 金额得分: 1亿+ → 90, 5000万 → 70, 1000万 → 50, 1000万以下 → 30
        if amount >= 100000000:  # 1亿
            amount_score = 90
        elif amount >= 50000000:  # 5000万
            amount_score = 70
        elif amount >= 10000000:  # 1000万
            amount_score = 50
        elif amount >= 5000000:  # 500万
            amount_score = 35
        elif amount >= 1000000:  # 100万
            amount_score = 20
        else:
            amount_score = 10

        # 数量得分
        if vol >= 10000000:  # 1000万股
            vol_score = 80
        elif vol >= 5000000:
            vol_score = 60
        elif vol >= 1000000:
            vol_score = 40
        elif vol >= 100000:
            vol_score = 25
        else:
            vol_score = 10

        # 新鲜度得分: 0天 → 100, 7天 → 75, 30天 → 30, 90天 → 5
        if days_since <= 0:
            freshness_score = 100
        elif days_since <= 7:
            freshness_score = 100 - days_since * 3.5
        elif days_since <= 30:
            freshness_score = 75.5 - (days_since - 7) * (45.5 / 23)
        elif days_since <= 90:
            freshness_score = 30 - (days_since - 30) * (25 / 60)
        else:
            freshness_score = 5

        # 综合评分
        score = amount_score * 0.5 + vol_score * 0.2 + freshness_score * 0.3
        return max(0, min(100, score))

    @staticmethod
    def _safe_float(row, col):
        try:
            v = row.get(col) if hasattr(row, "get") else row[col]
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            return float(v)
        except (ValueError, TypeError, KeyError):
            return None
