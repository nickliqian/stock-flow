"""Technical Indicator API routes."""

from fastapi import APIRouter, Query
from typing import Optional
from ..services.technical import TechnicalService

router = APIRouter(prefix="/api/technical", tags=["technical"])
service = TechnicalService()


@router.get("/screen")
def screen_by_signals(
    trade_date: Optional[str] = Query(None, description="交易日期 YYYYMMDD"),
    macd_golden: Optional[bool] = Query(None, description="MACD金叉"),
    macd_dead: Optional[bool] = Query(None, description="MACD死叉"),
    kdj_golden: Optional[bool] = Query(None, description="KDJ金叉"),
    kdj_overbought: Optional[bool] = Query(None, description="KDJ超买"),
    kdj_oversold: Optional[bool] = Query(None, description="KDJ超卖"),
    rsi_oversold: Optional[bool] = Query(None, description="RSI超卖"),
    rsi_overbought: Optional[bool] = Query(None, description="RSI超买"),
    boll_break_upper: Optional[bool] = Query(None, description="突破布林上轨"),
    boll_break_lower: Optional[bool] = Query(None, description="跌破布林下轨"),
    cci_oversold: Optional[bool] = Query(None, description="CCI超卖"),
    cci_overbought: Optional[bool] = Query(None, description="CCI超买"),
    ma5_above_ma20: Optional[bool] = Query(None, description="MA5在MA20上方"),
    page: int = Query(1, description="页码"),
    page_size: int = Query(50, description="每页条数"),
):
    """技术指标选股 — 按MACD/KDJ/RSI/布林带/CCI等技术指标筛选股票"""
    signals = {}
    if macd_golden is not None: signals["macd_golden"] = macd_golden
    if macd_dead is not None: signals["macd_dead"] = macd_dead
    if kdj_golden is not None: signals["kdj_golden"] = kdj_golden
    if kdj_overbought is not None: signals["kdj_overbought"] = kdj_overbought
    if kdj_oversold is not None: signals["kdj_oversold"] = kdj_oversold
    if rsi_oversold is not None: signals["rsi_oversold"] = rsi_oversold
    if rsi_overbought is not None: signals["rsi_overbought"] = rsi_overbought
    if boll_break_upper is not None: signals["boll_break_upper"] = boll_break_upper
    if boll_break_lower is not None: signals["boll_break_lower"] = boll_break_lower
    if cci_oversold is not None: signals["cci_oversold"] = cci_oversold
    if cci_overbought is not None: signals["cci_overbought"] = cci_overbought
    if ma5_above_ma20 is not None: signals["ma5_above_ma20"] = ma5_above_ma20

    return service.screen_by_signals(
        trade_date=trade_date,
        signals=signals if signals else None,
        page=page,
        page_size=page_size,
    )
