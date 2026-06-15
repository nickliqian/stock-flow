from fastapi import APIRouter, Query
from ..services.market import MarketService

router = APIRouter(prefix="/api/market", tags=["market"])
service = MarketService()


def _ok(data):
    """统一 API 响应格式：{success: true, data: ...}"""
    return {"success": True, "data": data}


@router.get("/overview")
def get_market_overview(trade_date: str = Query(None, pattern=r"^\d{8}$", description="交易日期 YYYYMMDD")):
    """大盘资金总览 — 主力/超大/大/中/小单净流入"""
    return _ok(service.get_overview(trade_date))


@router.get("/north")
def get_north_fund(trade_date: str = Query(None, pattern=r"^\d{8}$", description="交易日期 YYYYMMDD")):
    """北向资金 — 沪股通/深股通 + 历史对比"""
    return _ok(service.get_north_fund(trade_date))


@router.get("/flow-trend")
def get_flow_trend(days: int = Query(10, ge=1, le=120, description="最近N个交易日")):
    """资金趋势 — 近N日主力/超大/大/中/小单净流入"""
    # 修复：添加 ge=1, le=120 约束，防止异常天数参数
    return _ok(service.get_market_trend(days=days))


@router.get("/stock-ranking")
def get_stock_ranking(
    trade_date: str = Query(None, pattern=r"^\d{8}$", description="交易日期 YYYYMMDD"),
    type: str = Query("net_inflow", description="排行类型: net_inflow / net_outflow"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
):
    """个股资金流向排行榜 — 净流入/净流出 Top N"""
    return _ok(service.get_stock_ranking(trade_date=trade_date, ranking_type=type, limit=limit))


@router.get("/trend")
def get_fund_trend(days: int = Query(10, ge=1, le=120, description="最近N个交易日")):
    """资金趋势 — 近N日北向资金净流入"""
    # 修复：添加 ge=1, le=120 约束，防止异常天数参数
    return _ok(service.get_fund_trend(days=days))


@router.get("/turnover/trend")
def get_turnover_trend(days: int = Query(30, ge=1, le=120, description="最近N个交易日")):
    """成交额趋势 — 近N日全市场总成交额"""
    # 修复：添加 ge=1, le=120 约束，防止异常天数参数
    return _ok(service.get_turnover_trend(days=days))


@router.get("/breadth")
async def market_breadth(trade_date: str = Query(None, pattern=r"^\d{8}$", description="交易日期 YYYYMMDD")):
    """获取全市场涨跌分布."""
    return _ok(service.get_market_breadth(trade_date))


@router.get("/limit-stats")
async def get_limit_stats(trade_date: str = Query(None, pattern=r"^\d{8}$", description="交易日期 YYYYMMDD")):
    """获取涨跌停统计数据."""
    return _ok(service.get_limit_stats(trade_date))


@router.get("/indices")
async def get_market_indices(trade_date: str = Query(None, pattern=r"^\d{8}$", description="交易日期 YYYYMMDD")):
    """获取四大指数（上证指数、深证成指、创业板指、科创50）实时行情."""
    return _ok(service.get_market_indices(trade_date))


@router.get("/index-kline")
async def get_index_kline(ts_code: str = Query(..., description="指数代码, 如 000001.SH"), days: int = Query(30, ge=1, le=120, description="最近N个交易日")):
    """获取指数最近N日K线数据，用于 Drawer 趋势图."""
    # 修复：添加 ge=1, le=120 约束，防止异常天数参数
    return _ok(service.get_index_kline(ts_code, days))
