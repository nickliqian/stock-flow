"""Stock Screener API routes."""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from ..services.screener import ScreenerService

router = APIRouter(prefix="/api/screener", tags=["screener"])
service = ScreenerService()

# 修复：定义 sort_by 白名单，防止用户传入非法字段名导致 SQL 注入或异常
_VALID_SORT_FIELDS = {
    "close", "pe", "pe_ttm", "pb", "ps", "total_mv", "circ_mv",
    "turnover_rate", "volume_ratio", "dv_ttm", "net_amount", "net_inflow", "name",
}

# 修复：定义 sort_order 白名单，只允许 asc/desc
_VALID_SORT_ORDERS = {"asc", "desc"}


@router.get("/stocks")
def screen_stocks(
    trade_date: Optional[str] = Query(None, description="交易日期 YYYYMMDD"),
    pe_min: Optional[float] = Query(None, description="PE(TTM) 最小值"),
    pe_max: Optional[float] = Query(None, description="PE(TTM) 最大值"),
    pb_min: Optional[float] = Query(None, description="PB 最小值"),
    pb_max: Optional[float] = Query(None, description="PB 最大值"),
    mv_min: Optional[float] = Query(None, description="总市值最小值(亿元)"),
    mv_max: Optional[float] = Query(None, description="总市值最大值(亿元)"),
    circ_mv_min: Optional[float] = Query(None, description="流通市值最小值(亿元)"),
    circ_mv_max: Optional[float] = Query(None, description="流通市值最大值(亿元)"),
    turnover_min: Optional[float] = Query(None, description="换手率最小值(%)"),
    turnover_max: Optional[float] = Query(None, description="换手率最大值(%)"),
    volume_ratio_min: Optional[float] = Query(None, description="量比最小值"),
    volume_ratio_max: Optional[float] = Query(None, description="量比最大值"),
    dv_min: Optional[float] = Query(None, description="股息率最小值(%)"),
    dv_max: Optional[float] = Query(None, description="股息率最大值(%)"),
    net_inflow_min: Optional[float] = Query(None, description="净流入最小值(万元)"),
    name: Optional[str] = Query(None, description="股票名称/代码模糊搜索"),
    industry: Optional[str] = Query(None, description="行业筛选"),
    sort_by: str = Query("total_mv", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向: asc/desc"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页条数"),
):
    """多维度选股筛选器 — 按 PE/PB/市值/换手率/量比/股息率/资金流入等条件筛选股票"""
    # 修复：校验 sort_by 是否在白名单内，防止非法字段导致 SQL 注入
    if sort_by not in _VALID_SORT_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"sort_by 不合法: {sort_by!r}，允许的值: {sorted(_VALID_SORT_FIELDS)}",
        )
    # 修复：校验 sort_order 是否合法
    if sort_order.lower() not in _VALID_SORT_ORDERS:
        raise HTTPException(
            status_code=400,
            detail=f"sort_order 不合法: {sort_order!r}，仅支持 'asc' 或 'desc'",
        )

    filters = {}
    if pe_min is not None: filters["pe_min"] = pe_min
    if pe_max is not None: filters["pe_max"] = pe_max
    if pb_min is not None: filters["pb_min"] = pb_min
    if pb_max is not None: filters["pb_max"] = pb_max
    if mv_min is not None: filters["mv_min"] = mv_min
    if mv_max is not None: filters["mv_max"] = mv_max
    if circ_mv_min is not None: filters["circ_mv_min"] = circ_mv_min
    if circ_mv_max is not None: filters["circ_mv_max"] = circ_mv_max
    if turnover_min is not None: filters["turnover_min"] = turnover_min
    if turnover_max is not None: filters["turnover_max"] = turnover_max
    if volume_ratio_min is not None: filters["volume_ratio_min"] = volume_ratio_min
    if volume_ratio_max is not None: filters["volume_ratio_max"] = volume_ratio_max
    if dv_min is not None: filters["dv_min"] = dv_min
    if dv_max is not None: filters["dv_max"] = dv_max
    if net_inflow_min is not None: filters["net_inflow_min"] = net_inflow_min
    if name: filters["name"] = name
    if industry: filters["industry"] = industry

    return service.screen_stocks(
        trade_date=trade_date,
        filters=filters if filters else None,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )
