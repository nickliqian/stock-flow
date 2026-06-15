"""低估值金矿——筛选低PE、低PB、高股息率且市值足够大的股票。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class LowValuationGold(BaseStrategy):
    name = "low_valuation_gold"
    description = "低PE、低PB、高股息率，市值>50亿的价值洼地"
    category = "value"
    icon = "⛏️"

    def required_data(self) -> List[str]:
        return ["daily_basic"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        df = data.get("daily_basic")
        if df is None or df.empty:
            return []

        # 标准化列名——数据库返回可能是短列名
        pe_col = self._find_col(df, ["pe_ttm", "pt"])
        pb_col = self._find_col(df, ["pb"])
        dv_col = self._find_col(df, ["dv_ratio", "dr"])
        mv_col = self._find_col(df, ["total_mv", "tmv"])
        name_col = self._find_col(df, ["name", "nm"])
        code_col = self._find_col(df, ["ts_code", "tc"])
        turnover_col = self._find_col(df, ["turnover_rate", "tr"])

        if not all([pe_col, pb_col, dv_col, mv_col, code_col]):
            return []

        results = []
        for _, row in df.iterrows():
            pe_ttm = self._safe(row, pe_col)
            pb = self._safe(row, pb_col)
            dv = self._safe(row, dv_col)
            mv = self._safe(row, mv_col)

            # 基础过滤：PE > 0（盈利）、低PE、低PB、高股息、大市值
            if pe_ttm is None or pb is None or dv is None or mv is None:
                continue
            if pe_ttm <= 0 or pe_ttm >= 15:
                continue
            if pb <= 0 or pb >= 2:
                continue
            if dv < 3:
                continue
            if mv < 5000000:  # 50亿（万元）
                continue

            ts_code = str(row.get(code_col, ""))
            stock_name = str(row.get(name_col, "")) if name_col else ts_code

            # 评分：PE越低、股息率越高得分越高
            pe_score = max(0, min(50, (15 - pe_ttm) / 15 * 50))
            dv_score = max(0, min(30, (dv - 3) / 5 * 30))
            pb_score = max(0, min(20, (2 - pb) / 2 * 20))
            total_score = pe_score + dv_score + pb_score

            turnover = self._safe(row, turnover_col) if turnover_col else None

            signals = {
                "pe_ttm": round(pe_ttm, 2),
                "pb": round(pb, 2),
                "dv_ratio": round(dv, 2),
                "total_mv_yi": round(mv / 10000, 2),
            }
            if turnover is not None:
                signals["turnover_rate"] = round(turnover, 2)

            reason_parts = [f"PE(TTM)={pe_ttm:.2f}", f"PB={pb:.2f}", f"股息率={dv:.2f}%"]
            if mv >= 10000000:
                reason_parts.append(f"大盘股({mv/10000:.0f}亿)")

            results.append(StrategyResult(
                ts_code=ts_code,
                name=stock_name,
                score=total_score,
                signals=signals,
                reason="；".join(reason_parts),
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results
