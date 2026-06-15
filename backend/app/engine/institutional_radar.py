"""机构动向雷达 + 策略拥挤度检测引擎。

检测龙虎榜机构席位动向、策略拥挤度风险、
并提供策略+机构+拥挤度三维度综合置信度评分。
"""

import logging
import json
import math
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import pandas as pd

from ..engine.registry import get_all_strategies, load_all_strategies
from ..engine.data_loader import StrategyDataLoader
from ..cache import CacheService

logger = logging.getLogger(__name__)


class InstitutionalRadarEngine:
    """机构动向雷达 + 策略拥挤度检测引擎。"""

    def __init__(self, loader: StrategyDataLoader, cache: CacheService):
        self.loader = loader
        self.cache = cache

    # ------------------------------------------------------------------
    # 机构动向
    # ------------------------------------------------------------------
    def get_institutional_flow(self, trade_date: str) -> Dict:
        """获取龙虎榜机构席位净买入数据。

        Uses top_inst API from Tushare. Filter exalter=='机构专用'.
        Returns: {stocks: [...], summary: {...}}
        """
        try:
            df = self.loader.client._call_with_retry(
                self.loader.client.pro.top_inst, trade_date=trade_date
            )
        except Exception as exc:
            logger.warning("top_inst load failed: %s", exc)
            df = None

        if df is None or df.empty:
            return {
                "stocks": [],
                "summary": {
                    "total_stocks": 0,
                    "total_inst_trades": 0,
                    "bullish_count": 0,
                    "bearish_count": 0,
                    "total_net_buy": 0,
                },
                "trade_date": trade_date,
            }

        # Filter institutional seats only
        inst_df = df[df["exalter"].str.contains("机构专用", na=False)]
        if inst_df.empty:
            return {
                "stocks": [],
                "summary": {
                    "total_stocks": 0,
                    "total_inst_trades": 0,
                    "bullish_count": 0,
                    "bearish_count": 0,
                    "total_net_buy": 0,
                },
                "trade_date": trade_date,
            }

        # Aggregate by stock
        stocks = []
        for ts_code, group in inst_df.groupby("ts_code"):
            total_buy = group["buy"].sum() if "buy" in group.columns else 0
            total_sell = group["sell"].sum() if "sell" in group.columns else 0
            net = total_buy - total_sell
            inst_count = len(group)
            reasons = (
                ", ".join(group["reason"].dropna().unique()[:3])
                if "reason" in group.columns
                else ""
            )

            stocks.append({
                "ts_code": ts_code,
                "net_buy": round(float(net), 2),
                "total_buy": round(float(total_buy), 2),
                "total_sell": round(float(total_sell), 2),
                "inst_count": inst_count,
                "reasons": reasons,
                "signal": "bullish" if net > 0 else "bearish" if net < 0 else "neutral",
            })

        stocks.sort(key=lambda x: abs(x["net_buy"]), reverse=True)

        bullish_count = sum(1 for s in stocks if s["signal"] == "bullish")
        bearish_count = sum(1 for s in stocks if s["signal"] == "bearish")

        return {
            "stocks": stocks,
            "summary": {
                "total_stocks": len(stocks),
                "total_inst_trades": len(inst_df),
                "bullish_count": bullish_count,
                "bearish_count": bearish_count,
                "total_net_buy": round(sum(s["net_buy"] for s in stocks), 2),
            },
            "trade_date": trade_date,
        }

    # ------------------------------------------------------------------
    # 策略拥挤度检测
    # ------------------------------------------------------------------
    def detect_crowding(self, trade_date: str, min_strategies: int = 3) -> Dict:
        """检测策略拥挤度——哪些股票被过多策略选中。

        Crowding risk: stocks selected by N+ strategies may be overcrowded.
        Returns: {crowded_stocks: [...], summary: {...}}
        """
        load_all_strategies()
        strategies = get_all_strategies()

        # Collect all required data keys across strategies
        all_keys = set()
        for name, strategy in strategies.items():
            all_keys.update(strategy.required_data())
        
        # Load all data once
        shared_data = self.loader.load(trade_date, list(all_keys))

        # Execute all strategies and build stock->strategies mapping
        stock_strategies = {}  # ts_code -> [strategy_info]

        for name, strategy in strategies.items():
            try:
                required = strategy.required_data()
                data = {k: v for k, v in shared_data.items() if k in required}
                results = strategy.check(data)
                for r in results:
                    if r.ts_code not in stock_strategies:
                        stock_strategies[r.ts_code] = []
                    stock_strategies[r.ts_code].append({
                        "name": name,
                        "score": r.score,
                        "category": strategy.category,
                        "icon": strategy.icon,
                        "description": strategy.description,
                    })
            except Exception as exc:
                logger.warning("Crowding check failed for %s: %s", name, exc)

        # Filter stocks with min_strategies or more
        crowded = []
        for ts_code, strats in stock_strategies.items():
            if len(strats) >= min_strategies:
                total_score = sum(s["score"] for s in strats)
                avg_score = total_score / len(strats)
                categories = list(set(s["category"] for s in strats))

                crowding_risk = (
                    "high" if len(strats) >= 6
                    else "medium" if len(strats) >= 4
                    else "low"
                )

                crowded.append({
                    "ts_code": ts_code,
                    "strategy_count": len(strats),
                    "total_score": round(total_score, 1),
                    "avg_score": round(avg_score, 1),
                    "strategies": strats,
                    "categories": categories,
                    "crowding_risk": crowding_risk,
                })

        crowded.sort(key=lambda x: x["strategy_count"], reverse=True)

        high_risk = sum(1 for c in crowded if c["crowding_risk"] == "high")
        medium_risk = sum(1 for c in crowded if c["crowding_risk"] == "medium")

        return {
            "crowded_stocks": crowded,
            "summary": {
                "total_analyzed": len(stock_strategies),
                "crowded_count": len(crowded),
                "high_risk": high_risk,
                "medium_risk": medium_risk,
                "min_strategies": min_strategies,
            },
            "trade_date": trade_date,
        }

    # ------------------------------------------------------------------
    # 综合置信度评分
    # ------------------------------------------------------------------
    def get_conviction_score(self, ts_code: str, trade_date: str) -> Dict:
        """综合置信度评分——结合策略信号 + 机构动向 + 拥挤度。

        conviction = strategy_alignment(40%) + institutional_flow(30%) + crowding_adjustment(30%)
        """
        # 1. Strategy alignment score — batch load all strategies once
        load_all_strategies()
        strategies = get_all_strategies()
        strategy_hits = []

        # Collect all required data keys across strategies
        all_keys = set()
        for name, strategy in strategies.items():
            all_keys.update(strategy.required_data())
        
        # Load all data once
        shared_data = self.loader.load(trade_date, list(all_keys))

        for name, strategy in strategies.items():
            try:
                # Filter data to only what this strategy needs
                required = strategy.required_data()
                data = {k: v for k, v in shared_data.items() if k in required}
                results = strategy.check(data)
                for r in results:
                    if r.ts_code == ts_code:
                        strategy_hits.append({
                            "name": name,
                            "score": r.score,
                            "category": strategy.category,
                            "icon": strategy.icon,
                            "description": strategy.description,
                        })
                        break
            except Exception:
                pass

        if strategy_hits:
            strategy_score = min(
                100,
                len(strategy_hits) * 10
                + sum(h["score"] for h in strategy_hits) / len(strategy_hits),
            )
        else:
            strategy_score = 10  # no signals at all

        # 2. Institutional flow score
        inst_flow = self.get_institutional_flow(trade_date)
        inst_score = 50  # neutral default
        inst_detail = None
        for s in inst_flow.get("stocks", []):
            if s["ts_code"] == ts_code:
                if s["net_buy"] > 1000:
                    inst_score = 90
                elif s["net_buy"] > 500:
                    inst_score = 75
                elif s["net_buy"] > 0:
                    inst_score = 60
                elif s["net_buy"] > -500:
                    inst_score = 40
                else:
                    inst_score = 20
                inst_detail = s
                break

        # 3. Crowding adjustment
        crowding = self.detect_crowding(trade_date, min_strategies=2)
        crowding_score = 50  # neutral
        crowding_detail = None
        for c in crowding.get("crowded_stocks", []):
            if c["ts_code"] == ts_code:
                n = c["strategy_count"]
                if n <= 2:
                    crowding_score = 40
                elif n <= 4:
                    crowding_score = 70  # sweet spot
                elif n <= 6:
                    crowding_score = 60  # still good but crowded
                else:
                    crowding_score = 40  # too crowded
                crowding_detail = c
                break

        # Composite score
        conviction = round(
            strategy_score * 0.4 + inst_score * 0.3 + crowding_score * 0.3, 1
        )

        # Grade
        if conviction >= 80:
            grade = "A+"
        elif conviction >= 70:
            grade = "A"
        elif conviction >= 60:
            grade = "B+"
        elif conviction >= 50:
            grade = "B"
        elif conviction >= 40:
            grade = "C+"
        else:
            grade = "C"

        return {
            "ts_code": ts_code,
            "conviction_score": conviction,
            "grade": grade,
            "components": {
                "strategy": {
                    "score": round(strategy_score, 1),
                    "weight": 0.4,
                    "hits": len(strategy_hits),
                    "details": strategy_hits,
                },
                "institutional": {
                    "score": round(inst_score, 1),
                    "weight": 0.3,
                    "detail": inst_detail,
                },
                "crowding": {
                    "score": round(crowding_score, 1),
                    "weight": 0.3,
                    "detail": crowding_detail,
                },
            },
            "trade_date": trade_date,
        }
