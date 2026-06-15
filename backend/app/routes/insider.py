"""内部人与机构智能 API routes."""

import threading

from fastapi import APIRouter, Query
from typing import Optional

from ..services.base import get_global_client, get_global_cache
from ..engine.insider_conviction import InsiderConvictionEngine

router = APIRouter(prefix="/api/insider", tags=["insider"])

# 延迟初始化引擎实例
_engine = None
_engine_lock = threading.Lock()


def _get_engine() -> InsiderConvictionEngine:
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = InsiderConvictionEngine(get_global_client(), get_global_cache())
    return _engine


@router.get("/conviction")
def get_conviction(
    limit: int = Query(50, description="返回数量"),
):
    """全市场置信度扫描——四维信号合成置信度评分"""
    engine = _get_engine()
    return engine.get_market_conviction(limit=limit)


@router.get("/conviction/{ts_code}")
def get_conviction_detail(ts_code: str):
    """单只股票的详细置信度分析"""
    engine = _get_engine()
    return engine.get_stock_conviction(ts_code=ts_code)


@router.get("/trades/{ts_code}")
def get_trades(
    ts_code: str,
    days: int = Query(30, description="回溯天数"),
):
    """获取指定股票的内部人交易明细"""
    engine = _get_engine()
    return engine.get_insider_trades(ts_code=ts_code, days=days)


@router.get("/shareholder-trend/{ts_code}")
def get_shareholder_trend(ts_code: str):
    """获取股东人数变动趋势 + 前十大股东变动"""
    engine = _get_engine()
    return engine.get_shareholder_trend(ts_code=ts_code)
