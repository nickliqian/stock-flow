"""策略共振引擎——汇总多个策略结果，找出被多个策略同时选中的股票。"""

import logging
from typing import Dict, Any, List, Optional

from .registry import get_all_strategies
from .data_loader import StrategyDataLoader

logger = logging.getLogger(__name__)


class ConfluenceEngine:
    """策略共振引擎：运行所有策略并计算共振评分。"""

    def __init__(self, loader: StrategyDataLoader):
        self.loader = loader

    def scan(
        self,
        trade_date: str,
        min_strategies: int = 2,
    ) -> Dict[str, Any]:
        """执行策略共振扫描。

        Args:
            trade_date: 交易日期
            min_strategies: 最少匹配策略数（默认2）

        Returns:
            包含 confluence_results 的字典
        """
        strategies = get_all_strategies()
        if not strategies:
            return {"trade_date": trade_date, "results": [], "total": 0}

        # 1. 汇总所有策略所需数据键，一次加载
        all_keys: set = set()
        for s in strategies.values():
            all_keys.update(s.required_data())
        # 总是加载 daily_basic 用于数据
        all_keys.add("daily_basic")
        data = self.loader.load(trade_date, list(all_keys))

        # 1.5 构建 ts_code -> name 映射（从 stock_basic 表）
        name_map: Dict[str, str] = {}
        try:
            basic_rows = self.loader.cache.get_stock_basic_from_db()
            if basic_rows:
                for row in basic_rows:
                    name_map[row["ts_code"]] = row["name"]
        except Exception as exc:
            logger.warning("ConfluenceEngine: failed to load stock names: %s", exc)

        # 2. 执行所有策略，构建反向索引
        stock_map: Dict[str, Dict] = {}

        for strat_name, strategy in strategies.items():
            try:
                results = strategy.check(data)
                for r in results:
                    tc = r.ts_code
                    resolved_name = name_map.get(tc, r.name or tc)
                    if tc not in stock_map:
                        stock_map[tc] = {
                            "ts_code": tc,
                            "name": resolved_name,
                            "strategies": [],
                            "best_signals": {},
                        }
                    # 更新名称（优先用 daily_basic 的名称）
                    if resolved_name and resolved_name != tc:
                        stock_map[tc]["name"] = resolved_name
                    stock_map[tc]["strategies"].append({
                        "name": strategy.name,
                        "display_name": strategy.name,
                        "icon": strategy.icon,
                        "category": strategy.category,
                        "score": r.score,
                        "reason": r.reason,
                        "signals": r.signals,
                    })
                    # 合并信号（取分数最高的策略的信号作为 best_signals）
                    if r.score > stock_map[tc]["best_signals"].get("_score", 0):
                        stock_map[tc]["best_signals"] = {**r.signals, "_score": r.score}
            except Exception as exc:
                logger.error("ConfluenceEngine: strategy '%s' failed: %s", strat_name, exc)

        # 3. 计算共振评分
        confluence_results = []
        for tc, info in stock_map.items():
            num_strategies = len(info["strategies"])
            if num_strategies < min_strategies:
                continue

            base_score = sum(s["score"] for s in info["strategies"])
            multiplier = 1 + (num_strategies - 1) * 0.3
            final_score = min(100, base_score * multiplier / num_strategies)

            # 清理 best_signals 中的内部评分键
            best_signals = {k: v for k, v in info["best_signals"].items() if not k.startswith("_")}

            confluence_results.append({
                "ts_code": tc,
                "name": info["name"],
                "confluence_score": round(final_score, 2),
                "num_strategies": num_strategies,
                "strategies": info["strategies"],
                "best_signals": best_signals,
            })

        # 按共振评分降序排序
        confluence_results.sort(key=lambda x: x["confluence_score"], reverse=True)

        return {
            "trade_date": trade_date,
            "total": len(confluence_results),
            "results": confluence_results,
        }
