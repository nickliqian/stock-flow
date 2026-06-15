"""融资余额增长——筛选融资余额连续增长且幅度较大的标的。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class MarginGrowth(BaseStrategy):
    name = "margin_growth"
    description = "融资余额增长：连续3日融资余额增长且累计幅度>3%的标的"
    category = "flow"
    icon = "📊"

    def required_data(self) -> List[str]:
        return ["margin_detail_multi", "stock_basic"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        md = data.get("margin_detail_multi")
        sb = data.get("stock_basic")

        if md is None or md.empty:
            return []

        # 构建股票名称映射
        name_map: Dict[str, str] = {}
        industry_map: Dict[str, str] = {}
        if sb is not None and not sb.empty:
            ts_col_sb = self._find_col(sb, ["ts_code", "tc"])
            name_col_sb = self._find_col(sb, ["name", "nm"])
            ind_col_sb = self._find_col(sb, ["industry", "ind"])
            if ts_col_sb:
                for _, row in sb.iterrows():
                    code = str(row.get(ts_col_sb, ""))
                    if name_col_sb:
                        name_map[code] = str(row.get(name_col_sb, ""))
                    if ind_col_sb:
                        industry_map[code] = str(row.get(ind_col_sb, ""))

        # 确定列名
        ts_col = self._find_col(md, ["ts_code", "tc"])
        date_col = self._find_col(md, ["trade_date", "td"])
        rzye_col = self._find_col(md, ["rzye"])

        if not all([ts_col, date_col, rzye_col]):
            return []

        # 按股票分组
        grouped = md.groupby(ts_col)
        results = []

        for ts_code, group in grouped:
            stock_name = name_map.get(ts_code, ts_code)

            # 过滤 ST
            if "ST" in stock_name.upper():
                continue

            # 按日期排序，取最近3个交易日
            sorted_group = group.sort_values(date_col, ascending=False)
            if len(sorted_group) < 3:
                continue

            latest_3 = sorted_group.head(3)
            rzye_values = []
            for _, r in latest_3.iterrows():
                val = self._safe(r, rzye_col)
                if val is None:
                    break
                rzye_values.append(val)

            if len(rzye_values) < 3:
                continue

            # rzye_values[0] 是最新日期，rzye_values[2] 是最早日期
            # 检查连续3日增长（从旧到新）
            if not (rzye_values[2] < rzye_values[1] < rzye_values[0]):
                continue

            # 第1日（最早）rzye > 1亿
            if rzye_values[2] <= 1e8:
                continue

            # 累计增长幅度
            growth_pct = (rzye_values[0] - rzye_values[2]) / rzye_values[2] * 100
            if growth_pct <= 3:
                continue

            # 评分：增长幅度越大越高分，cap 在 100
            score = min(growth_pct * 5, 100)

            signals = {
                "rzye_latest": round(rzye_values[0] / 1e8, 2),
                "rzye_3d_ago": round(rzye_values[2] / 1e8, 2),
                "growth_pct": round(growth_pct, 2),
                "consecutive_days": 3,
            }

            industry = industry_map.get(ts_code, "")
            reason = f"融资余额连续3日增长{growth_pct:.1f}%（{rzye_values[2]/1e8:.1f}亿→{rzye_values[0]/1e8:.1f}亿）"

            results.append(StrategyResult(
                ts_code=ts_code,
                name=stock_name,
                score=score,
                signals=signals,
                reason=reason,
            ))

        return results
