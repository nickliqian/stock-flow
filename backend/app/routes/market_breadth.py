from fastapi import APIRouter, Query
from ..engine.market_breadth import MarketBreadthEngine

router = APIRouter(prefix="/api/market-breadth", tags=["market-breadth"])
engine = MarketBreadthEngine()


@router.get("")
def get_market_breadth(
    trade_date: str = Query(None, pattern=r"^\d{8}$", description="交易日期 YYYYMMDD"),
):
    """市场宽度指标 — 涨跌分布、涨跌停统计、市场温度。"""
    return engine.get_breadth(trade_date)


@router.get("/temperature")
def get_temperature_history(
    days: int = Query(30, description="最近N个交易日"),
):
    """市场温度历史 — 近N日温度趋势。"""
    return engine.get_temperature_history(days)
