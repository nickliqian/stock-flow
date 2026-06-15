"""自选股 API 路由。"""

import re
from fastapi import APIRouter, Query, Path
from typing import Optional
from pydantic import BaseModel, field_validator

from ..services.watchlist import WatchlistService

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

service = WatchlistService()

_TS_CODE_PATTERN = re.compile(r"^\d{6}\.(SH|SZ)$")


class WatchlistAddRequest(BaseModel):
    ts_code: str
    group_name: str = "default"
    notes: str = ""

    @field_validator("ts_code")
    @classmethod
    def validate_ts_code(cls, v: str) -> str:
        if not _TS_CODE_PATTERN.match(v):
            raise ValueError(f"ts_code 格式无效: {v!r}，应为 6位数字.SH/SZ，如 000001.SZ")
        return v


class WatchlistUpdateRequest(BaseModel):
    group_name: Optional[str] = None
    notes: Optional[str] = None


@router.get("/")
def list_watchlist(group_name: Optional[str] = Query(None)):
    """自选股列表（支持 ?group_name=xxx 筛选）。"""
    return service.list_watchlist(group_name)


@router.post("/")
def add_to_watchlist(body: WatchlistAddRequest):
    """添加自选股，body: { ts_code, group_name?, notes? }"""
    return service.add_to_watchlist(body.ts_code, body.group_name, body.notes)


@router.delete("/{ts_code}")
def remove_from_watchlist(ts_code: str = Path(pattern=r"^\d{6}\.(SH|SZ)$")):
    """删除自选股。"""
    return service.remove_from_watchlist(ts_code)


@router.put("/{ts_code}")
def update_watchlist(ts_code: str = Path(pattern=r"^\d{6}\.(SH|SZ)$"), body: WatchlistUpdateRequest = ...):
    """更新自选股（group_name, notes）。"""
    return service.update_watchlist(ts_code, body.group_name, body.notes)


@router.get("/signals")
def get_all_signals(trade_date: Optional[str] = Query(None)):
    """所有自选股的信号汇总。"""
    return service.get_all_signals(trade_date)


@router.get("/stats")
def get_stats():
    """统计：总数、各分组数量、各 conviction 数量。"""
    return service.get_stats()


@router.get("/{ts_code}/signals")
def get_stock_signals(ts_code: str = Path(pattern=r"^\d{6}\.(SH|SZ)$")):
    """单只股票的信号详情。"""
    return service.get_stock_signals(ts_code)
