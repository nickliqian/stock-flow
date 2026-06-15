"""Shareholder Intelligence API routes."""

import threading

from fastapi import APIRouter, Query
from typing import Optional

from ..services.base import get_global_client, get_global_cache
from ..engine.shareholder_intelligence import ShareholderIntelligenceEngine

router = APIRouter(prefix="/api/shareholder", tags=["shareholder"])

# 延迟初始化引擎实例
_engine = None
_engine_lock = threading.Lock()


def _get_engine() -> ShareholderIntelligenceEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = ShareholderIntelligenceEngine(get_global_client(), get_global_cache())
    return _engine


@router.get("/holder-trade")
def get_holder_trade(
    start_date: Optional[str] = Query(None, description="开始日期 YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
    lookback_days: int = Query(30, description="回溯天数"),
):
    """股东增减持分析 — 获取大股东增减持动态"""
    engine = _get_engine()
    return engine.analyze_holder_trade(
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )


@router.get("/holder-num")
def get_holder_num(
    ts_code: Optional[str] = Query(None, description="股票代码，如 000001.SZ"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYYMMDD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYYMMDD"),
    lookback_days: int = Query(90, description="回溯天数"),
):
    """股东人数变动分析 — 通过股东人数变化判断筹码集中/分散"""
    engine = _get_engine()
    return engine.analyze_holder_num(
        ts_code=ts_code,
        start_date=start_date,
        end_date=end_date,
        lookback_days=lookback_days,
    )


@router.get("/top-holders")
def get_top_holders(
    ts_code: Optional[str] = Query(None, description="股票代码，如 000001.SZ"),
    end_date: Optional[str] = Query(None, description="截止日期 YYYYMMDD"),
):
    """前十大股东分析 — 分析股权结构和机构持仓"""
    engine = _get_engine()
    return engine.analyze_top_holders(
        ts_code=ts_code,
        end_date=end_date,
    )


@router.get("/comprehensive")
def get_comprehensive(
    ts_code: Optional[str] = Query(None, description="股票代码，如 000001.SZ"),
    trade_date: Optional[str] = Query(None, description="交易日期 YYYYMMDD"),
    lookback_days: int = Query(30, description="回溯天数"),
):
    """综合股东情报分析 — 整合增减持、人数变动、前十大股东三个维度"""
    engine = _get_engine()
    return engine.get_comprehensive_analysis(
        ts_code=ts_code,
        trade_date=trade_date,
        lookback_days=lookback_days,
    )
