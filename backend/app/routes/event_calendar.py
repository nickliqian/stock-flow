"""Event Calendar API routes — 限售解禁日历 + 回购信号分析。"""

import threading

from fastapi import APIRouter, Query
from typing import Optional

from ..services.base import get_global_client, get_global_cache
from ..engine.event_calendar import EventCalendarEngine

router = APIRouter(prefix="/api/events", tags=["events"])

# 延迟初始化引擎实例
_engine = None
_engine_lock = threading.Lock()


def _get_engine() -> EventCalendarEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = EventCalendarEngine(get_global_client(), get_global_cache())
    return _engine


@router.get("/unlock-calendar")
def get_unlock_calendar(
    start_date: Optional[str] = Query(None, description="开始日期 YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
    min_unlock_ratio: float = Query(0.01, description="最小解禁比例 (0-1)"),
):
    """限售解禁日历 — 获取即将到来的限售股解禁事件"""
    engine = _get_engine()
    return engine.get_unlock_calendar(
        start_date=start_date,
        end_date=end_date,
        min_unlock_ratio=min_unlock_ratio,
    )


@router.get("/buyback-signals")
def get_buyback_signals(
    start_date: Optional[str] = Query(None, description="开始日期 YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
    min_amount: float = Query(0, description="最小回购金额"),
):
    """回购信号分析 — 获取股票回购公告与信心评分"""
    engine = _get_engine()
    return engine.get_buyback_signals(
        start_date=start_date,
        end_date=end_date,
        min_amount=min_amount,
    )


@router.get("/heatmap")
def get_event_heatmap(
    trade_date: Optional[str] = Query(None, description="基准日期 YYYYMMDD"),
    lookforward_days: int = Query(30, description="前瞻天数"),
    lookback_days: int = Query(30, description="回溯天数"),
):
    """事件热力图 — 综合解禁压力与回购信心的全局视图"""
    engine = _get_engine()
    return engine.get_event_heatmap(
        trade_date=trade_date,
        lookforward_days=lookforward_days,
        lookback_days=lookback_days,
    )
