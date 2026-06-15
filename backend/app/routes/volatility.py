"""波动率聚类与风险分区 API 路由。"""

from fastapi import APIRouter, Query
from typing import Optional

from ..utils import make_lazy

router = APIRouter(prefix="/api/volatility", tags=["波动率聚类"])


# ------- 模块级延迟初始化引擎实例（避免每次请求重复创建） -------


def _create_volatility_engine():
    from ..engine.volatility_clustering import VolatilityClusteringEngine
    return VolatilityClusteringEngine()


_volatility_engine = make_lazy(_create_volatility_engine)


# -----------------------------------------------------------------------
# 全市场波动率聚类
# -----------------------------------------------------------------------

@router.get("/market")
def get_market_volatility(trade_date: Optional[str] = Query(None, description="交易日 YYYYMMDD，留空取最新")):
    """获取全市场波动率聚类分析 —— 风险分区分布、行业波动率汇总、高波动股票排名。"""
    engine = _volatility_engine()
    return engine.compute_market_volatility(trade_date)


# -----------------------------------------------------------------------
# 单股波动率详情
# -----------------------------------------------------------------------

@router.get("/stock/{ts_code}")
def get_stock_volatility(ts_code: str):
    """获取单股波动率详情 —— 年化波动率、风险分区、价格序列、日收益率、全市场百分位。"""
    engine = _volatility_engine()
    return engine.get_stock_detail(ts_code)


# -----------------------------------------------------------------------
# 板块风险分布
# -----------------------------------------------------------------------

@router.get("/sectors")
def get_sector_risk_summary():
    """获取板块风险分布 —— 按概念板块聚合的平均波动率、高/低风险股票数量。"""
    engine = _volatility_engine()
    return engine.get_sector_risk_summary()
