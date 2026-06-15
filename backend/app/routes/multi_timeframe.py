"""多时间框架动量共振 API 路由。"""

import logging
from fastapi import APIRouter, Query
from typing import Optional

from ..services.strategy import StrategyService, get_global_strategy_service
from ..utils import make_lazy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/multi-timeframe", tags=["multi-timeframe"])

service = get_global_strategy_service()


def _create_multi_timeframe_engine():
    from ..engine.multi_timeframe import MultiTimeframeEngine
    return MultiTimeframeEngine(service.loader, service.cache)


_get_engine = make_lazy(_create_multi_timeframe_engine)


@router.get("/analyze")
def analyze_multi_timeframe(
    trade_date: Optional[str] = Query(None, description="交易日期 YYYYMMDD，留空取最新"),
):
    """全市场多时间框架动量共振分析。

    检测 5日/10日/20日 三个时间框架的动量方向一致性，
    当多时间框架方向一致时产生强共振信号。
    """
    engine = _get_engine()
    result = engine.analyze(trade_date=trade_date)
    return {"success": True, "data": result}


@router.get("/stock/{ts_code}")
def analyze_stock(
    ts_code: str,
    trade_date: Optional[str] = Query(None, description="交易日期 YYYYMMDD，留空取最新"),
):
    """单只股票的多时间框架深度分析。

    包含各时间框架的动量、成交量、趋势方向详情，
    以及共振评分和信号判定。
    """
    engine = _get_engine()
    result = engine.analyze_stock(ts_code, trade_date=trade_date)
    return {"success": True, "data": result}
