"""策略选股 API 路由。"""

import logging

from fastapi import APIRouter, Query, HTTPException
from typing import Optional

from ..services.strategy import StrategyService, get_global_strategy_service
from ..engine.registry import get_all_strategies
from ..utils import make_lazy  # 修复：从共享模块导入 make_lazy，消除与 alpha.py 的重复定义

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/strategies", tags=["strategies"])

service = get_global_strategy_service()


# ------- 模块级延迟初始化引擎实例（避免每次请求重复创建） -------


def _create_intelligence_svc():
    from ..engine.intelligence import StrategyIntelligenceService
    return StrategyIntelligenceService(service.loader)

def _create_regime_detector():
    from ..engine.regime import MarketRegimeDetector
    return MarketRegimeDetector(service.cache)

def _create_correlation_engine():
    from ..engine.correlation import StrategyCorrelationEngine
    return StrategyCorrelationEngine(service.cache)

def _create_evolution_engine():
    from ..engine.strategy_evolution import StrategyEvolutionEngine
    return StrategyEvolutionEngine(service.loader, service.cache)

def _create_factor_model_engine():
    from ..engine.factor_model import FactorModelEngine
    return FactorModelEngine(service.loader, service.cache)

def _create_adaptive_weight_engine():
    from ..engine.adaptive_weight import AdaptiveWeightEngine
    return AdaptiveWeightEngine(service.cache)

def _create_institutional_radar_engine():
    from ..engine.institutional_radar import InstitutionalRadarEngine
    return InstitutionalRadarEngine(service.loader, service.cache)

def _create_sector_rotation_engine():
    from ..engine.sector_rotation import SectorRotationEngine
    return SectorRotationEngine(service.cache)

def _create_flow_intelligence_engine():
    from ..engine.flow_intelligence import FlowIntelligenceEngine
    return FlowIntelligenceEngine(service.client, service.cache)

def _create_crowding_evolution_engine():
    from ..engine.crowding_evolution import StrategyCrowdingEvolutionEngine
    return StrategyCrowdingEvolutionEngine(service.cache)

def _create_signal_effectiveness_engine():
    from ..engine.signal_effectiveness import SignalEffectivenessEngine
    return SignalEffectivenessEngine(service.cache)

def _create_signal_matrix_engine():
    from ..engine.signal_matrix import SignalMatrixEngine
    return SignalMatrixEngine(service.client, service.cache)

def _create_stock_health_engine():
    from ..engine.health import StockHealthEngine
    from ..engine.data_loader import StrategyDataLoader
    loader = StrategyDataLoader(service.client, service.cache)
    return StockHealthEngine(loader)


_get_intelligence_svc = make_lazy(_create_intelligence_svc)
_get_regime_detector = make_lazy(_create_regime_detector)
_get_correlation_engine = make_lazy(_create_correlation_engine)
_get_evolution_engine = make_lazy(_create_evolution_engine)
_get_factor_model_engine = make_lazy(_create_factor_model_engine)
_get_adaptive_weight_engine = make_lazy(_create_adaptive_weight_engine)
_get_institutional_radar_engine = make_lazy(_create_institutional_radar_engine)
_get_sector_rotation_engine = make_lazy(_create_sector_rotation_engine)
_get_flow_intelligence_engine = make_lazy(_create_flow_intelligence_engine)
_get_crowding_evolution_engine = make_lazy(_create_crowding_evolution_engine)
_get_signal_effectiveness_engine = make_lazy(_create_signal_effectiveness_engine)
_get_signal_matrix_engine = make_lazy(_create_signal_matrix_engine)
_get_stock_health_engine = make_lazy(_create_stock_health_engine)


@router.get("/")
def list_strategies():
    """获取所有可用策略列表。"""
    return {"success": True, "data": service.list_strategies()}


@router.post("/execute/{strategy_name}")
def execute_strategy(
    strategy_name: str,
    trade_date: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """执行单个策略。"""
    return service.execute_strategy(strategy_name, trade_date, limit)


@router.post("/execute-all")
def execute_all(trade_date: Optional[str] = Query(None)):
    """一次性执行所有策略。"""
    return service.execute_all(trade_date)


@router.get("/confluence")
def strategy_confluence(
    trade_date: Optional[str] = Query(None),
    min_strategies: int = Query(2, ge=2, le=10),
):
    """策略共振扫描：找出被多个策略同时选中的股票。"""
    return service.confluence_scan(trade_date, min_strategies)


@router.get("/sector-heatmap")
def strategy_sector_heatmap(trade_date: Optional[str] = Query(None)):
    """策略板块热力图：展示各行业在各策略中的触发数量。"""
    return service.sector_heatmap(trade_date)


@router.get("/backtest/{strategy_name}")
def backtest_strategy(
    strategy_name: str,
    start_date: str = Query(..., description="回测起始日期 YYYYMMDD"),
    end_date: str = Query(..., description="回测结束日期 YYYYMMDD"),
    hold_days: int = Query(5, ge=1, le=20, description="持有天数"),
    limit: int = Query(30, ge=5, le=50, description="每日选股数量"),
):
    """回测指定策略的历史表现。"""
    from ..engine.backtest import BacktestEngine
    engine = BacktestEngine(service.loader)
    return engine.run(strategy_name, start_date, end_date, hold_days, limit)


@router.get("/intelligence/health")
def strategy_health(lookback_days: int = Query(20, ge=5, le=60)):
    """获取所有策略的健康度概览。"""
    svc = _get_intelligence_svc()
    return {"success": True, "data": svc.get_strategy_health(lookback_days)}


@router.get("/intelligence/trend/{strategy_name}")
def strategy_trend(strategy_name: str, days: int = Query(30, ge=5, le=90)):
    """获取策略胜率趋势数据。"""
    svc = _get_intelligence_svc()
    return {"success": True, "data": svc.get_performance_trend(strategy_name, days)}


@router.get("/intelligence/compare")
def strategy_compare(
    strategies: str = Query(..., description="逗号分隔的策略名称"),
    days: int = Query(20, ge=5, le=60),
):
    """对比多个策略的表现。"""
    names = [s.strip() for s in strategies.split(",") if s.strip()]
    if len(names) < 2:
        raise HTTPException(status_code=400, detail="至少需要2个策略进行对比")
    if len(names) > 10:
        raise HTTPException(status_code=400, detail="最多支持10个策略对比")
    svc = _get_intelligence_svc()
    return {"success": True, "data": svc.compare_strategies(names, days)}


@router.get("/intelligence/recommend")
def strategy_recommend():
    """基于历史表现推荐最值得信赖的策略。"""
    svc = _get_intelligence_svc()
    return {"success": True, "data": svc.get_recommendation()}


@router.get("/compose")
def compose_strategies(
    strategies: str = Query(..., description="逗号分隔的策略名称或描述"),
    operator: str = Query("AND", description="逻辑运算符: AND 或 OR"),
    trade_date: Optional[str] = Query(None),
):
    """组合多个策略：通过 AND/OR 逻辑组合自定义筛选规则。"""
    from ..engine.composer import StrategyComposer
    from ..utils import get_latest_trade_date

    names = [s.strip() for s in strategies.split(",") if s.strip()]
    if not names:
        return {"success": False, "error": "请至少选择一个策略"}
    if operator not in ("AND", "OR"):
        return {"success": False, "error": "operator 必须是 AND 或 OR"}

    if not trade_date:
        trade_date = get_latest_trade_date(service.cache)

    composer = StrategyComposer(service.loader)
    result = composer.compose(trade_date, names, operator)
    return {"success": True, "data": result}


@router.get("/compose/presets")
def compose_presets():
    """获取预置的策略组合。"""
    from ..engine.composer import StrategyComposer
    return {"success": True, "data": StrategyComposer.get_presets()}


# -----------------------------------------------------------------------
# 市场状态检测 API
# -----------------------------------------------------------------------

@router.get("/regime")
def get_market_regime():
    """获取当前市场状态分析。"""
    detector = _get_regime_detector()
    return detector.detect()


@router.get("/regime/history")
def get_regime_history(limit: int = Query(20, ge=1, le=60)):
    """获取市场状态历史（最近N个交易日）。"""
    detector = _get_regime_detector()
    return detector.get_history(limit)


@router.get("/regime/recommend")
def get_regime_recommendations():
    """获取当前市场状态下的策略推荐。"""
    detector = _get_regime_detector()
    return detector.get_recommendations()


# -----------------------------------------------------------------------
# 策略相关性分析与智能配置 API
# -----------------------------------------------------------------------

@router.get("/correlation/overlap")
def strategy_overlap(trade_date: Optional[str] = Query(None)):
    """策略选股重叠度分析（Jaccard 相似系数）。"""
    engine = _get_correlation_engine()
    return engine.get_overlap_matrix(trade_date)


@router.get("/correlation/matrix")
def strategy_correlation_matrix(days: int = Query(20, ge=5, le=60)):
    """策略收益率相关性矩阵（Pearson 相关系数）。"""
    engine = _get_correlation_engine()
    return engine.get_correlation_matrix(days)


@router.get("/correlation/optimize")
def strategy_optimize(days: int = Query(20, ge=5, le=60)):
    """策略配置优化（均值方差分析）。"""
    engine = _get_correlation_engine()
    return engine.optimize_allocation(days)


@router.get("/correlation/regime")
def strategy_regime_allocation():
    """体制自适应策略配置。"""
    engine = _get_correlation_engine()
    return engine.get_regime_allocation()


@router.get("/correlation/summary")
def strategy_portfolio_summary(trade_date: Optional[str] = Query(None)):
    """策略配置综合分析仪表板。"""
    engine = _get_correlation_engine()
    return engine.get_portfolio_summary(trade_date)


# -----------------------------------------------------------------------
# 策略信号矩阵 API
# -----------------------------------------------------------------------

@router.get("/signals/matrix")
def signals_matrix(
    trade_date: Optional[str] = Query(None, description="交易日 YYYYMMDD，留空取最新"),
    min_strategies: int = Query(1, ge=1, le=10, description="最少触发策略数"),
    category: Optional[str] = Query(None, description="策略分类过滤: value/momentum/flow/event/combo"),
):
    """策略信号矩阵——统一展示所有策略的信号。"""
    engine = _get_signal_matrix_engine()
    return engine.get_matrix(
        trade_date=trade_date,
        min_strategies=min_strategies,
        category=category,
    )


# -----------------------------------------------------------------------
# 板块轮动雷达 API
# -----------------------------------------------------------------------

@router.get("/sector-rotation")
def sector_rotation_analysis(
    trade_date: Optional[str] = Query(None, description="截止日期 YYYYMMDD"),
    lookback_days: int = Query(10, ge=3, le=30, description="回看天数"),
):
    """板块轮动雷达——分析板块资金流向趋势，检测轮动信号。"""
    engine = _get_sector_rotation_engine()
    return engine.analyze(trade_date=trade_date, lookback_days=lookback_days)


@router.get("/sector-rotation/{sector_code}/stocks")
def sector_rotation_stocks(
    sector_code: str,
    trade_date: Optional[str] = Query(None),
    limit: int = Query(30, ge=5, le=100),
):
    """获取板块轮动信号板块的成分股。"""
    engine = _get_sector_rotation_engine()
    return engine.get_sector_stocks(sector_code=sector_code, trade_date=trade_date, limit=limit)


# -----------------------------------------------------------------------
# 资金流向背离分析 API
# -----------------------------------------------------------------------

@router.get("/flow-intelligence/divergence-scan")
def divergence_scan(
    trade_date: Optional[str] = Query(None),
    lookback_days: int = Query(10, ge=3, le=30),
    signal_type: str = Query("all", description="信号类型: all/bullish/bearish"),
    min_strength: float = Query(50, ge=0, le=100),
):
    """资金流向背离扫描——检测价格与资金流向的背离信号。"""
    engine = _get_flow_intelligence_engine()
    return engine.detect_divergence(trade_date=trade_date, lookback_days=lookback_days, signal_type=signal_type, min_strength=min_strength)


@router.get("/flow-intelligence/analyze/{ts_code}")
def analyze_stock_flow(
    ts_code: str,
    lookback_days: int = Query(10, ge=3, le=30),
):
    """深度分析单只股票的资金流向背离信号。"""
    engine = _get_flow_intelligence_engine()
    return engine.analyze_stock(ts_code, lookback_days=lookback_days)


# -----------------------------------------------------------------------
# 筹码穿透率 + 股权质押风险 API
# -----------------------------------------------------------------------

@router.get("/chip-analysis")
def chip_analysis(
    trade_date: Optional[str] = Query(None, description="交易日 YYYYMMDD"),
    min_pledge_ratio: float = Query(0.0, ge=0, le=100, description="最低质押比例过滤"),
    max_pledge_ratio: float = Query(60.0, ge=0, le=100, description="最高质押比例过滤"),
):
    """筹码穿透率 + 股权质押风险综合分析。"""
    from ..engine.chip_intelligence import ChipIntelligenceEngine
    engine = ChipIntelligenceEngine(service.loader)
    return {
        "success": True,
        "data": engine.analyze(
            trade_date=trade_date,
            min_pledge_ratio=min_pledge_ratio,
            max_pledge_ratio=max_pledge_ratio,
        ),
    }


# -----------------------------------------------------------------------
# 股票健康度评分 API
# -----------------------------------------------------------------------

# NOTE: /health/market/top 必须在 /health/{ts_code} 之前注册，
#       否则 "market" 会被当作 {ts_code} 匹配，导致路径冲突。

@router.get("/health/market/top")
def market_health_top(
    trade_date: Optional[str] = Query(None),
    limit: int = Query(30, ge=5, le=100),
):
    """获取全市场 TOP 健康度股票排名。"""
    from ..utils import get_latest_trade_date
    if not trade_date:
        trade_date = get_latest_trade_date(service.cache)
    engine = _get_stock_health_engine()
    result = engine.batch_score(trade_date)
    result["results"] = result.get("results", [])[:limit]
    return {"success": True, "data": result}


@router.get("/health/{ts_code}")
def stock_health(ts_code: str, trade_date: Optional[str] = Query(None)):
    """获取单只股票的综合健康度评分（0-100，5个维度）。"""
    from ..utils import get_latest_trade_date
    if not trade_date:
        trade_date = get_latest_trade_date(service.cache)
    engine = _get_stock_health_engine()
    return {"success": True, "data": engine.score(ts_code, trade_date)}


# -----------------------------------------------------------------------
# 策略自进化引擎 API
# -----------------------------------------------------------------------

@router.get("/evolution/report")
def evolution_report():
    """策略进化报告——所有策略的衰减检测和优化建议。"""
    engine = _get_evolution_engine()
    return {"success": True, "data": engine.get_evolution_report()}


@router.get("/evolution/optimize/{strategy_name}")
def optimize_strategy(
    strategy_name: str,
    start_date: str = Query(None, description="回测起始日期 YYYYMMDD"),
    end_date: str = Query(None, description="回测结束日期 YYYYMMDD"),
    hold_days: int = Query(5, ge=1, le=20),
    top_n: int = Query(30, ge=5, le=50),
):
    """策略参数优化——测试参数变体，找最优配置。"""
    engine = _get_evolution_engine()
    return {"success": True, "data": engine.optimize_strategy(
        strategy_name, start_date, end_date, hold_days, top_n
    )}


@router.get("/evolution/lifecycle/{strategy_name}")
def strategy_lifecycle(strategy_name: str):
    """策略生命周期——追踪策略的出生、成长、成熟、衰退阶段。"""
    engine = _get_evolution_engine()
    return {"success": True, "data": engine.get_strategy_lifecycle(strategy_name)}


@router.get("/evolution/decay")
def decay_detection(lookback_days: int = Query(20, ge=5, le=60)):
    """策略衰减检测——找出正在失效的策略。"""
    engine = _get_evolution_engine()
    strategies = get_all_strategies()
    results = []
    for name in strategies:
        try:
            decay = engine.detect_decay(name, lookback_days)
            results.append(decay)
        except Exception as e:
            logger.warning("Decay detection failed for %s: %s", name, e)
    results.sort(key=lambda x: x.get("decay_score", 0), reverse=True)
    return {"success": True, "data": results}


# -----------------------------------------------------------------------
# 机构动向雷达 + 策略拥挤度 API
# -----------------------------------------------------------------------

@router.get("/institutional/flow")
def institutional_flow(trade_date: str = Query(None, description="交易日 YYYYMMDD")):
    """龙虎榜机构席位净买入数据。"""
    engine = _get_institutional_radar_engine()
    if not trade_date:
        from ..utils import get_latest_trade_date
        trade_date = get_latest_trade_date(service.cache)
    return {"success": True, "data": engine.get_institutional_flow(trade_date)}


@router.get("/institutional/crowding")
def crowding_detection(
    trade_date: str = Query(None),
    min_strategies: int = Query(3, ge=2, le=10),
):
    """策略拥挤度检测。"""
    engine = _get_institutional_radar_engine()
    if not trade_date:
        from ..utils import get_latest_trade_date
        trade_date = get_latest_trade_date(service.cache)
    return {"success": True, "data": engine.detect_crowding(trade_date, min_strategies)}


@router.get("/institutional/conviction/{ts_code}")
def conviction_score(ts_code: str, trade_date: str = Query(None)):
    """综合置信度评分——策略+机构+拥挤度。"""
    engine = _get_institutional_radar_engine()
    if not trade_date:
        from ..utils import get_latest_trade_date
        trade_date = get_latest_trade_date(service.cache)
    return {"success": True, "data": engine.get_conviction_score(ts_code, trade_date)}


# -----------------------------------------------------------------------
# 量化因子模型 + 因子轮动 API
# -----------------------------------------------------------------------

@router.get("/factor-model/performance")
def factor_performance(
    trade_date: Optional[str] = Query(None),
    lookback_days: int = Query(20, ge=3, le=60),
):
    """因子表现历史——按因子分类聚合策略收益率。"""
    engine = _get_factor_model_engine()
    return {"success": True, "data": engine.get_factor_performance(trade_date, lookback_days)}


@router.get("/factor-model/momentum")
def factor_momentum(
    trade_date: Optional[str] = Query(None),
    recent_days: int = Query(5, ge=1, le=20),
    older_days: int = Query(15, ge=3, le=40),
):
    """因子动量信号——比较近期与历史表现。"""
    engine = _get_factor_model_engine()
    return {"success": True, "data": engine.get_factor_momentum(trade_date, recent_days, older_days)}


@router.get("/factor-model/regime")
def factor_regime(trade_date: Optional[str] = Query(None)):
    """当前因子轮动状态——主导因子与体制分类。"""
    engine = _get_factor_model_engine()
    return {"success": True, "data": engine.detect_factor_regime(trade_date)}


@router.get("/factor-model/rotation")
def factor_rotation(
    trade_date: Optional[str] = Query(None),
    top_factors: int = Query(2, ge=1, le=4),
    limit: int = Query(30, ge=5, le=100),
):
    """因子轮动选股——基于因子动量的综合选股。"""
    engine = _get_factor_model_engine()
    return {"success": True, "data": engine.get_rotation_picks(trade_date, top_factors, limit)}


@router.get("/factor-model/exposure/{ts_code}")
def factor_exposure(ts_code: str, trade_date: Optional[str] = Query(None)):
    """单股因子暴露度——显示某只股票在各因子中的暴露。"""
    engine = _get_factor_model_engine()
    return {"success": True, "data": engine.get_stock_factor_exposure(ts_code, trade_date)}


@router.get("/factor-model/record")
def factor_record(trade_date: Optional[str] = Query(None)):
    """记录因子表现到数据库。"""
    from ..utils import get_latest_trade_date
    engine = _get_factor_model_engine()
    if not trade_date:
        trade_date = get_latest_trade_date(service.cache)
    return {"success": True, "data": engine.record_factor_performance(trade_date)}


# -----------------------------------------------------------------------
# 策略自适应权重 API
# -----------------------------------------------------------------------

@router.get("/adaptive/weights")
def get_adaptive_weights(
    trade_date: Optional[str] = Query(None),
    lookback_days: int = Query(20, ge=5, le=60),
):
    """获取策略自适应权重。"""
    engine = _get_adaptive_weight_engine()
    return engine.calculate_weights(trade_date, lookback_days)


@router.get("/adaptive/execute")
def execute_adaptive(
    trade_date: Optional[str] = Query(None),
    limit: int = Query(50, ge=5, le=200),
):
    """执行自适应加权策略选股。"""
    engine = _get_adaptive_weight_engine()
    return engine.execute_adaptive(trade_date, limit)


@router.get("/adaptive/history")
def weight_history(
    strategy_name: Optional[str] = Query(None),
    days: int = Query(30, ge=5, le=90),
):
    """获取策略权重历史趋势。"""
    engine = _get_adaptive_weight_engine()
    return engine.get_weight_history(strategy_name, days)


@router.get("/adaptive/summary")
def adaptive_summary():
    """自适应权重综合仪表板数据。"""
    engine = _get_adaptive_weight_engine()
    return engine.get_summary()


# -----------------------------------------------------------------------
# 策略拥挤度演进 API
# -----------------------------------------------------------------------

@router.get("/crowding-evolution")
def crowding_evolution(
    trade_date: Optional[str] = Query(None),
    lookback_days: int = Query(30, ge=5, le=90),
):
    """策略拥挤度演进——追踪各策略选股宽度变化、拥挤比率趋势。"""
    engine = _get_crowding_evolution_engine()
    return engine.get_crowding_evolution(trade_date=trade_date, lookback_days=lookback_days)


@router.get("/crowding-alerts")
def crowding_alerts(trade_date: Optional[str] = Query(None)):
    """策略拥挤度告警——检测拥挤、急升、退潮等信号。"""
    engine = _get_crowding_evolution_engine()
    return engine.get_crowding_alerts(trade_date=trade_date)


@router.get("/crowding-diversity")
def crowding_diversity(
    trade_date: Optional[str] = Query(None),
    lookback_days: int = Query(30, ge=5, le=90),
):
    """策略多样性指数——追踪活跃策略数与市场因子集中度。"""
    engine = _get_crowding_evolution_engine()
    return engine.get_diversity_index(trade_date=trade_date, lookback_days=lookback_days)


@router.get("/crowding-cross")
def crowding_cross(trade_date: Optional[str] = Query(None)):
    """跨策略拥挤分析——检测多策略选股重叠。"""
    engine = _get_crowding_evolution_engine()
    return engine.get_cross_crowding(trade_date=trade_date)


# -----------------------------------------------------------------------
# 策略信号有效性追踪 API
# -----------------------------------------------------------------------

@router.get("/signal-effectiveness/distribution")
def signal_quality_distribution(
    trade_date: Optional[str] = Query(None),
    lookback_days: int = Query(20, ge=5, le=60),
):
    """信号质量分布——分析评分与实际收益的关系。"""
    engine = _get_signal_effectiveness_engine()
    return {"success": True, "data": engine.get_signal_quality_distribution(trade_date, lookback_days)}

@router.get("/signal-effectiveness/trust")
def strategy_trust_scores(lookback_days: int = Query(20, ge=5, le=60)):
    """策略信任度评分。"""
    engine = _get_signal_effectiveness_engine()
    return {"success": True, "data": engine.get_strategy_trust_scores(lookback_days)}

@router.get("/signal-effectiveness/trend/{strategy_name}")
def effectiveness_trend(strategy_name: str, days: int = Query(30, ge=5, le=90)):
    """信号有效性趋势。"""
    engine = _get_signal_effectiveness_engine()
    return {"success": True, "data": engine.get_effectiveness_trend(strategy_name, days)}

@router.get("/signal-effectiveness/trend")
def effectiveness_trend_all(days: int = Query(30, ge=5, le=90)):
    """全策略信号有效性趋势。"""
    engine = _get_signal_effectiveness_engine()
    return {"success": True, "data": engine.get_effectiveness_trend(None, days)}

@router.get("/signal-effectiveness/rebalance")
def rebalancing_recommendations(lookback_days: int = Query(20, ge=5, le=60)):
    """暴露调整建议。"""
    engine = _get_signal_effectiveness_engine()
    return {"success": True, "data": engine.get_rebalancing_recommendations(lookback_days)}

