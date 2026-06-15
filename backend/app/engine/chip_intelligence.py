"""筹码穿透率 + 股权质押风险分析引擎。

提供两个核心分析维度:
1. 筹码穿透率: 衡量当前价格穿越上方套牢盘所需的成本，值越高说明上方压力越小。
2. 股权质押风险: 评估大股东质押比例对股价的潜在冲击。
"""

import logging
import pandas as pd
from typing import Dict, Any, List, Optional

from .data_loader import StrategyDataLoader

logger = logging.getLogger(__name__)


class ChipIntelligenceEngine:
    """筹码穿透率 + 股权质押风险综合分析引擎。"""

    def __init__(self, loader: StrategyDataLoader):
        self.loader = loader

    # ------------------------------------------------------------------
    # public
    # ------------------------------------------------------------------
    def analyze(
        self,
        trade_date: Optional[str] = None,
        min_pledge_ratio: float = 0.0,
        max_pledge_ratio: float = 60.0,
    ) -> Dict[str, Any]:
        """返回全市场筹码穿透率 + 股权质押风险分析结果。"""
        if not trade_date:
            from ..utils import get_latest_trade_date
            trade_date = get_latest_trade_date(self.loader.cache)

        # 加载所需数据
        data = self.loader.load(trade_date, ["cyq_perf", "pledge_stat", "daily_basic"])
        cyq_df = data.get("cyq_perf", pd.DataFrame())
        pledge_df = data.get("pledge_stat", pd.DataFrame())
        basic_df = data.get("daily_basic", pd.DataFrame())

        results = {
            "trade_date": trade_date,
            "chip_penetration": [],
            "pledge_risk": [],
            "summary": {},
        }

        # 1. 筹码穿透率分析
        if not cyq_df.empty:
            results["chip_penetration"] = self._calc_chip_penetration(cyq_df, basic_df)

        # 2. 股权质押风险分析
        if not pledge_df.empty:
            results["pledge_risk"] = self._calc_pledge_risk(
                pledge_df, basic_df, min_pledge_ratio, max_pledge_ratio
            )

        # 3. 汇总
        results["summary"] = {
            "total_analyzed_chip": len(results["chip_penetration"]),
            "total_analyzed_pledge": len(results["pledge_risk"]),
            "high_pledge_risk_count": sum(
                1 for r in results["pledge_risk"] if r.get("risk_level") == "high"
            ),
        }

        return results

    # ------------------------------------------------------------------
    # private
    # ------------------------------------------------------------------
    @staticmethod
    def _find_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        for c in candidates:
            if c in df.columns:
                return c
        return None

    @staticmethod
    def _safe_val(row, col):
        try:
            v = row.get(col) if hasattr(row, "get") else row[col]
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            return float(v)
        except (ValueError, TypeError, KeyError):
            return None

    def _calc_chip_penetration(
        self, cyq_df: pd.DataFrame, basic_df: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """计算筹码穿透率。

        穿透率 = 当前价位于筹码分布中的位置，值越高说明越接近上方套牢盘。
        """
        code_col = self._find_col(cyq_df, ["ts_code", "tc"])
        if not code_col:
            return []

        # 构建 basic 映射: ts_code -> {close, name}
        basic_map: Dict[str, Dict] = {}
        if not basic_df.empty:
            b_code = self._find_col(basic_df, ["ts_code", "tc"])
            b_close = self._find_col(basic_df, ["close", "cl"])
            b_name = self._find_col(basic_df, ["name", "nm"])
            if b_code:
                for _, r in basic_df.iterrows():
                    tc = str(r.get(b_code, ""))
                    close = self._safe_val(r, b_close) if b_close else None
                    nm = str(r.get(b_name, "")) if b_name else tc
                    basic_map[tc] = {"close": close, "name": nm}

        results = []
        for _, row in cyq_df.iterrows():
            ts_code = str(row.get(code_col, ""))
            if not ts_code:
                continue

            # 关键字段
            weight_avg = self._safe_val(row, self._find_col(cyq_df, ["weight_avg", "wa"]))
            cost_50 = self._safe_val(row, self._find_col(cyq_df, ["cost_50pct", "c50"]))
            cost_85 = self._safe_val(row, self._find_col(cyq_df, ["cost_85pct", "c85"]))
            cost_95 = self._safe_val(row, self._find_col(cyq_df, ["cost_95pct", "c95"]))
            winner_pct = self._safe_val(row, self._find_col(cyq_df, ["winner_pct", "wp"]))
            sum_pct_5_15 = self._safe_val(row, self._find_col(cyq_df, ["sum_pct_5_15", "sp515"]))
            sum_pct_15_50 = self._safe_val(row, self._find_col(cyq_df, ["sum_pct_15_50", "sp1550"]))
            sum_pct_50_85 = self._safe_val(row, self._find_col(cyq_df, ["sum_pct_50_85", "sp5085"]))
            sum_pct_85_95 = self._safe_val(row, self._find_col(cyq_df, ["sum_pct_85_95", "sp8595"]))

            # 获取当前价格
            info = basic_map.get(ts_code, {})
            close = info.get("close")
            name = info.get("name", ts_code)

            if close is None or close <= 0:
                continue

            # 穿透率计算: 当前价格在筹码加权均价之上的百分比
            penetration = None
            if weight_avg and weight_avg > 0:
                penetration = (close - weight_avg) / weight_avg * 100

            # 套牢盘压力: cost_95 - close 越小说明上方压力越小
            overhead_pressure = None
            if cost_95 and close:
                overhead_pressure = (cost_95 - close) / close * 100

            # 获利比例
            profit_ratio = winner_pct

            # 筹码集中度: sum_pct_15_85 越大说明筹码越集中
            concentration = None
            if sum_pct_15_50 is not None and sum_pct_50_85 is not None:
                concentration = sum_pct_15_50 + sum_pct_50_85

            entry = {
                "ts_code": ts_code,
                "name": name,
                "close": round(close, 2),
            }
            if penetration is not None:
                entry["penetration_pct"] = round(penetration, 2)
            if overhead_pressure is not None:
                entry["overhead_pressure_pct"] = round(overhead_pressure, 2)
            if profit_ratio is not None:
                entry["profit_ratio_pct"] = round(profit_ratio, 2)
            if concentration is not None:
                entry["concentration_pct"] = round(concentration, 2)
            if weight_avg is not None:
                entry["weight_avg"] = round(weight_avg, 2)
            if cost_50 is not None:
                entry["cost_50"] = round(cost_50, 2)

            results.append(entry)

        # 按穿透率降序排列
        results.sort(
            key=lambda x: x.get("penetration_pct", -999), reverse=True
        )
        return results[:200]

    def _calc_pledge_risk(
        self,
        pledge_df: pd.DataFrame,
        basic_df: pd.DataFrame,
        min_ratio: float,
        max_ratio: float,
    ) -> List[Dict[str, Any]]:
        """计算股权质押风险。

        风险评级:
        - high: 质押比例 > 50%
        - medium: 质押比例 30%~50%
        - low: 质押比例 < 30%
        """
        code_col = self._find_col(pledge_df, ["ts_code", "tc"])
        ratio_col = self._find_col(pledge_df, ["pledge_ratio", "pr"])
        count_col = self._find_col(pledge_df, ["pledge_count", "pc"])
        amount_col = self._find_col(pledge_df, ["pledge_amount", "pa"])

        if not code_col or not ratio_col:
            return []

        # 构建 basic 映射
        basic_map: Dict[str, Dict] = {}
        if not basic_df.empty:
            b_code = self._find_col(basic_df, ["ts_code", "tc"])
            b_name = self._find_col(basic_df, ["name", "nm"])
            b_mv = self._find_col(basic_df, ["total_mv", "tmv"])
            if b_code:
                for _, r in basic_df.iterrows():
                    tc = str(r.get(b_code, ""))
                    nm = str(r.get(b_name, "")) if b_name else tc
                    mv = self._safe_val(r, b_mv) if b_mv else None
                    basic_map[tc] = {"name": nm, "total_mv": mv}

        results = []
        for _, row in pledge_df.iterrows():
            ts_code = str(row.get(code_col, ""))
            ratio = self._safe_val(row, ratio_col)
            if ratio is None or ratio < min_ratio or ratio > max_ratio:
                continue

            count = self._safe_val(row, count_col)
            amount = self._safe_val(row, amount_col)

            info = basic_map.get(ts_code, {})
            name = info.get("name", ts_code)
            total_mv = info.get("total_mv")

            # 风险等级
            if ratio >= 50:
                risk_level = "high"
                risk_score = min(100, 50 + (ratio - 50) * 2)
            elif ratio >= 30:
                risk_level = "medium"
                risk_score = 30 + (ratio - 30) * 2
            else:
                risk_level = "low"
                risk_score = ratio * 1.0

            # 质押市值占总市值比例
            pledge_mv_ratio = None
            if amount and total_mv and total_mv > 0:
                pledge_mv_ratio = amount / total_mv * 100

            entry = {
                "ts_code": ts_code,
                "name": name,
                "pledge_ratio": round(ratio, 2),
                "risk_level": risk_level,
                "risk_score": round(risk_score, 1),
            }
            if count is not None:
                entry["pledge_count"] = int(count)
            if amount is not None:
                entry["pledge_amount_yi"] = round(amount / 10000, 2)
            if pledge_mv_ratio is not None:
                entry["pledge_mv_ratio_pct"] = round(pledge_mv_ratio, 2)

            results.append(entry)

        # 按风险等级排序 (high > medium > low)，同级别按质押比例降序
        risk_order = {"high": 0, "medium": 1, "low": 2}
        results.sort(
            key=lambda x: (risk_order.get(x["risk_level"], 3), -x["pledge_ratio"])
        )
        return results[:200]
