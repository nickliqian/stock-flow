"""策略信号告警 API 路由。"""

import logging
from fastapi import APIRouter, Query

from ..services.strategy import StrategyService, get_global_strategy_service
from ..utils import make_lazy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

service = get_global_strategy_service()


# ------- 模块级延迟初始化引擎实例 -------


def _create_signal_alert_engine():
    from ..engine.signal_alert import SignalAlertEngine
    from ..engine.data_loader import StrategyDataLoader
    loader = StrategyDataLoader(service.client, service.cache)
    return SignalAlertEngine(loader, service.cache)


_get_engine = make_lazy(_create_signal_alert_engine)


@router.get("/signals")
def generate_signals(trade_date: str = Query(..., description="交易日期 YYYYMMDD")):
    """生成并记录策略信号（每次调用会清空旧数据后重新生成）。"""
    engine = _get_engine()
    return engine.generate_signals(trade_date)


@router.get("/")
def get_alerts(
    trade_date: str = Query(..., description="交易日期 YYYYMMDD"),
    min_strategies: int = Query(3, ge=2, le=10, description="最少策略数"),
):
    """获取告警列表（被多个策略同时选中的股票）。"""
    engine = _get_engine()
    return engine.get_alerts(trade_date, min_strategies)


@router.get("/history/{ts_code}")
def get_signal_history(
    ts_code: str,
    days: int = Query(20, ge=1, le=60, description="回溯天数"),
):
    """获取某只股票的信号历史。"""
    engine = _get_engine()
    return engine.get_signal_history(ts_code, days)


@router.get("/summary")
def get_alert_summary(
    trade_date: str = Query(..., description="交易日期 YYYYMMDD"),
):
    """获取告警汇总统计。"""
    engine = _get_engine()
    return engine.get_alert_summary(trade_date)
