"""Alpha 评分 & 行业轮动 API 路由。"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional

from ..services.strategy import StrategyService, get_global_strategy_service
from ..utils import make_lazy  # 修复：从共享模块导入 make_lazy，消除与 strategy.py 的重复定义

router = APIRouter(prefix="/api/alpha", tags=["alpha"])

service = get_global_strategy_service()


# ------- 模块级延迟初始化引擎实例（避免每次请求重复创建） -------


def _create_alpha_engine():
    from ..engine.alpha_scoring import AlphaScoringEngine
    return AlphaScoringEngine()

def _create_industry_rotation_engine():
    from ..engine.industry_heatmap import IndustryRotationEngine
    return IndustryRotationEngine()


_alpha_engine = make_lazy(_create_alpha_engine)
_industry_rotation_engine = make_lazy(_create_industry_rotation_engine)


# -----------------------------------------------------------------------
# Alpha 评分 API
# -----------------------------------------------------------------------

@router.get("/score")
def market_alpha_scores(
    trade_date: Optional[str] = Query(None, description="交易日 YYYYMMDD，留空取最新"),
    industry: Optional[str] = Query(None, description="行业过滤"),
    min_mv: float = Query(20, ge=0, description="最低总市值过滤（亿元）"),
    limit: int = Query(50, ge=1, le=500, description="返回数量"),
):
    """全市场 Alpha 评分排行——多因子综合评分 + 行业百分位排名。"""
    engine = _alpha_engine()
    return engine.get_market_alpha_scores(
        trade_date=trade_date,
        industry=industry,
        min_mv=min_mv,
        limit=limit,
    )


@router.get("/score/{ts_code}")
def stock_alpha_profile(ts_code: str, trade_date: Optional[str] = Query(None)):
    """单只股票 Alpha 评分画像——各因子得分、行业排名、百分位。"""
    engine = _alpha_engine()
    return engine.get_stock_alpha_profile(ts_code, trade_date=trade_date)


# -----------------------------------------------------------------------
# 行业热力图 API
# -----------------------------------------------------------------------

@router.get("/industry-heatmap")
def industry_heatmap(trade_date: Optional[str] = Query(None)):
    """行业热力图——PE/PB/Alpha/资金流向/动量综合视图。"""
    engine = _industry_rotation_engine()
    return engine.get_industry_flow_summary(trade_date=trade_date)


# -----------------------------------------------------------------------
# 同业对比 API
# -----------------------------------------------------------------------

@router.get("/peer-comparison/{ts_code}")
def peer_comparison(ts_code: str, trade_date: Optional[str] = Query(None)):
    """同业对比表——与同行业股票的多维度对比。"""
    engine = _alpha_engine()
    return engine.get_peer_comparison(ts_code, trade_date=trade_date)


# -----------------------------------------------------------------------
# 行业轮动信号 API
# -----------------------------------------------------------------------

@router.get("/rotation-signals")
def rotation_signals(
    trade_date: Optional[str] = Query(None),
    lookback_days: int = Query(10, ge=3, le=30, description="回看天数"),
):
    """行业轮动信号——检测行业资金流向的轮动趋势。"""
    engine = _industry_rotation_engine()
    return engine.get_rotation_signals(trade_date=trade_date, lookback_days=lookback_days)
