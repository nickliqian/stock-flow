"""量化因子模型 + 因子轮动引擎。

将所有策略归类为5大因子（价值/动量/资金/事件/组合），
追踪因子表现，检测轮动信号，基于因子动量构建轮动策略。

创新点：市面上没有个人股票工具做「因子级轮动分析」，
这是将机构量化的 Smart Beta 因子投资方法论平民化。
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict

import pandas as pd

from .registry import get_all_strategies, load_all_strategies
from ..models import SessionLocal, FactorPerformance, StrategyPerformance, StockBasic
from ..utils import get_latest_trade_date, get_last_n_trade_dates

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 因子分类映射：strategy_name -> factor_name
# ------------------------------------------------------------------
STRATEGY_TO_FACTOR: Dict[str, str] = {
    # 价值因子
    "low_valuation_gold": "value",
    "high_dividend": "value",
    "value_fund_resonance": "value",
    "broken_net_gold": "value",
    # 动量因子
    "volume_breakthrough": "momentum",
    "ma_alignment": "momentum",
    "trend_volume_resonance": "momentum",
    "volume_anomaly": "momentum",
    "oversold_bounce": "momentum",
    "kdj_oversold_rebound": "momentum",
    "macd_golden_cross": "momentum",
    # 资金因子
    "main_fund_inflow": "flow",
    "margin_fund_convergence": "flow",
    "smart_money_tracker": "flow",
    "flow_divergence": "flow",
    "margin_growth": "flow",
    "sector_rotation": "flow",
    # 事件因子
    "consecutive_limit_up": "event",
    "limit_up_reseal": "event",
    "block_trade_premium": "event",
    # 组合因子
    "chip_pledge_strategy": "combo",
}

FACTOR_META: Dict[str, Dict[str, str]] = {
    "value": {
        "name": "价值因子",
        "icon": "💎",
        "color": "#1890ff",
        "description": "低估值、高股息、破净等价值型策略",
    },
    "momentum": {
        "name": "动量因子",
        "icon": "🚀",
        "color": "#52c41a",
        "description": "趋势、均线、放量突破等动量型策略",
    },
    "flow": {
        "name": "资金因子",
        "icon": "💰",
        "color": "#faad14",
        "description": "主力资金、融资、聪明钱等资金流向策略",
    },
    "event": {
        "name": "事件因子",
        "icon": "🔥",
        "color": "#f5222d",
        "description": "涨停板、大宗交易等事件驱动策略",
    },
    "combo": {
        "name": "组合因子",
        "icon": "🧩",
        "color": "#722ed1",
        "description": "质押、组合等特殊策略",
    },
}

# 因子轮动状态
FACTOR_REGIMES = {
    "VALUE_DOMINANT": {"label": "价值主导", "icon": "💎", "color": "#1890ff",
                       "desc": "价值因子表现强势，低估值高股息策略领先"},
    "MOMENTUM_DOMINANT": {"label": "动量主导", "icon": "🚀", "color": "#52c41a",
                          "desc": "动量因子表现强势，趋势跟踪策略领先"},
    "FLOW_DOMINANT": {"label": "资金主导", "icon": "💰", "color": "#faad14",
                      "desc": "资金因子表现强势，主力资金策略领先"},
    "EVENT_DOMINANT": {"label": "事件主导", "icon": "🔥", "color": "#f5222d",
                       "desc": "事件因子表现强势，事件驱动策略领先"},
    "BALANCED": {"label": "均衡", "icon": "⚖️", "color": "#8c8c8c",
                 "desc": "各因子表现均衡，无明显轮动信号"},
}


class FactorModelEngine:
    """量化因子模型 + 因子轮动引擎。"""

    def __init__(self, loader=None, cache=None):
        """
        Args:
            loader: StrategyDataLoader 实例（可选，用于执行策略获取选股数据）
            cache: CacheService 实例（兼容旧接口，因子模型直接读 DB）
        """
        self.loader = loader
        self.cache = cache
        load_all_strategies()

    # ------------------------------------------------------------------
    # 1. 因子表现追踪
    # ------------------------------------------------------------------
    def get_factor_performance(self, trade_date: str = None, lookback_days: int = 20) -> Dict[str, Any]:
        """获取各因子的历史表现。

        数据源：strategy_performance 表（策略推荐股票的后续收益率）。
        按策略分类聚合，计算每个因子的平均收益率和胜率。

        Returns:
            {
                "trade_date": "20260612",
                "lookback_days": 20,
                "factors": {
                    "value": {avg_return_1d, avg_return_5d, win_rate, stock_count, strategies, ...},
                    ...
                }
            }
        """
        if trade_date is None:
            trade_date = get_latest_trade_date(self.cache) if hasattr(self, 'cache') else None
            if trade_date is None:
                trade_date = datetime.now().strftime("%Y%m%d")

        dates = get_last_n_trade_dates(trade_date, lookback_days)
        dates.append(trade_date)
        dates = sorted(set(dates))

        if not dates:
            return {"trade_date": trade_date, "lookback_days": lookback_days, "factors": {}}

        start_date = dates[0]
        end_date = dates[-1]

        # Query strategy_performance for the date range
        session = SessionLocal()
        try:
            rows = session.query(
                StrategyPerformance.trade_date,
                StrategyPerformance.strategy_name,
                StrategyPerformance.ts_code,
                StrategyPerformance.entry_score,
                StrategyPerformance.ret_1d,
                StrategyPerformance.ret_3d,
                StrategyPerformance.ret_5d,
            ).filter(
                StrategyPerformance.trade_date >= start_date,
                StrategyPerformance.trade_date <= end_date,
            ).all()
        finally:
            session.close()

        # Group by factor category
        factor_data: Dict[str, Dict[str, List]] = {
            f: {"ret_1d": [], "ret_5d": [], "scores": [], "wins": 0, "total": 0, "strategies": set()}
            for f in FACTOR_META
        }

        for row in rows:
            factor = STRATEGY_TO_FACTOR.get(row.strategy_name, "combo")
            fd = factor_data[factor]
            fd["strategies"].add(row.strategy_name)
            fd["total"] += 1
            fd["scores"].append(row.entry_score or 0)

            if row.ret_1d is not None:
                fd["ret_1d"].append(row.ret_1d)
                if row.ret_1d > 0:
                    fd["wins"] += 1
            if row.ret_5d is not None:
                fd["ret_5d"].append(row.ret_5d)

        # Compute aggregates
        factors = {}
        for fname, fd in factor_data.items():
            meta = FACTOR_META[fname]
            avg_1d = sum(fd["ret_1d"]) / len(fd["ret_1d"]) if fd["ret_1d"] else 0
            avg_5d = sum(fd["ret_5d"]) / len(fd["ret_5d"]) if fd["ret_5d"] else 0
            avg_score = sum(fd["scores"]) / len(fd["scores"]) if fd["scores"] else 0
            win_rate = fd["wins"] / fd["total"] * 100 if fd["total"] > 0 else 0

            factors[fname] = {
                "name": meta["name"],
                "icon": meta["icon"],
                "color": meta["color"],
                "description": meta["description"],
                "avg_return_1d": round(avg_1d, 4),
                "avg_return_5d": round(avg_5d, 4),
                "avg_score": round(avg_score, 2),
                "win_rate": round(win_rate, 1),
                "stock_count": fd["total"],
                "strategies": sorted(fd["strategies"]),
            }

        return {
            "trade_date": trade_date,
            "lookback_days": lookback_days,
            "data_points": len(rows),
            "factors": factors,
        }

    # ------------------------------------------------------------------
    # 2. 因子动量信号
    # ------------------------------------------------------------------
    def get_factor_momentum(
        self, trade_date: str = None, recent_days: int = 5, older_days: int = 15
    ) -> Dict[str, Any]:
        """获取因子动量——近期 vs 历史表现对比。

        动量 = (近期平均收益 - 历史平均收益) / max(|历史平均收益|, 0.01)
        正动量 = 因子正在改善，负动量 = 因子正在衰减。

        Returns:
            {
                "trade_date": "...",
                "momentum": [
                    {factor, momentum_score, recent_return, older_return, trend: "improving"|"declining"|"stable"},
                    ...
                ]
            }
        """
        if trade_date is None:
            trade_date = datetime.now().strftime("%Y%m%d")

        all_dates = get_last_n_trade_dates(trade_date, recent_days + older_days)
        all_dates.append(trade_date)
        all_dates = sorted(set(all_dates))

        if len(all_dates) < 2:
            return {"trade_date": trade_date, "momentum": []}

        # Split into recent and older periods
        mid_idx = len(all_dates) - recent_days
        recent_dates = all_dates[mid_idx:]
        older_dates = all_dates[:mid_idx] if mid_idx > 0 else all_dates[:1]

        def _avg_return_for_dates(date_list: List[str]) -> Dict[str, float]:
            """Compute average return per factor for a list of dates."""
            session = SessionLocal()
            try:
                rows = session.query(
                    StrategyPerformance.strategy_name,
                    StrategyPerformance.ret_1d,
                ).filter(
                    StrategyPerformance.trade_date.in_(date_list),
                    StrategyPerformance.ret_1d.isnot(None),
                ).all()
            finally:
                session.close()

            factor_rets: Dict[str, List[float]] = defaultdict(list)
            for row in rows:
                factor = STRATEGY_TO_FACTOR.get(row.strategy_name, "combo")
                factor_rets[factor].append(row.ret_1d)

            return {
                f: sum(rets) / len(rets) if rets else 0
                for f, rets in factor_rets.items()
            }

        recent_avg = _avg_return_for_dates(recent_dates)
        older_avg = _avg_return_for_dates(older_dates)

        momentum_list = []
        for fname in FACTOR_META:
            recent = recent_avg.get(fname, 0)
            older = older_avg.get(fname, 0)
            denom = max(abs(older), 0.0001)
            mom_score = (recent - older) / denom

            if mom_score > 0.1:
                trend = "improving"
            elif mom_score < -0.1:
                trend = "declining"
            else:
                trend = "stable"

            momentum_list.append({
                "factor": fname,
                "name": FACTOR_META[fname]["name"],
                "icon": FACTOR_META[fname]["icon"],
                "color": FACTOR_META[fname]["color"],
                "momentum_score": round(mom_score, 4),
                "recent_return": round(recent, 4),
                "older_return": round(older, 4),
                "trend": trend,
            })

        # Sort by momentum score (highest first)
        momentum_list.sort(key=lambda x: x["momentum_score"], reverse=True)

        return {
            "trade_date": trade_date,
            "recent_period": f"{recent_dates[0]}~{recent_dates[-1]}",
            "older_period": f"{older_dates[0]}~{older_dates[-1]}" if older_dates else "N/A",
            "momentum": momentum_list,
        }

    # ------------------------------------------------------------------
    # 3. 因子轮动状态检测
    # ------------------------------------------------------------------
    def detect_factor_regime(self, trade_date: str = None) -> Dict[str, Any]:
        """检测当前因子轮动状态。

        根据因子动量得分判断哪个因子正在主导市场。

        Returns:
            {
                "regime": "VALUE_DOMINANT",
                "regime_info": {label, icon, color, desc},
                "dominant_factor": "value",
                "dominant_momentum": 0.35,
                "confidence": 0.72,
                "all_factors": [...]
            }
        """
        momentum_data = self.get_factor_momentum(trade_date)
        momentum_list = momentum_data.get("momentum", [])

        if not momentum_list:
            return {
                "trade_date": trade_date or datetime.now().strftime("%Y%m%d"),
                "regime": "BALANCED",
                "regime_info": FACTOR_REGIMES["BALANCED"],
                "dominant_factor": None,
                "dominant_momentum": 0,
                "confidence": 0,
                "all_factors": [],
            }

        # Find the dominant factor (highest positive momentum)
        top = momentum_list[0]
        top_mom = top["momentum_score"]

        # Determine regime
        if top_mom < 0.05:
            regime = "BALANCED"
        else:
            factor_to_regime = {
                "value": "VALUE_DOMINANT",
                "momentum": "MOMENTUM_DOMINANT",
                "flow": "FLOW_DOMINANT",
                "event": "EVENT_DOMINANT",
                "combo": "BALANCED",
            }
            regime = factor_to_regime.get(top["factor"], "BALANCED")

        # Confidence: based on how far ahead the top factor is
        if len(momentum_list) >= 2:
            gap = top_mom - momentum_list[1]["momentum_score"]
            confidence = min(max(gap / max(abs(top_mom), 0.01), 0), 1)
        else:
            confidence = 0.5

        return {
            "trade_date": trade_date or datetime.now().strftime("%Y%m%d"),
            "regime": regime,
            "regime_info": FACTOR_REGIMES[regime],
            "dominant_factor": top["factor"],
            "dominant_factor_name": top["name"],
            "dominant_factor_icon": top["icon"],
            "dominant_momentum": top_mom,
            "confidence": round(confidence, 2),
            "all_factors": momentum_list,
        }

    # ------------------------------------------------------------------
    # 4. 因子轮动选股
    # ------------------------------------------------------------------
    def get_rotation_picks(
        self, trade_date: str = None, top_factors: int = 2, limit: int = 30
    ) -> Dict[str, Any]:
        """基于因子轮动的选股策略。

        1. 识别当前表现最好的 N 个因子
        2. 执行这些因子对应的策略
        3. 给同时被多个因子选中的股票加分

        Returns:
            {
                "trade_date": "...",
                "selected_factors": [...],
                "stocks": [{ts_code, name, score, factor_hits, factors, ...}],
                "summary": {total, avg_score, ...}
            }
        """
        if trade_date is None:
            trade_date = datetime.now().strftime("%Y%m%d")

        # Get factor momentum to identify top factors
        momentum_data = self.get_factor_momentum(trade_date)
        momentum_list = momentum_data.get("momentum", [])

        # Select top N factors with positive momentum
        selected = [m for m in momentum_list if m["momentum_score"] > 0][:top_factors]
        if not selected:
            # If no positive momentum, take top 2 regardless
            selected = momentum_list[:top_factors]

        selected_factor_names = [m["factor"] for m in selected]

        # Find strategies belonging to selected factors
        target_strategies = [
            sname for sname, factor in STRATEGY_TO_FACTOR.items()
            if factor in selected_factor_names
        ]

        # Execute strategies and collect stock scores
        stock_scores: Dict[str, Dict] = {}
        strategy_results: Dict[str, List] = {}

        strategies = get_all_strategies()
        for sname in target_strategies:
            strategy = strategies.get(sname)
            if not strategy or not self.loader:
                continue

            try:
                data_keys = strategy.required_data()
                # Use the loader's cache-aware loading
                data = self.loader.load(trade_date, data_keys)
                results = strategy.check(data)
                strategy_results[sname] = results

                factor = STRATEGY_TO_FACTOR.get(sname, "combo")
                for r in results:
                    code = r.ts_code
                    if code not in stock_scores:
                        stock_scores[code] = {
                            "ts_code": code,
                            "name": r.name,
                            "total_score": 0,
                            "factor_hits": 0,
                            "factors": [],
                            "strategy_details": [],
                        }
                    stock_scores[code]["total_score"] += r.score
                    stock_scores[code]["factor_hits"] += 1
                    if factor not in stock_scores[code]["factors"]:
                        stock_scores[code]["factors"].append(factor)
                    stock_scores[code]["strategy_details"].append({
                        "strategy": sname,
                        "score": r.score,
                        "reason": r.reason,
                    })
            except Exception as exc:
                logger.error("Factor rotation: strategy '%s' failed: %s", sname, exc)

        # Apply multi-factor bonus
        for code, info in stock_scores.items():
            if info["factor_hits"] > 1:
                bonus = 1.0 + (info["factor_hits"] - 1) * 0.3  # 30% bonus per extra factor
                info["total_score"] = round(info["total_score"] * bonus, 2)

        # Sort and limit
        stocks = sorted(stock_scores.values(), key=lambda x: x["total_score"], reverse=True)[:limit]

        # Get stock names from DB if missing
        name_map = {}
        try:
            session = SessionLocal()
            try:
                rows = session.query(StockBasic.ts_code, StockBasic.name).filter(
                    StockBasic.ts_code.in_([s["ts_code"] for s in stocks if not s.get("name")])
                ).all()
                name_map = {r.ts_code: r.name for r in rows}
            finally:
                session.close()
        except Exception:
            pass

        for s in stocks:
            if not s.get("name"):
                s["name"] = name_map.get(s["ts_code"], s["ts_code"])

        return {
            "trade_date": trade_date,
            "selected_factors": [
                {"factor": m["factor"], "name": m["name"], "icon": m["icon"],
                 "momentum": m["momentum_score"]}
                for m in selected
            ],
            "strategies_executed": sorted(target_strategies),
            "total_matches": len(stocks),
            "stocks": stocks,
        }

    # ------------------------------------------------------------------
    # 5. 单股因子暴露度
    # ------------------------------------------------------------------
    def get_stock_factor_exposure(
        self, ts_code: str, trade_date: str = None
    ) -> Dict[str, Any]:
        """获取单只股票的因子暴露度。

        检查该股票在各因子的策略中被选中的情况。

        Returns:
            {
                "ts_code": "...",
                "exposure": {value: {hit, strategies, avg_score}, ...},
                "dominant_factor": "value",
                "total_score": 123.45
            }
        """
        if trade_date is None:
            trade_date = datetime.now().strftime("%Y%m%d")

        exposure = {}
        for fname in FACTOR_META:
            exposure[fname] = {"hit": False, "strategies": [], "avg_score": 0}

        strategies = get_all_strategies()
        total_score = 0
        hit_count = 0

        for sname, strategy in strategies.items():
            factor = STRATEGY_TO_FACTOR.get(sname, "combo")
            if not self.loader:
                continue

            try:
                data_keys = strategy.required_data()
                data = self.loader.load(trade_date, data_keys)
                results = strategy.check(data)

                for r in results:
                    if r.ts_code == ts_code:
                        exposure[factor]["hit"] = True
                        exposure[factor]["strategies"].append({
                            "name": sname,
                            "score": r.score,
                            "reason": r.reason,
                        })
                        exposure[factor]["avg_score"] += r.score
                        total_score += r.score
                        hit_count += 1
                        break
            except Exception as exc:
                logger.debug("Factor exposure: strategy '%s' failed for %s: %s", sname, ts_code, exc)

        # Compute average scores
        for fname in exposure:
            strats = exposure[fname]["strategies"]
            if strats:
                exposure[fname]["avg_score"] = round(
                    exposure[fname]["avg_score"] / len(strats), 2
                )

        # Find dominant factor
        dominant = max(exposure.items(), key=lambda x: x[1]["avg_score"] if x[1]["hit"] else 0)

        return {
            "ts_code": ts_code,
            "trade_date": trade_date,
            "exposure": exposure,
            "dominant_factor": dominant[0] if dominant[1]["hit"] else None,
            "total_score": round(total_score, 2),
            "factor_count": hit_count,
        }

    # ------------------------------------------------------------------
    # 6. 综合仪表板
    # ------------------------------------------------------------------
    def get_dashboard(self, trade_date: str = None) -> Dict[str, Any]:
        """因子模型综合仪表板——一次调用获取所有数据。"""
        if trade_date is None:
            trade_date = datetime.now().strftime("%Y%m%d")

        return {
            "trade_date": trade_date,
            "performance": self.get_factor_performance(trade_date),
            "momentum": self.get_factor_momentum(trade_date),
            "regime": self.detect_factor_regime(trade_date),
        }

    # ------------------------------------------------------------------
    # 7. 记录因子表现到数据库
    # ------------------------------------------------------------------
    def record_factor_performance(self, trade_date: str) -> Dict[str, Any]:
        """将当日因子表现写入 factor_performance 表。

        每次执行策略后调用，为后续因子动量分析积累数据。
        """
        perf = self.get_factor_performance(trade_date, lookback_days=1)
        factors = perf.get("factors", {})

        session = SessionLocal()
        recorded = 0
        try:
            for fname, fdata in factors.items():
                # Upsert: delete existing + insert
                session.query(FactorPerformance).filter(
                    FactorPerformance.trade_date == trade_date,
                    FactorPerformance.factor_name == fname,
                ).delete()

                fp = FactorPerformance(
                    trade_date=trade_date,
                    factor_name=fname,
                    avg_return_1d=fdata.get("avg_return_1d", 0),
                    avg_return_5d=fdata.get("avg_return_5d", 0),
                    avg_score=fdata.get("avg_score", 0),
                    stock_count=fdata.get("stock_count", 0),
                    win_rate=fdata.get("win_rate", 0),
                    momentum=0,  # Will be computed by get_factor_momentum
                )
                session.add(fp)
                recorded += 1

            session.commit()
        except Exception as exc:
            session.rollback()
            logger.error("record_factor_performance failed: %s", exc)
            return {"success": False, "error": str(exc)}
        finally:
            session.close()

        return {"trade_date": trade_date, "recorded": recorded}
