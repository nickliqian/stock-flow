"""筹码穿透+股权质押安全——筛选筹码结构健康且质押风险低的标的。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class ChipPledgeSafe(BaseStrategy):
    name = "chip_pledge_safe"
    description = "筹码结构健康+低质押风险，双重安全边际标的"
    category = "value"
    icon = "💎"

    def required_data(self) -> List[str]:
        return ["cyq_perf", "pledge_stat", "daily_basic"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        cyq_df = data.get("cyq_perf")
        pledge_df = data.get("pledge_stat")
        basic_df = data.get("daily_basic")

        # 至少需要 cyq_perf 或 pledge_stat 其中之一
        if (cyq_df is None or cyq_df.empty) and (pledge_df is None or pledge_df.empty):
            return []

        # 构建 basic 映射
        basic_map = self._build_basic_map(basic_df)

        # 构建质押数据映射: ts_code -> {ratio, count, amount}
        pledge_map = self._build_pledge_map(pledge_df)

        # 构建筹码数据映射: ts_code -> {penetration, profit_ratio, concentration, ...}
        chip_map = self._build_chip_map(cyq_df, basic_map)

        # 综合评分
        results = []
        all_codes = set(chip_map.keys()) | set(pledge_map.keys())

        for ts_code in all_codes:
            chip = chip_map.get(ts_code, {})
            pledge = pledge_map.get(ts_code, {})
            info = basic_map.get(ts_code, {})

            name = info.get("name", ts_code)
            close = info.get("close")

            # 评分
            score = 0.0
            signals: Dict[str, Any] = {}
            reasons = []

            # --- 筹码维度 (0-50分) ---
            penetration = chip.get("penetration_pct")
            profit_ratio = chip.get("profit_ratio_pct")
            concentration = chip.get("concentration_pct")

            if penetration is not None:
                signals["penetration_pct"] = round(penetration, 2)
                # 穿透率 > 0 说明价格在加权均价之上，健康
                if penetration > 0:
                    score += min(20, penetration * 2)
                    reasons.append(f"穿透率{penetration:.1f}%")
                else:
                    score += max(0, 10 + penetration)  # 负穿透扣分

            if profit_ratio is not None:
                signals["profit_ratio_pct"] = round(profit_ratio, 2)
                # 获利比例 40%-70% 较健康
                if 40 <= profit_ratio <= 70:
                    score += 15
                    reasons.append(f"获利比{profit_ratio:.0f}%")
                elif profit_ratio > 70:
                    score += 10  # 获利盘多，有抛压
                else:
                    score += 5  # 套牢盘多

            if concentration is not None:
                signals["concentration_pct"] = round(concentration, 2)
                # 筹码集中度 > 40% 说明筹码集中
                if concentration > 40:
                    score += 15
                    reasons.append(f"筹码集中{concentration:.0f}%")
                elif concentration > 25:
                    score += 10

            # --- 质押维度 (0-50分) ---
            pledge_ratio = pledge.get("pledge_ratio")
            if pledge_ratio is not None:
                signals["pledge_ratio"] = round(pledge_ratio, 2)
                # 质押比例越低越好
                if pledge_ratio < 10:
                    score += 40
                    reasons.append(f"质押率仅{pledge_ratio:.1f}%")
                elif pledge_ratio < 20:
                    score += 30
                    reasons.append(f"质押率{pledge_ratio:.1f}%")
                elif pledge_ratio < 30:
                    score += 20
                    reasons.append(f"质押率{pledge_ratio:.1f}%")
                elif pledge_ratio < 50:
                    score += 10
                else:
                    score += 0  # 高质押不加分

                pledge_count = pledge.get("pledge_count")
                if pledge_count is not None:
                    signals["pledge_count"] = int(pledge_count)

                pledge_amount = pledge.get("pledge_amount_yi")
                if pledge_amount is not None:
                    signals["pledge_amount_yi"] = pledge_amount

            # 无质押数据视为安全
            if pledge_ratio is None:
                score += 35
                reasons.append("无质押记录")

            # 过滤: 至少有一个维度的数据
            if not chip and not pledge:
                continue

            # 最低分门槛
            if score < 20:
                continue

            if close is not None:
                signals["close"] = round(close, 2)

            results.append(StrategyResult(
                ts_code=ts_code,
                name=name,
                score=min(100, score),
                signals=signals,
                reason="；".join(reasons) if reasons else "综合安全标的",
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:50]

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _build_basic_map(self, basic_df) -> Dict[str, Dict]:
        result = {}
        if basic_df is None or basic_df.empty:
            return result
        code_col = self._find_col(basic_df, ["ts_code", "tc"])
        close_col = self._find_col(basic_df, ["close", "cl"])
        name_col = self._find_col(basic_df, ["name", "nm"])
        mv_col = self._find_col(basic_df, ["total_mv", "tmv"])
        if not code_col:
            return result
        for _, r in basic_df.iterrows():
            tc = str(r.get(code_col, ""))
            result[tc] = {
                "close": self._safe(r, close_col) if close_col else None,
                "name": str(r.get(name_col, "")) if name_col else tc,
                "total_mv": self._safe(r, mv_col) if mv_col else None,
            }
        return result

    def _build_pledge_map(self, pledge_df) -> Dict[str, Dict]:
        result = {}
        if pledge_df is None or pledge_df.empty:
            return result
        code_col = self._find_col(pledge_df, ["ts_code", "tc"])
        ratio_col = self._find_col(pledge_df, ["pledge_ratio", "pr"])
        count_col = self._find_col(pledge_df, ["pledge_count", "pc"])
        amount_col = self._find_col(pledge_df, ["pledge_amount", "pa"])
        if not code_col or not ratio_col:
            return result
        for _, r in pledge_df.iterrows():
            tc = str(r.get(code_col, ""))
            ratio = self._safe(r, ratio_col)
            if ratio is None:
                continue
            entry: Dict[str, Any] = {"pledge_ratio": ratio}
            if count_col:
                c = self._safe(r, count_col)
                if c is not None:
                    entry["pledge_count"] = int(c)
            if amount_col:
                a = self._safe(r, amount_col)
                if a is not None:
                    entry["pledge_amount_yi"] = round(a / 10000, 2)
            result[tc] = entry
        return result

    def _build_chip_map(self, cyq_df, basic_map: Dict) -> Dict[str, Dict]:
        result = {}
        if cyq_df is None or cyq_df.empty:
            return result
        code_col = self._find_col(cyq_df, ["ts_code", "tc"])
        if not code_col:
            return result
        for _, r in cyq_df.iterrows():
            tc = str(r.get(code_col, ""))
            if not tc:
                continue

            weight_avg = self._safe(r, self._find_col(cyq_df, ["weight_avg", "wa"]))
            cost_50 = self._safe(r, self._find_col(cyq_df, ["cost_50pct", "c50"]))
            cost_95 = self._safe(r, self._find_col(cyq_df, ["cost_95pct", "c95"]))
            winner_pct = self._safe(r, self._find_col(cyq_df, ["winner_pct", "wp"]))
            sp1550 = self._safe(r, self._find_col(cyq_df, ["sum_pct_15_50", "sp1550"]))
            sp5085 = self._safe(r, self._find_col(cyq_df, ["sum_pct_50_85", "sp5085"]))

            close = basic_map.get(tc, {}).get("close")
            penetration = None
            if weight_avg and weight_avg > 0 and close and close > 0:
                penetration = (close - weight_avg) / weight_avg * 100

            concentration = None
            if sp1550 is not None and sp5085 is not None:
                concentration = sp1550 + sp5085

            entry: Dict[str, Any] = {}
            if penetration is not None:
                entry["penetration_pct"] = penetration
            if winner_pct is not None:
                entry["profit_ratio_pct"] = winner_pct
            if concentration is not None:
                entry["concentration_pct"] = concentration
            if weight_avg is not None:
                entry["weight_avg"] = weight_avg
            if cost_50 is not None:
                entry["cost_50"] = cost_50
            if cost_95 is not None:
                entry["cost_95"] = cost_95

            result[tc] = entry
        return result
