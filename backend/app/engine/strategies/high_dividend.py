"""高股息防守——筛选股息率排名前50且PE合理的股票。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class HighDividend(BaseStrategy):
    name = "high_dividend"
    description = "股息率TOP50，PE<20的高分红防守型标的"
    category = "value"
    icon = "🛡️"

    def required_data(self) -> List[str]:
        return ["daily_basic"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        df = data.get("daily_basic")
        if df is None or df.empty:
            return []

        pe_col = self._find_col(df, ["pe_ttm", "pt"])
        dv_col = self._find_col(df, ["dv_ratio", "dr"])
        mv_col = self._find_col(df, ["total_mv", "tmv"])
        name_col = self._find_col(df, ["name", "nm"])
        code_col = self._find_col(df, ["ts_code", "tc"])
        turnover_col = self._find_col(df, ["turnover_rate", "tr"])

        if not all([pe_col, dv_col, code_col]):
            return []

        # 预过滤
        candidates = []
        for _, row in df.iterrows():
            pe = self._safe(row, pe_col)
            dv = self._safe(row, dv_col)
            if pe is None or dv is None:
                continue
            if pe <= 0 or pe >= 20:
                continue
            if dv < 1:  # 至少1%股息率
                continue
            candidates.append(row)

        if not candidates:
            return []

        # 按股息率降序排列取前50
        candidates.sort(key=lambda r: self._safe(r, dv_col) or 0, reverse=True)
        candidates = candidates[:50]

        # 股息率最大值用于评分归一化
        max_dv = self._safe(candidates[0], dv_col) if candidates else 10

        results = []
        for rank, row in enumerate(candidates, 1):
            pe = self._safe(row, pe_col)
            dv = self._safe(row, dv_col)
            mv = self._safe(row, mv_col)
            ts_code = str(row.get(code_col, ""))
            stock_name = str(row.get(name_col, "")) if name_col else ts_code

            # 评分：股息率排名（越高越好）+ PE越低越好
            dv_score = (dv / max_dv) * 60 if max_dv else 0
            pe_score = max(0, min(40, (20 - pe) / 20 * 40))
            total_score = dv_score + pe_score

            signals = {
                "pe_ttm": round(pe, 2),
                "dv_ratio": round(dv, 2),
                "rank": rank,
            }
            if mv is not None:
                signals["total_mv_yi"] = round(mv / 10000, 2)
            turnover = self._safe(row, turnover_col) if turnover_col else None
            if turnover is not None:
                signals["turnover_rate"] = round(turnover, 2)

            results.append(StrategyResult(
                ts_code=ts_code,
                name=stock_name,
                score=total_score,
                signals=signals,
                reason=f"股息率排名#{rank}({dv:.2f}%)；PE(TTM)={pe:.2f}",
            ))

        return results
