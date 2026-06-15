# [修改] 问题8：添加 sort_order 参数支持，前端无需请求 300 条即可获取净流出排行
from fastapi import APIRouter, Query
from ..services.sector import SectorService

router = APIRouter(prefix="/api/sectors", tags=["sectors"])
service = SectorService()


@router.get("")
def get_sectors(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页条数"),
    trade_date: str = Query(None, pattern=r"^\d{8}$", description="交易日期 YYYYMMDD"),
    sort_order: str = Query("desc", description="排序方向: asc（净流出TOP）/ desc（净流入TOP）"),
    sort_by: str = Query("net_inflow", description="排序字段: net_inflow / large_net"),
):
    """板块资金流向列表（分页）"""
    return service.get_sectors(trade_date=trade_date, page=page, size=size, sort_order=sort_order, sort_by=sort_by)


@router.get("/search")
def search_sectors(
    q: str = Query(..., description="搜索关键词"),
    trade_date: str = Query(None, pattern=r"^\d{8}$", description="交易日期 YYYYMMDD"),
):
    """搜索板块"""
    return service.search_sectors(q, trade_date)


@router.get("/{sector_code}/members")
def get_sector_members(
    sector_code: str,
    trade_date: str = Query(None, pattern=r"^\d{8}$", description="交易日期 YYYYMMDD"),
):
    """获取板块成分股列表及资金流向"""
    return service.get_sector_members(sector_code, trade_date)


@router.get("/{sector_code}/trend")
def get_sector_trend(
    sector_code: str,
    days: int = Query(30, ge=1, le=120, description="最近N个交易日"),
):
    """获取板块资金流向趋势（近N日净流入数据）"""
    return service.get_sector_trend(sector_code, days)
