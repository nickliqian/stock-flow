"""策略组合引擎——将多个策略通过 AND/OR 逻辑组合为自定义筛选规则。"""

import logging
from typing import Dict, Any, List, Optional

from .registry import get_all_strategies, get_strategy
from .data_loader import StrategyDataLoader

logger = logging.getLogger(__name__)

# 预置组合
COMPOSE_PRESETS = [
    {
        "name": "价值+资金共振",
        "description": "低估值且有资金关注的标的",
        "strategies": ["low_valuation_gold", "main_fund_inflow"],
        "operator": "AND",
        "icon": "💎💰",
    },
    {
        "name": "动量+事件共振",
        "description": "强势股且有事件催化",
        "strategies": ["volume_breakthrough", "consecutive_limit_up"],
        "operator": "OR",
        "icon": "🚀⚡",
    },
    {
        "name": "超跌反弹",
        "description": "KDJ超卖+MACD金叉双重确认",
        "strategies": ["kdj_oversold_rebound", "macd_golden_cross"],
        "operator": "AND",
        "icon": "📉📈",
    },
    {
        "name": "高分红防守",
        "description": "高股息+低估值+资金流入",
        "strategies": ["high_dividend", "low_valuation_gold", "main_fund_inflow"],
        "operator": "OR",
        "icon": "🛡️🏦",
    },
]


class StrategyComposer:
    """策略组合引擎：将多个策略通过 AND/OR 逻辑组合。"""

    def __init__(self, loader: StrategyDataLoader):
        self.loader = loader

    def _resolve_strategy_name(self, name_or_desc: str, strategies: Dict) -> Optional[str]:
        """将策略名称或中文描述解析为英文策略名。"""
        if name_or_desc in strategies:
            return name_or_desc
        for key, strat in strategies.items():
            if strat.description == name_or_desc:
                return key
        return None

    def compose(
        self,
        trade_date: str,
        strategy_names: List[str],
        operator: str = "AND",
    ) -> Dict[str, Any]:
        """组合多个策略。

        Args:
            trade_date: 交易日期
            strategy_names: 策略名称列表（英文名或中文描述均可）
            operator: "AND" 或 "OR"

        Returns:
            组合结果字典
        """
        strategies = get_all_strategies()

        # 解析策略名称
        resolved_names = []
        for name in strategy_names:
            resolved = self._resolve_strategy_name(name, strategies)
            if resolved:
                resolved_names.append(resolved)
            else:
                logger.warning("StrategyComposer: unknown strategy '%s', skipping", name)

        if not resolved_names:
            return {
                "trade_date": trade_date,
                "operator": operator,
                "strategy_names": strategy_names,
                "total": 0,
                "results": [],
            }

        # 汇总所有策略所需数据键，一次加载
        all_keys: set = set()
        for name in resolved_names:
            all_keys.update(strategies[name].required_data())
        all_keys.add("daily_basic")
        data = self.loader.load(trade_date, list(all_keys))

        # 加载股票名称映射
        name_map: Dict[str, str] = {}
        try:
            basic_rows = self.loader.cache.get_stock_basic_from_db()
            if basic_rows:
                for row in basic_rows:
                    name_map[row["ts_code"]] = row["name"]
        except Exception as exc:
            logger.warning("StrategyComposer: failed to load stock names: %s", exc)

        # 执行每个策略
        strategy_results: Dict[str, Dict[str, Any]] = {}
        for name in resolved_names:
            try:
                results = strategies[name].check(data)
                strategy_results[name] = {r.ts_code: r for r in results}
            except Exception as exc:
                logger.error("StrategyComposer: strategy '%s' failed: %s", name, exc)
                strategy_results[name] = {}

        # 应用 AND/OR 逻辑
        if operator == "AND":
            all_codes: set = None
            for name in resolved_names:
                codes = set(strategy_results.get(name, {}).keys())
                all_codes = codes if all_codes is None else all_codes & codes
            if all_codes is None:
                all_codes = set()
        else:  # OR
            all_codes = set()
            for results in strategy_results.values():
                all_codes |= set(results.keys())

        # 构建结果
        results = []
        for ts_code in all_codes:
            matched_strategies = []
            total_score = 0
            for name in resolved_names:
                if ts_code in strategy_results.get(name, {}):
                    r = strategy_results[name][ts_code]
                    matched_strategies.append({
                        "name": strategies[name].name,
                        "description": strategies[name].description,
                        "icon": strategies[name].icon,
                        "category": strategies[name].category,
                        "score": round(r.score, 2),
                        "reason": r.reason,
                    })
                    total_score += r.score

            avg_score = total_score / len(matched_strategies) if matched_strategies else 0
            # AND 组合加分：匹配策略越多，分数越高
            if operator == "AND" and len(matched_strategies) > 1:
                avg_score = min(100, avg_score * (1 + (len(matched_strategies) - 1) * 0.2))

            stock_name = name_map.get(ts_code, ts_code)

            results.append({
                "ts_code": ts_code,
                "name": stock_name,
                "composition_score": round(avg_score, 2),
                "matched_strategies": matched_strategies,
                "num_matched": len(matched_strategies),
            })

        results.sort(key=lambda x: x["composition_score"], reverse=True)

        return {
            "trade_date": trade_date,
            "operator": operator,
            "strategy_names": resolved_names,
            "total": len(results),
            "results": results[:100],
        }

    @staticmethod
    def get_presets() -> List[Dict[str, Any]]:
        """返回预置组合列表。"""
        return COMPOSE_PRESETS
