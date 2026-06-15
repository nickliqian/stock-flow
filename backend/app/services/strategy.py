# [修改] 问题1+6：使用 BaseService 基类，共享全局单例 TuShareClient 和 CacheService
"""策略服务层——协调策略引擎的加载与执行。"""

import logging
from typing import Dict, Any, List, Optional

from .base import BaseService, get_global_client, get_global_cache
from ..engine.registry import get_all_strategies, get_strategy, load_all_strategies
from ..engine.data_loader import StrategyDataLoader
from ..engine.confluence import ConfluenceEngine

logger = logging.getLogger(__name__)


class StrategyService(BaseService):
    """提供策略列表、单策略执行、全策略执行等 API 服务。"""

    def __init__(self, cache=None, client=None):
        super().__init__(cache=cache, client=client)
        self.loader = StrategyDataLoader(self.client, self.cache)
        load_all_strategies()

    # ------------------------------------------------------------------
    # public
    # ------------------------------------------------------------------
    def list_strategies(self) -> List[Dict]:
        """返回所有已注册策略的元信息。"""
        strategies = get_all_strategies()
        return [
            {
                "name": s.name,
                "description": s.description,
                "category": s.category,
                "icon": s.icon,
                "data_required": s.required_data(),
            }
            for s in strategies.values()
        ]

    def execute_strategy(
        self,
        strategy_name: str,
        trade_date: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """执行单个策略并返回结果。"""
        strategy = get_strategy(strategy_name)
        if not strategy:
            return {"success": False, "error": f"未找到策略：{strategy_name}"}

        if not trade_date:
            from ..utils import get_latest_trade_date
            trade_date = get_latest_trade_date(self.cache)

        data_keys = strategy.required_data()
        data = self.loader.load(trade_date, data_keys)

        results = strategy.check(data)
        results.sort(key=lambda r: r.score, reverse=True)
        results = results[:limit]

        # Record snapshot for intelligence tracking
        try:
            from ..engine.intelligence import StrategyIntelligenceService
            intel = StrategyIntelligenceService(self.loader)
            scores = [r.score for r in results]
            avg_s = sum(scores) / len(scores) if scores else 0
            max_s = max(scores) if scores else 0
            intel.record_snapshot(trade_date, strategy_name, results, avg_s, max_s)
            # Record performance (forward returns) - async-friendly
            intel.record_performance(trade_date, strategy_name, results)
        except Exception as exc:
            logger.warning("Failed to record strategy snapshot: %s", exc)

        return {
            "success": True,
            "data": {
                "strategy": {
                    "name": strategy.name,
                    "description": strategy.description,
                    "category": strategy.category,
                    "icon": strategy.icon,
                },
                "trade_date": trade_date,
                "total_matches": len(results),
                "results": [r.to_dict() for r in results],
            },
        }

    def execute_all(self, trade_date: Optional[str] = None, record: bool = True) -> Dict[str, Any]:
        """一次性执行所有策略（共享数据加载）。

        Args:
            trade_date: 交易日期，留空取最新。
            record: 是否记录快照/性能。为 False 时只读执行（用于热力图等只读场景）。
        """
        strategies = get_all_strategies()
        if not trade_date:
            from ..utils import get_latest_trade_date
            trade_date = get_latest_trade_date(self.cache)

        # 汇总所有策略所需数据键，去重后一次加载
        all_keys: set = set()
        for s in strategies.values():
            all_keys.update(s.required_data())
        data = self.loader.load(trade_date, list(all_keys))

        results: Dict[str, Any] = {}
        for name, strategy in strategies.items():
            try:
                sr = strategy.check(data)
                sr.sort(key=lambda r: r.score, reverse=True)

                # Record snapshot / performance only when requested
                if record:
                    try:
                        from ..engine.intelligence import StrategyIntelligenceService
                        intel = StrategyIntelligenceService(self.loader)
                        scores = [r.score for r in sr]
                        avg_s = sum(scores) / len(scores) if scores else 0
                        max_s = max(scores) if scores else 0
                        intel.record_snapshot(trade_date, name, sr, avg_s, max_s)
                        intel.record_performance(trade_date, name, sr)
                    except Exception:
                        pass

                results[name] = {
                    "name": strategy.name,
                    "description": strategy.description,
                    "category": strategy.category,
                    "icon": strategy.icon,
                    "total_matches": len(sr),
                    "results": [r.to_dict() for r in sr[:30]],
                }
            except Exception as exc:
                logger.error("Strategy '%s' execution failed: %s", name, exc, exc_info=True)
                results[name] = {"error": "策略执行失败，请稍后重试"}

        return {
            "success": True,
            "data": {
                "trade_date": trade_date,
                "strategies": results,
            },
        }

    def confluence_scan(
        self,
        trade_date: Optional[str] = None,
        min_strategies: int = 2,
    ) -> Dict[str, Any]:
        """策略共振扫描：找出被多个策略同时选中的股票。"""
        if not trade_date:
            from ..utils import get_latest_trade_date
            trade_date = get_latest_trade_date(self.cache)

        engine = ConfluenceEngine(self.loader)
        result = engine.scan(trade_date, min_strategies)
        return {
            "success": True,
            "data": result,
        }

    def sector_heatmap(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """策略板块热力图：展示各行业在各策略中的触发数量。"""
        if not trade_date:
            from ..utils import get_latest_trade_date
            trade_date = get_latest_trade_date(self.cache)

        # 执行所有策略（只读，不写入快照/性能记录）
        all_result = self.execute_all(trade_date, record=False)
        if not all_result.get("success"):
            return {"success": False, "error": all_result.get("error", "策略执行失败")}

        strategies_data = all_result.get("data", {}).get("strategies", {})

        # 查询 stock_basic 获取每只股票的 industry
        from ..models import SessionLocal, StockBasic
        stock_industry: Dict[str, str] = {}
        try:
            with SessionLocal() as session:
                rows = session.query(StockBasic.ts_code, StockBasic.industry).all()
                stock_industry = {r.ts_code: r.industry or "未知" for r in rows}
        except Exception as exc:
            logger.error("sector_heatmap: failed to load stock_basic: %s", exc)

        # 按 industry 聚合计数
        sector_stats: Dict[str, Dict[str, int]] = {}
        strategy_meta = []

        for strat_name, strat_data in strategies_data.items():
            if "error" in strat_data or "results" not in strat_data:
                continue

            strategy_meta.append({
                "name": strat_data.get("name", strat_name),
                "description": strat_data.get("description", ""),
                "category": strat_data.get("category", ""),
                "icon": strat_data.get("icon", ""),
            })

            for result in strat_data.get("results", []):
                ts_code = result.get("ts_code", "")
                industry = stock_industry.get(ts_code, "未知")
                if industry not in sector_stats:
                    sector_stats[industry] = {"industry": industry, "total": 0}
                sector_stats[industry]["total"] += 1
                sector_stats[industry][strat_name] = sector_stats[industry].get(strat_name, 0) + 1

        # 排序取 top 30
        sectors = sorted(sector_stats.values(), key=lambda x: x["total"], reverse=True)[:30]

        return {
            "success": True,
            "data": {
                "trade_date": trade_date,
                "sectors": sectors,
                "strategies": strategy_meta,
            },
        }
