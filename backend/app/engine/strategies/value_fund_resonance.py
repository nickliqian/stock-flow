"""价值+资金共振——PE合理+近期资金流入+换手活跃的共振标的。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class ValueFundResonance(BaseStrategy):
    name = "value_fund_resonance"
    description = "低PE估值+资金持续流入+换手率活跃的共振机会"
    category = "combo"
    icon = "🎯"

    def required_data(self) -> List[str]:
        return ["daily_basic", "moneyflow_multi"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        daily_df = data.get("daily_basic")
        flow_df = data.get("moneyflow_multi")

        if daily_df is None or daily_df.empty:
            return []
        if flow_df is None or flow_df.empty:
            return []

        # ---- 处理 daily_basic ----
        pe_col = self._find_col(daily_df, ["pe_ttm", "pt"])
        pb_col = self._find_col(daily_df, ["pb"])
        mv_col = self._find_col(daily_df, ["total_mv", "tmv"])
        tr_col = self._find_col(daily_df, ["turnover_rate", "tr"])
        name_col = self._find_col(daily_df, ["name", "nm"])
        code_col = self._find_col(daily_df, ["ts_code", "tc"])

        if not all([pe_col, code_col]):
            return []

        # 基础过滤：PE > 0 且 < 20
        pe_map = {}
        info_map = {}
        for _, row in daily_df.iterrows():
            ts_code = str(row.get(code_col, ""))
            pe = self._safe(row, pe_col)
            if pe is None or pe <= 0 or pe >= 20:
                continue
            pe_map[ts_code] = pe
            info_map[ts_code] = {
                "name": str(row.get(name_col, "")) if name_col else ts_code,
                "pe_ttm": pe,
                "pb": self._safe(row, pb_col),
                "total_mv": self._safe(row, mv_col),
                "turnover_rate": self._safe(row, tr_col),
            }

        if not pe_map:
            return []

        # ---- 处理 moneyflow_multi ----
        flow_code_col = self._find_col(flow_df, ["ts_code", "tc"])
        flow_date_col = self._find_col(flow_df, ["trade_date", "td"])
        net_col = self._find_col(flow_df, ["net_mf_amount", "nma"])

        if not all([flow_code_col, flow_date_col, net_col]):
            return []

        # 计算每只股票最近3日主力净流入总和 & 换手率
        flow_grouped = flow_df.groupby(flow_code_col)
        fund_map = {}
        for ts_code, group in flow_grouped:
            if ts_code not in pe_map:
                continue
            recent = group.sort_values(flow_date_col).tail(3)
            total_net = 0
            positive_days = 0
            for _, row in recent.iterrows():
                net = self._safe(row, net_col)
                if net is not None and net > 0:
                    total_net += net
                    positive_days += 1
            fund_map[ts_code] = {
                "total_net_3d": total_net,
                "positive_days": positive_days,
            }

        # ---- 共振评分 ----
        results = []
        for ts_code, pe in pe_map.items():
            fund = fund_map.get(ts_code)
            if fund is None:
                continue
            if fund["total_net_3d"] <= 0:
                continue  # 必须有净流入

            info = info_map[ts_code]
            turnover = info.get("turnover_rate")

            # 换手率门槛：> 2%
            if turnover is not None and turnover < 2:
                continue

            # 估值质量分（0-30）
            val_score = max(0, min(30, (20 - pe) / 20 * 30))

            # 资金关注度分（0-40）
            fund_score = min(40, fund["total_net_3d"] / 10000 * 20 + fund["positive_days"] * 10)

            # 换手活跃分（0-30）
            if turnover is not None:
                tr_score = min(30, (turnover - 2) / 8 * 30)  # 2%-10%区间
            else:
                tr_score = 10  # 无数据给中等分

            total_score = val_score + fund_score + tr_score

            signals = {
                "pe_ttm": round(pe, 2),
                "pb": round(info["pb"], 2) if info.get("pb") else None,
                "total_mv_yi": round(info["total_mv"] / 10000, 2) if info.get("total_mv") else None,
                "turnover_rate": round(turnover, 2) if turnover else None,
                "net_inflow_3d_wan": round(fund["total_net_3d"], 2),
                "net_inflow_3d_yi": round(fund["total_net_3d"] / 10000, 4),
                "positive_flow_days": fund["positive_days"],
            }

            results.append(StrategyResult(
                ts_code=ts_code,
                name=info["name"],
                score=min(100, total_score),
                signals=signals,
                reason=f"PE={pe:.2f}；近3日净流入{fund['total_net_3d']/10000:.2f}亿；{fund['positive_days']}日正流入",
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results
