"""Portfolio Constructor API routes"""

import logging
import threading

from fastapi import APIRouter, Query
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

_engine = None
_engine_lock = threading.Lock()


def _get_engine():
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                from ..engine.portfolio_constructor import PortfolioConstructorEngine
                _engine = PortfolioConstructorEngine()
    return _engine


@router.get("/candidates")
def get_candidates(
    trade_date: Optional[str] = None,
    min_strategies: int = Query(2, ge=1, le=10),
):
    """获取组合构建候选股票池"""
    try:
        engine = _get_engine()
        candidates = engine.get_candidate_stocks(trade_date, min_strategies)
        return {"success": True, "data": candidates, "total": len(candidates)}
    except Exception as e:
        logger.error("获取组合候选股票失败: %s", e, exc_info=True)
        return {"success": False, "error": "获取候选股票失败，请稍后重试", "data": [], "total": 0}


@router.get("/optimize")
def optimize_portfolio(
    trade_date: Optional[str] = None,
    method: str = Query("mean_variance"),
    max_stocks: int = Query(15, ge=3, le=30),
    max_sector_pct: float = Query(0.30, ge=0.10, le=0.50),
    min_strategies: int = Query(2, ge=1, le=10),
):
    """优化组合配置"""
    try:
        engine = _get_engine()
        candidates = engine.get_candidate_stocks(trade_date, min_strategies)
        portfolio = engine.optimize_portfolio(candidates, method, max_stocks, max_sector_pct)
        analysis = engine.analyze_portfolio(portfolio)
        return {
            "success": True,
            "data": {
                "portfolio": portfolio,
                "analysis": analysis,
                "method": method,
                "candidate_count": len(candidates),
            },
        }
    except Exception as e:
        logger.error("优化组合配置失败: %s", e, exc_info=True)
        return {"success": False, "error": "优化组合配置失败，请稍后重试"}


@router.get("/compare")
def compare_portfolios(
    trade_date: Optional[str] = None,
    max_stocks: int = Query(15, ge=3, le=30),
    min_strategies: int = Query(2, ge=1, le=10),
):
    """对比多种优化方法"""
    try:
        engine = _get_engine()
        candidates = engine.get_candidate_stocks(trade_date, min_strategies)
        results = engine.compare_portfolios(candidates)
        return {"success": True, "data": results, "candidate_count": len(candidates)}
    except Exception as e:
        logger.error("对比组合失败: %s", e, exc_info=True)
        return {"success": False, "error": "对比组合失败，请稍后重试"}


@router.get("/attribution")
def get_attribution(
    trade_date: Optional[str] = None,
    method: str = Query("mean_variance"),
    max_stocks: int = Query(15, ge=3, le=30),
    min_strategies: int = Query(2, ge=1, le=10),
):
    """绩效归因分析"""
    try:
        engine = _get_engine()
        candidates = engine.get_candidate_stocks(trade_date, min_strategies)
        portfolio = engine.optimize_portfolio(candidates, method, max_stocks)
        attribution = engine.get_attribution(portfolio)
        return {"success": True, "data": attribution}
    except Exception as e:
        logger.error("绩效归因分析失败: %s", e, exc_info=True)
        return {"success": False, "error": "绩效归因分析失败，请稍后重试"}
