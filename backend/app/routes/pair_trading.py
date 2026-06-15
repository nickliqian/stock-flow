"""协整配对交易 API 路由。"""

import logging
from fastapi import APIRouter, Query, HTTPException
from typing import Optional

from ..services.strategy import StrategyService, get_global_strategy_service
from ..utils import make_lazy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pair-trading", tags=["pair-trading"])

service = get_global_strategy_service()


def _create_pair_trading_engine():
    from ..engine.pair_trading import PairTradingEngine
    return PairTradingEngine(service.client, service.cache)

_get_engine = make_lazy(_create_pair_trading_engine)


@router.get("/discover")
def discover_pairs(
    trade_date: Optional[str] = Query(None, description="交易日期 YYYYMMDD"),
    lookback_days: int = Query(90, ge=30, le=200, description="回看天数"),
    min_correlation: float = Query(0.7, ge=0.3, le=0.95, description="最小相关性"),
    significance: float = Query(0.05, ge=0.01, le=0.1, description="协整显著性水平"),
    min_market_cap: float = Query(50, ge=10, le=1000, description="最小市值(亿)"),
    universe_size: int = Query(80, ge=20, le=200, description="股票池大小"),
):
    """发现协整配对

    基于 Engle-Granger 协整检验，寻找具有均值回复特性的股票配对。
    """
    engine = _get_engine()
    # min_market_cap 从亿转为万元
    result = engine.discover_pairs(
        trade_date=trade_date,
        lookback_days=lookback_days,
        min_correlation=min_correlation,
        significance=significance,
        min_market_cap=min_market_cap * 10000,
        universe_size=universe_size,
    )
    return {"success": True, "data": result}


@router.get("/signals")
def get_signals(
    trade_date: Optional[str] = Query(None, description="交易日期 YYYYMMDD"),
    lookback_days: int = Query(90, ge=30, le=200, description="回看天数"),
    zscore_entry: float = Query(2.0, ge=1.0, le=3.0, description="入场z-score阈值"),
    zscore_exit: float = Query(0.5, ge=0.0, le=1.5, description="出场z-score阈值"),
    min_market_cap: float = Query(50, ge=10, le=1000, description="最小市值(亿)"),
):
    """获取当前配对交易信号

    基于价差 z-score 生成入场/出场/持有信号。
    """
    engine = _get_engine()
    result = engine.get_pair_signals(
        trade_date=trade_date,
        lookback_days=lookback_days,
        zscore_entry=zscore_entry,
        zscore_exit=zscore_exit,
        min_market_cap=min_market_cap * 10000,
    )
    return {"success": True, "data": result}


@router.get("/backtest")
def backtest_pair(
    code1: str = Query(..., pattern=r"^\d{6}\.(SH|SZ)$", description="股票1代码，如 000001.SZ"),
    code2: str = Query(..., pattern=r"^\d{6}\.(SH|SZ)$", description="股票2代码，如 600519.SH"),
    start_date: Optional[str] = Query(None, description="起始日期"),
    end_date: Optional[str] = Query(None, description="结束日期"),
    hold_days: int = Query(5, ge=1, le=20, description="最大持有天数"),
    zscore_entry: float = Query(2.0, ge=1.0, le=3.0, description="入场z-score阈值"),
    zscore_exit: float = Query(0.5, ge=0.0, le=1.5, description="出场z-score阈值"),
):
    """回测单个配对交易策略"""
    engine = _get_engine()
    result = engine.backtest_pair(
        code1=code1,
        code2=code2,
        start_date=start_date,
        end_date=end_date,
        hold_days=hold_days,
        zscore_entry=zscore_entry,
        zscore_exit=zscore_exit,
    )
    return {"success": True, "data": result}


@router.get("/pair")
def get_pair_detail(
    code1: str = Query(..., pattern=r"^\d{6}\.(SH|SZ)$", description="股票1代码，如 000001.SZ"),
    code2: str = Query(..., pattern=r"^\d{6}\.(SH|SZ)$", description="股票2代码，如 600519.SH"),
    lookback_days: int = Query(90, ge=30, le=200, description="回看天数"),
):
    """获取配对详情（价差走势、z-score、协整检验结果）"""
    engine = _get_engine()
    result = engine.get_pair_detail(
        code1=code1, code2=code2, lookback_days=lookback_days
    )
    return {"success": True, "data": result}
