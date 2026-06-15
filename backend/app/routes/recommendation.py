"""智能荐股 API 路由。"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional

from ..utils import make_lazy

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


# ------- 模块级延迟初始化引擎实例（避免每次请求重复创建） -------


def _create_recommendation_engine():
    from ..engine.recommendation import RecommendationEngine
    return RecommendationEngine()


_recommendation_engine = make_lazy(_create_recommendation_engine)


# -----------------------------------------------------------------------
# 推荐列表 API
# -----------------------------------------------------------------------

@router.get("")
def list_recommendations(
    trade_date: Optional[str] = Query(None, description="交易日 YYYYMMDD，留空取最新"),
    min_score: float = Query(0, ge=0, le=100, description="最低综合评分过滤"),
    limit: int = Query(50, ge=1, le=500, description="返回数量"),
    category: Optional[str] = Query(None, description="推荐级别过滤: STRONG_BUY, BUY, HOLD, REDUCE, AVOID"),
):
    """获取智能荐股列表——7维度综合评分。"""
    engine = _recommendation_engine()
    return engine.get_recommendations(
        trade_date=trade_date,
        min_score=min_score,
        limit=limit,
        category=category,
    )


# -----------------------------------------------------------------------
# 单只股票推荐详情 API
# -----------------------------------------------------------------------

@router.get("/summary")
def recommendation_summary(
    trade_date: Optional[str] = Query(None, description="交易日 YYYYMMDD，留空取最新"),
):
    """获取市场级推荐概要统计。"""
    engine = _recommendation_engine()
    return engine.get_recommendation_summary(trade_date=trade_date)


@router.get("/{ts_code}")
def stock_recommendation(
    ts_code: str,
    trade_date: Optional[str] = Query(None, description="交易日 YYYYMMDD，留空取最新"),
):
    """获取单只股票的详细推荐分析。"""
    engine = _recommendation_engine()
    result = engine.get_stock_recommendation(ts_code, trade_date=trade_date)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "未找到推荐数据"))
    return result
