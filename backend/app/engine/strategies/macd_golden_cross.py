"""MACD 金叉——筛选 DIF 上穿 DEA 且零轴上方的强势股。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class MACDGoldenCross(BaseStrategy):
    name = "macd_golden_cross"
    description = "MACD金叉：DIF>DEA且MACD柱状线为正的强势标的"
    category = "momentum"
    icon = "📈"

    def required_data(self) -> List[str]:
        return ["stk_factor"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        sf = data.get("stk_factor")
        if sf is None or sf.empty:
            return []

        # 确定列名
        ts_col = self._find_col(sf, ["ts_code", "tc"])
        name_col = self._find_col(sf, ["name", "nm"])
        dif_col = self._find_col(sf, ["macd_dif", "dif"])
        dea_col = self._find_col(sf, ["macd_dea", "dea"])
        macd_col = self._find_col(sf, ["macd", "macd_hist"])
        pct_col = self._find_col(sf, ["pct_change", "pct_chg", "pct"])
        close_col = self._find_col(sf, ["close", "cl"])

        if not all([ts_col, dif_col, dea_col, macd_col, pct_col, close_col]):
            return []

        results = []
        for _, row in sf.iterrows():
            ts_code = str(row.get(ts_col, ""))
            stock_name = str(row.get(name_col, "")) if name_col else ts_code

            # 过滤 ST
            if "ST" in stock_name.upper():
                continue

            close = self._safe(row, close_col)
            pct_change = self._safe(row, pct_col)
            dif = self._safe(row, dif_col)
            dea = self._safe(row, dea_col)
            macd = self._safe(row, macd_col)

            if close is None or pct_change is None or dif is None or dea is None or macd is None:
                continue

            # 过滤低价股
            if close < 2:
                continue

            # 条件：DIF > DEA（金叉状态）
            if dif <= dea:
                continue

            # 条件：MACD 柱状线为正
            if macd <= 0:
                continue

            # 条件：当日收阳
            if pct_change <= 0:
                continue

            # 评分
            # macd 值越大越好（动量强度），贡献最多 40 分
            macd_score = min(max(macd / 0.5, 0), 40)

            # pct_change 越大越好，贡献最多 30 分
            pct_score = min(pct_change * 3, 30)

            # macd_dif > 0 额外加分 30 分（零轴上方金叉更有意义）
            zero_bonus = 30 if dif > 0 else 0

            total_score = min(macd_score + pct_score + zero_bonus, 100)

            signals = {
                "macd_dif": round(dif, 4),
                "macd_dea": round(dea, 4),
                "macd": round(macd, 4),
                "pct_change": round(pct_change, 2),
                "close": round(close, 2),
                "above_zero": dif > 0,
            }

            # 构建理由
            reason_parts = [f"MACD={macd:.3f}", f"涨幅{pct_change:.1f}%"]
            if dif > 0:
                reason_parts.append("零轴上方")
            reason = "；".join(reason_parts)

            results.append(StrategyResult(
                ts_code=ts_code,
                name=stock_name,
                score=total_score,
                signals=signals,
                reason=reason,
            ))

        return results
