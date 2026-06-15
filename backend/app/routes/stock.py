from fastapi import APIRouter, Path, Query
from ..services.stock import StockService

router = APIRouter(prefix="/api/stocks", tags=["stocks"])
service = StockService()


@router.get("/search")
def search_stocks(q: str = Query(..., description="搜索关键词（名称/代码）")):
    """搜索个股"""
    return service.search_stocks(q)


@router.get("/{ts_code}")
def get_stock_flow(
    ts_code: str = Path(..., pattern=r"^\d{6}\.(SH|SZ)$", description="股票代码，如 000001.SZ"),
    trade_date: str = Query(None, pattern=r"^\d{8}$", description="交易日期 YYYYMMDD"),
):
    """个股资金流向详情"""
    return service.get_stock_flow(ts_code, trade_date)


@router.get("/{ts_code}/dragon")
def get_dragon_tiger(
    ts_code: str,
    trade_date: str = Query(None, pattern=r"^\d{8}$", description="交易日期 YYYYMMDD"),
):
    """个股龙虎榜数据"""
    # 修复：添加 pattern 校验，防止非法日期格式传入后端
    return service.get_dragon_tiger(ts_code, trade_date)


@router.get("/{ts_code}/daily")
def get_daily_prices(
    ts_code: str,
    days: int = Query(20, ge=1, le=120, description="最近N个交易日"),
):
    """个股日线行情数据（K线图）"""
    # 修复：添加 ge/le 约束，防止异常天数参数导致查询超大结果集
    return service.get_daily_prices(ts_code, days)


@router.get("/{ts_code}/flow-trend")
def get_stock_flow_trend(
    ts_code: str,
    days: int = Query(10, ge=1, le=120, description="最近N个交易日"),
):
    """个股资金流向趋势（近N日各类型资金净流入）"""
    # 修复：添加 ge/le 约束，防止异常天数参数
    return service.get_stock_flow_trend(ts_code, days)


@router.get("/{ts_code}/basic")
def get_stock_basic(
    ts_code: str = Path(..., pattern=r"^\d{6}\.(SH|SZ)$", description="股票代码，如 000001.SZ"),
):
    """个股基本面指标（PE、PB、市值等）"""
    return service.get_stock_basic_info(ts_code)
