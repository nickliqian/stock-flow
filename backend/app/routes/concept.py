"""Concept Board API routes."""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from ..services.concept import ConceptService

router = APIRouter(prefix="/api/concepts", tags=["concepts"])
service = ConceptService()

# 修复：定义 sort_by 白名单，与 ConceptService 内部校验逻辑保持一致
_VALID_SORT_FIELDS = {"pct_change", "close", "vol", "turnover_rate", "member_count", "name"}

# 修复：定义 sort_order 白名单，只允许 asc/desc
_VALID_SORT_ORDERS = {"asc", "desc"}


@router.get("")
def list_concepts(
    page: int = Query(1, description="页码"),
    page_size: int = Query(20, description="每页条数"),
    sort_by: str = Query("pct_change", description="排序字段"),
    sort_order: str = Query("desc", description="排序方向: asc/desc"),
    name: Optional[str] = Query(None, description="概念名称模糊搜索"),
):
    """概念板块列表 — 展示所有同花顺概念板块及其最新行情"""
    # 修复：在路由层校验 sort_by 和 sort_order，提前拦截非法参数
    if sort_by not in _VALID_SORT_FIELDS:
        raise HTTPException(
            status_code=400,
            detail=f"sort_by 不合法: {sort_by!r}，允许的值: {sorted(_VALID_SORT_FIELDS)}",
        )
    if sort_order.lower() not in _VALID_SORT_ORDERS:
        raise HTTPException(
            status_code=400,
            detail=f"sort_order 不合法: {sort_order!r}，仅支持 'asc' 或 'desc'",
        )

    return service.list_concepts(
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
        name=name,
    )


@router.get("/{ts_code}")
def get_concept_detail(ts_code: str):
    """概念板块详情 — 基本信息 + 近10日行情走势"""
    return service.get_concept_detail(ts_code)


@router.get("/{ts_code}/members")
def get_concept_members(ts_code: str):
    """概念板块成分股 — 成分股列表 + 基本面数据"""
    return service.get_concept_members(ts_code)
