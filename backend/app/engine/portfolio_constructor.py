"""量化组合构建器 (Quantitative Portfolio Constructor)

核心功能：
1. 选股池构建：从策略信号、基本面、资金流向构建候选股票池
2. 组合优化：均值方差/风险平价/等权/最大夏普 4种优化方法
3. 风险分析：组合PE/市值/行业集中度/分散度评分
4. 绩效归因：按股票和行业分解收益贡献

创新点：市面上没有个人股票工具做「策略信号→组合优化→风险预算→绩效归因」的完整闭环，
将机构量化的组合构建方法论平民化。
"""

import logging
import json
import math
from typing import Dict, Any, List, Optional
from collections import defaultdict

import numpy as np
from sqlalchemy import create_engine, text

import os as _os

logger = logging.getLogger(__name__)

# Absolute path: resolve relative to this file's location
_DB_DIR = _os.path.normpath(_os.path.join(_os.path.dirname(__file__), '..', '..', 'data'))
DB_PATH = _os.path.join(_DB_DIR, 'cache.db')


class PortfolioConstructorEngine:
    """量化组合构建器"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
        )

    def _query(self, sql: str, params: dict = None) -> list:
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            return [dict(row._mapping) for row in result]

    def _get_latest_trade_date(self) -> str:
        rows = self._query("SELECT MAX(trade_date) as td FROM daily_basic")
        return rows[0]["td"] if rows and rows[0]["td"] else "20260612"

    # ================================================================
    # 1. 选股池构建
    # ================================================================

    def get_candidate_stocks(
        self, trade_date: str = None, min_strategies: int = 2
    ) -> List[Dict[str, Any]]:
        """从策略信号构建候选股票池"""
        if trade_date is None:
            trade_date = self._get_latest_trade_date()

        # 获取策略快照中的股票
        snaps = self._query(
            "SELECT strategy_name, top_picks FROM strategy_snapshot WHERE trade_date = :td",
            {"td": trade_date},
        )

        # 统计每只股票被多少策略选中 + 累计分数
        stock_strategies = defaultdict(lambda: {"count": 0, "total_score": 0.0, "strategies": []})
        for snap in snaps:
            strategy_name = snap["strategy_name"]
            if strategy_name.startswith("_"):
                continue
            try:
                picks = json.loads(snap["top_picks"])
                if not isinstance(picks, list):
                    continue
                for pick in picks:
                    if not isinstance(pick, dict):
                        continue
                    ts_code = pick.get("ts_code")
                    score = float(pick.get("score", pick.get("total_score", 0)))
                    if ts_code:
                        stock_strategies[ts_code]["count"] += 1
                        stock_strategies[ts_code]["total_score"] += score
                        stock_strategies[ts_code]["strategies"].append(strategy_name)
            except (json.JSONDecodeError, TypeError):
                continue

        # 过滤 >= min_strategies 的股票
        qualified = {
            ts_code: info
            for ts_code, info in stock_strategies.items()
            if info["count"] >= min_strategies
        }

        if not qualified:
            return []

        ts_codes = list(qualified.keys())
        placeholders = ", ".join([f":tc{i}" for i in range(len(ts_codes))])
        params = {f"tc{i}": tc for i, tc in enumerate(ts_codes)}
        params["td"] = trade_date

        # 获取基本面数据
        basics = self._query(
            f"""SELECT ts_code, pe_ttm, total_mv, circ_mv, turnover_rate, dv_ratio
                FROM daily_basic WHERE trade_date = :td AND ts_code IN ({placeholders})""",
            params,
        )
        basic_map = {r["ts_code"]: r for r in basics}

        # 获取股票名称和行业
        stock_params = {f"tc{i}": tc for i, tc in enumerate(ts_codes)}
        stocks = self._query(
            f"SELECT ts_code, name, industry FROM stock_basic WHERE ts_code IN ({placeholders})",
            stock_params,
        )
        stock_map = {r["ts_code"]: r for r in stocks}

        # 构建候选列表
        candidates = []
        for ts_code in ts_codes:
            info = qualified[ts_code]
            basic = basic_map.get(ts_code, {})
            stock = stock_map.get(ts_code, {})
            candidates.append({
                "ts_code": ts_code,
                "name": stock.get("name", ts_code[:6]),
                "industry": stock.get("industry", "未知"),
                "pe_ttm": basic.get("pe_ttm"),
                "total_mv": basic.get("total_mv"),
                "circ_mv": basic.get("circ_mv"),
                "turnover_rate": basic.get("turnover_rate"),
                "dv_ratio": basic.get("dv_ratio"),
                "strategy_count": info["count"],
                "total_score": round(info["total_score"], 2),
                "avg_score": round(info["total_score"] / info["count"], 2),
                "strategies": info["strategies"],
            })

        # 按策略数+总分排序
        candidates.sort(key=lambda x: (x["strategy_count"], x["total_score"]), reverse=True)
        return candidates

    # ================================================================
    # 2. 组合优化
    # ================================================================

    def optimize_portfolio(
        self,
        candidates: List[Dict],
        method: str = "mean_variance",
        max_stocks: int = 15,
        max_sector_pct: float = 0.30,
    ) -> List[Dict]:
        """优化组合配置"""
        if not candidates:
            return []

        # 限制候选数量
        pool = candidates[:max_stocks * 3]  # 取更多用于优化

        if method == "equal_weight":
            return self._equal_weight(pool, max_stocks)
        elif method == "risk_parity":
            return self._risk_parity(pool, max_stocks)
        elif method == "mean_variance":
            return self._mean_variance(pool, max_stocks, max_sector_pct)
        elif method == "max_sharpe":
            return self._max_sharpe(pool, max_stocks, max_sector_pct)
        else:
            return self._equal_weight(pool, max_stocks)

    def _equal_weight(self, pool: List[Dict], max_stocks: int) -> List[Dict]:
        """等权配置"""
        n = min(len(pool), max_stocks)
        selected = pool[:n]
        weight = 1.0 / n if n > 0 else 0
        result = []
        for s in selected:
            result.append({
                "ts_code": s["ts_code"],
                "name": s["name"],
                "industry": s.get("industry", "未知"),
                "weight": round(weight, 4),
                "allocation_pct": round(weight * 100, 2),
                "pe_ttm": s.get("pe_ttm"),
                "total_mv": s.get("total_mv"),
                "score": s.get("total_score", 0),
                "strategy_count": s.get("strategy_count", 0),
            })
        return result

    def _risk_parity(self, pool: List[Dict], max_stocks: int) -> List[Dict]:
        """风险平价配置：按波动率倒数加权"""
        n = min(len(pool), max_stocks)
        selected = pool[:n]

        # 用 turnover_rate 近似波动率（换手率越高波动越大）
        vols = []
        for s in selected:
            tr = s.get("turnover_rate")
            vol = float(tr) if tr and tr > 0 else 5.0  # 默认5%
            vols.append(max(vol, 0.1))

        inv_vols = [1.0 / v for v in vols]
        total = sum(inv_vols)
        weights = [iv / total for iv in inv_vols]

        result = []
        for i, s in enumerate(selected):
            result.append({
                "ts_code": s["ts_code"],
                "name": s["name"],
                "industry": s.get("industry", "未知"),
                "weight": round(weights[i], 4),
                "allocation_pct": round(weights[i] * 100, 2),
                "pe_ttm": s.get("pe_ttm"),
                "total_mv": s.get("total_mv"),
                "score": s.get("total_score", 0),
                "strategy_count": s.get("strategy_count", 0),
            })
        return result

    def _mean_variance(self, pool: List[Dict], max_stocks: int, max_sector_pct: float) -> List[Dict]:
        """均值方差优化：最大化夏普比率"""
        n = min(len(pool), max_stocks)
        selected = pool[:n]

        if n <= 1:
            return self._equal_weight(pool, max_stocks)

        # 构建预期收益率向量（用策略分数归一化作为预期收益代理）
        scores = np.array([max(s.get("total_score", 1), 0.1) for s in selected])
        returns = scores / scores.sum() * 0.1  # 缩放到合理范围

        # 构建协方差矩阵（用换手率作为波动率代理）
        vols = np.array([
            max(float(s.get("turnover_rate", 5.0) or 5.0), 0.1) / 100.0
            for s in selected
        ])
        # 简化的对角协方差矩阵（无相关性信息时的默认假设）
        cov_matrix = np.diag(vols ** 2)

        # 求解最优权重（简化版：用分数加权 + 波动率调整）
        try:
            inv_vols = 1.0 / vols
            raw_weights = returns * inv_vols
            raw_weights = np.maximum(raw_weights, 0)  # 不允许做空
            total = raw_weights.sum()
            if total > 0:
                weights = raw_weights / total
            else:
                weights = np.ones(n) / n
        except Exception:
            weights = np.ones(n) / n

        # 应用行业约束
        weights = self._apply_sector_constraint(selected, weights, max_sector_pct)

        result = []
        for i, s in enumerate(selected):
            result.append({
                "ts_code": s["ts_code"],
                "name": s["name"],
                "industry": s.get("industry", "未知"),
                "weight": round(float(weights[i]), 4),
                "allocation_pct": round(float(weights[i]) * 100, 2),
                "pe_ttm": s.get("pe_ttm"),
                "total_mv": s.get("total_mv"),
                "score": s.get("total_score", 0),
                "strategy_count": s.get("strategy_count", 0),
            })
        return result

    def _max_sharpe(self, pool: List[Dict], max_stocks: int, max_sector_pct: float) -> List[Dict]:
        """最大夏普比率优化"""
        n = min(len(pool), max_stocks)
        selected = pool[:n]

        if n <= 1:
            return self._equal_weight(pool, max_stocks)

        # 用策略分数作为 alpha 信号
        scores = np.array([max(s.get("total_score", 1), 0.1) for s in selected])
        vols = np.array([
            max(float(s.get("turnover_rate", 5.0) or 5.0), 0.1) / 100.0
            for s in selected
        ])

        # 网格搜索最优夏普比率权重
        best_sharpe = -999
        best_weights = np.ones(n) / n

        for _ in range(200):
            # 随机扰动
            noise = np.random.randn(n) * 0.05
            w = np.maximum(scores / scores.sum() + noise, 0)
            w = w / w.sum()

            # 计算组合指标
            port_return = (w * scores / scores.sum()).sum()
            port_vol = np.sqrt((w * vols ** 2).sum())
            sharpe = port_return / port_vol if port_vol > 0 else 0

            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_weights = w.copy()

        # 应用行业约束
        best_weights = self._apply_sector_constraint(selected, best_weights, max_sector_pct)

        result = []
        for i, s in enumerate(selected):
            result.append({
                "ts_code": s["ts_code"],
                "name": s["name"],
                "industry": s.get("industry", "未知"),
                "weight": round(float(best_weights[i]), 4),
                "allocation_pct": round(float(best_weights[i]) * 100, 2),
                "pe_ttm": s.get("pe_ttm"),
                "total_mv": s.get("total_mv"),
                "score": s.get("total_score", 0),
                "strategy_count": s.get("strategy_count", 0),
            })
        return result

    def _apply_sector_constraint(
        self, stocks: List[Dict], weights: np.ndarray, max_pct: float
    ) -> np.ndarray:
        """应用行业集中度约束"""
        sector_weights = defaultdict(float)
        for i, s in enumerate(stocks):
            sector_weights[s.get("industry", "未知")] += weights[i]

        adjusted = weights.copy()
        for sector, sw in sector_weights.items():
            if sw > max_pct:
                # 按比例缩减该行业所有股票的权重
                scale = max_pct / sw
                for i, s in enumerate(stocks):
                    if s.get("industry", "未知") == sector:
                        adjusted[i] *= scale

        # 重新归一化
        total = adjusted.sum()
        if total > 0:
            adjusted = adjusted / total
        return adjusted

    # ================================================================
    # 3. 组合分析
    # ================================================================

    def analyze_portfolio(self, portfolio: List[Dict]) -> Dict[str, Any]:
        """分析组合风险和特征"""
        if not portfolio:
            return {"error": "empty portfolio"}

        weights = np.array([p["weight"] for p in portfolio])
        total_mv = sum(
            (p.get("total_mv") or 0) * p["weight"] for p in portfolio
        )
        weighted_pe = sum(
            (p.get("pe_ttm") or 0) * p["weight"]
            for p in portfolio if p.get("pe_ttm")
        )
        weighted_dv = sum(
            (p.get("dv_ratio") or 0) * p["weight"]
            for p in portfolio if p.get("dv_ratio")
        )

        # 行业集中度
        sector_weights = defaultdict(float)
        for p in portfolio:
            sector_weights[p.get("industry", "未知")] += p["weight"]

        # Herfindahl 指数（行业层面）
        hhi = sum(v ** 2 for v in sector_weights.values())
        diversification_score = round((1 - hhi) * 100, 1)

        # Top 5 集中度
        sorted_by_weight = sorted(portfolio, key=lambda x: x["weight"], reverse=True)
        top5_pct = sum(p["weight"] for p in sorted_by_weight[:5]) * 100

        return {
            "stock_count": len(portfolio),
            "weighted_pe": round(weighted_pe, 2),
            "weighted_mv_yi": round(total_mv / 10000, 2),  # 万元→亿元
            "weighted_dv_ratio": round(weighted_dv, 2),
            "sector_count": len(sector_weights),
            "sector_concentration": {
                k: round(v * 100, 1) for k, v in
                sorted(sector_weights.items(), key=lambda x: -x[1])
            },
            "top5_concentration_pct": round(top5_pct, 1),
            "diversification_score": diversification_score,
            "herfindahl_index": round(hhi, 4),
            "max_single_weight": round(max(weights) * 100, 1),
            "min_single_weight": round(min(weights) * 100, 1),
        }

    # ================================================================
    # 4. 绩效归因
    # ================================================================

    def get_attribution(self, portfolio: List[Dict]) -> Dict[str, Any]:
        """绩效归因分析"""
        if not portfolio:
            return {"error": "empty portfolio"}

        ts_codes = [p["ts_code"] for p in portfolio]
        weight_map = {p["ts_code"]: p["weight"] for p in portfolio}

        # 获取历史收益
        placeholders = ", ".join([f":tc{i}" for i in range(len(ts_codes))])
        params = {f"tc{i}": tc for i, tc in enumerate(ts_codes)}

        perf_rows = self._query(
            f"""SELECT ts_code, ret_1d, ret_3d, ret_5d
                FROM strategy_performance
                WHERE ts_code IN ({placeholders})
                AND ret_1d IS NOT NULL""",
            params,
        )

        # 按股票归因
        stock_attribution = []
        for row in perf_rows:
            tc = row["ts_code"]
            w = weight_map.get(tc, 0)
            stock_attribution.append({
                "ts_code": tc,
                "weight": round(w * 100, 2),
                "ret_1d": row.get("ret_1d"),
                "ret_3d": row.get("ret_3d"),
                "ret_5d": row.get("ret_5d"),
                "contribution_1d": round(w * (row.get("ret_1d") or 0) * 100, 4) if row.get("ret_1d") else None,
            })

        # 组合整体收益
        total_contribution = sum(
            s["contribution_1d"] for s in stock_attribution if s["contribution_1d"] is not None
        )

        # 行业归因
        industry_map = {p["ts_code"]: p.get("industry", "未知") for p in portfolio}
        industry_contrib = defaultdict(float)
        industry_count = defaultdict(int)
        for s in stock_attribution:
            ind = industry_map.get(s["ts_code"], "未知")
            if s["contribution_1d"] is not None:
                industry_contrib[ind] += s["contribution_1d"]
                industry_count[ind] += 1

        industry_attribution = [
            {"industry": k, "contribution_1d": round(v, 4), "stock_count": industry_count[k]}
            for k, v in sorted(industry_contrib.items(), key=lambda x: -x[1])
        ]

        # 因子暴露
        pe_values = [p.get("pe_ttm") for p in portfolio if p.get("pe_ttm")]
        mv_values = [p.get("total_mv") for p in portfolio if p.get("total_mv")]
        tr_values = [p.get("turnover_rate") for p in portfolio if p.get("turnover_rate")]

        factor_exposure = {
            "avg_pe": round(sum(pe_values) / len(pe_values), 2) if pe_values else None,
            "avg_mv_yi": round(sum(mv_values) / len(mv_values) / 10000, 2) if mv_values else None,
            "avg_turnover": round(sum(tr_values) / len(tr_values), 2) if tr_values else None,
            "growth_bias": "value" if (sum(pe_values) / len(pe_values) if pe_values else 0) < 15 else "growth",
        }

        return {
            "total_contribution_1d": round(total_contribution, 4),
            "stock_attribution": sorted(stock_attribution, key=lambda x: -(x["contribution_1d"] or 0)),
            "industry_attribution": industry_attribution,
            "factor_exposure": factor_exposure,
            "data_coverage": f"{len(perf_rows)}/{len(portfolio)} stocks with performance data",
        }

    # ================================================================
    # 5. 多方法对比
    # ================================================================

    def compare_portfolios(self, candidates: List[Dict]) -> Dict[str, Any]:
        """对比多种优化方法"""
        methods = ["equal_weight", "risk_parity", "mean_variance", "max_sharpe"]
        results = {}
        for m in methods:
            portfolio = self.optimize_portfolio(candidates, m)
            analysis = self.analyze_portfolio(portfolio)
            results[m] = {
                "portfolio": portfolio,
                "analysis": analysis,
                "method": m,
            }
        return results
