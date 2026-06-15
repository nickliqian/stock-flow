"""策略信号矩阵引擎——统一展示所有策略的信号。"""

import logging
from typing import Dict, Any, List, Optional

from .base import BaseStrategy
from .registry import get_all_strategies
from .data_loader import StrategyDataLoader
from ..clients.tushare import TuShareClient
from ..cache import CacheService
from ..utils import get_latest_trade_date

logger = logging.getLogger(__name__)


class SignalMatrixEngine:
    """策略信号矩阵——为给定交易日执行所有策略，构建 Stock × Strategy 信号矩阵。"""

    def __init__(self, client: TuShareClient, cache: CacheService):
        self.client = client
        self.cache = cache
        self.loader = StrategyDataLoader(client, cache)

    def get_matrix(
        self,
        trade_date: str = None,
        min_strategies: int = 1,
        category: str = None,
    ) -> Dict[str, Any]:
        """构建信号矩阵。

        Returns:
            {
                "trade_date": "20260612",
                "strategies": [{name, category, icon, description, pick_count, avg_score}],
                "stocks": [{ts_code, name, industry, total_score, strategy_count,
                            signals: {strategy_name: {score, reason}}}],
                "summary": {total_stocks, avg_strategies_per_stock, max_strategies,
                            strategy_distribution}
            }
        """
        if trade_date is None:
            trade_date = get_latest_trade_date(self.cache)

        # Get all registered strategies
        all_strategies = get_all_strategies()
        strategy_list: List[BaseStrategy] = list(all_strategies.values())
        if category:
            strategy_list = [s for s in strategy_list if s.category == category]

        # Collect all required data keys
        all_keys: set = set()
        for strategy in strategy_list:
            all_keys.update(strategy.required_data())

        # Load data once
        data = self.loader.load(trade_date, list(all_keys))
        if not data:
            return {"trade_date": trade_date, "strategies": [], "stocks": [], "summary": {}}

        # Execute each strategy and build results
        strategy_results: Dict[str, Dict[str, Any]] = {}  # {strategy_name: {ts_code: StrategyResult}}
        strategy_info: List[Dict[str, Any]] = []

        for strategy in strategy_list:
            try:
                results = strategy.check(data)
                results_dict = {r.ts_code: r for r in results}
                strategy_results[strategy.name] = results_dict
                strategy_info.append({
                    "name": strategy.name,
                    "category": strategy.category,
                    "icon": strategy.icon,
                    "description": strategy.description,
                    "pick_count": len(results),
                    "avg_score": (
                        round(sum(r.score for r in results) / len(results), 1)
                        if results else 0
                    ),
                })
            except Exception as exc:
                logger.error("Signal matrix: strategy '%s' failed: %s", strategy.name, exc)

        # Build stock-centric view: for each stock, which strategies triggered?
        stock_signals: Dict[str, Dict[str, Any]] = {}  # {ts_code: {strategy_name: StrategyResult}}
        for sname, results_dict in strategy_results.items():
            for ts_code, result in results_dict.items():
                if ts_code not in stock_signals:
                    stock_signals[ts_code] = {}
                stock_signals[ts_code][sname] = result

        # Get stock names from loaded data
        name_map: Dict[str, str] = {}
        industry_map: Dict[str, str] = {}
        try:
            stock_basic_df = data.get("stock_basic")
            if stock_basic_df is not None and not stock_basic_df.empty:
                for _, row in stock_basic_df.iterrows():
                    name_map[row.get("ts_code", "")] = row.get("name", "")
                    industry_map[row.get("ts_code", "")] = row.get("industry", "")
        except Exception:
            pass

        # Fallback: try from database directly
        if not name_map:
            try:
                from ..models import SessionLocal, StockBasic
                session = SessionLocal()
                try:
                    for r in session.query(StockBasic.ts_code, StockBasic.name, StockBasic.industry).all():
                        name_map[r.ts_code] = r.name or ""
                        industry_map[r.ts_code] = r.industry or ""
                finally:
                    session.close()
            except Exception:
                pass

        # Build stock list with signals
        stocks = []
        for ts_code, signals in stock_signals.items():
            strategy_count = len(signals)
            if strategy_count < min_strategies:
                continue
            total_score = sum(r.score for r in signals.values()) / strategy_count
            stocks.append({
                "ts_code": ts_code,
                "name": name_map.get(ts_code, ts_code),
                "industry": industry_map.get(ts_code, ""),
                "total_score": round(total_score, 1),
                "strategy_count": strategy_count,
                "signals": {
                    sname: {"score": round(r.score, 1), "reason": r.reason}
                    for sname, r in signals.items()
                },
            })

        # Sort by strategy_count desc, then total_score desc
        stocks.sort(key=lambda x: (-x["strategy_count"], -x["total_score"]))

        # Summary statistics
        strategy_dist: Dict[str, int] = {}
        for s in stocks:
            n = s["strategy_count"]
            strategy_dist[str(n)] = strategy_dist.get(str(n), 0) + 1

        total_stocks_with_signals = len(stocks)
        avg_strategies = (
            sum(s["strategy_count"] for s in stocks) / total_stocks_with_signals
            if total_stocks_with_signals > 0 else 0
        )
        max_strategies = max((s["strategy_count"] for s in stocks), default=0)

        return {
            "trade_date": trade_date,
            "strategies": strategy_info,
            "stocks": stocks,
            "summary": {
                "total_stocks": total_stocks_with_signals,
                "avg_strategies_per_stock": round(avg_strategies, 1),
                "max_strategies": max_strategies,
                "strategy_distribution": strategy_dist,
            },
        }
