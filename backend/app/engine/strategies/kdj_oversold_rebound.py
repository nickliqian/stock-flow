"""KDJ超卖反弹——筛选K值从超卖区金叉向上反转的标的。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class KDJOversoldRebound(BaseStrategy):
    name = "kdj_oversold_rebound"
    description = "KDJ超卖反弹：K值从超卖区金叉向上，短线反转信号"
    category = "momentum"
    icon = "📉"

    def required_data(self) -> List[str]:
        return ["stk_factor"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        sf = data.get("stk_factor")
        if sf is None or sf.empty:
            return []

        # 确定列名
        ts_col = self._find_col(sf, ["ts_code", "tc"])
        name_col = self._find_col(sf, ["name", "nm"])
        k_col = self._find_col(sf, ["kdj_k"])
        d_col = self._find_col(sf, ["kdj_d"])
        j_col = self._find_col(sf, ["kdj_j"])
        close_col = self._find_col(sf, ["close", "cl"])
        pct_col = self._find_col(sf, ["pct_change", "pct_chg", "pct"])

        if not all([ts_col, k_col, d_col]):
            return []

        # 需要前一日数据来判断金叉
        prev_k_col = self._find_col(sf, ["prev_kdj_k", "kdj_k_prev"])
        prev_d_col = self._find_col(sf, ["prev_kdj_d", "kdj_d_prev"])

        results = []
        for _, row in sf.iterrows():
            ts_code = str(row.get(ts_col, ""))
            stock_name = str(row.get(name_col, "")) if name_col else ts_code

            # 过滤 ST
            if "ST" in stock_name.upper():
                continue

            k_val = self._safe(row, k_col)
            d_val = self._safe(row, d_col)
            j_val = self._safe(row, j_col)

            if k_val is None or d_val is None:
                continue

            # 条件1：K值处于超卖区（K < 20）
            if k_val >= 20:
                continue

            # 条件2：K上穿D（金叉）— 如果有前一天数据则检查交叉，否则检查K<D的趋势
            has_cross = False
            if prev_k_col and prev_d_col:
                prev_k = self._safe(row, prev_k_col)
                prev_d = self._safe(row, prev_d_col)
                if prev_k is not None and prev_d is not None:
                    # 前一天 K <= D，今天 K > D
                    has_cross = prev_k <= prev_d and k_val > d_val

            if not has_cross:
                # 没有前一天数据时，使用宽松条件：K < 20 且 K > D（已经开始反弹）
                if k_val <= d_val:
                    continue

            # 评分
            k_score = max(0, (20 - k_val) * 3)  # K越低分越高，最多60分
            cross_bonus = 20 if has_cross else 0  # 金叉加分
            j_bonus = min(max(0, (10 - (j_val or 0))) * 2, 20) if j_val is not None else 0

            total_score = min(k_score + cross_bonus + j_bonus, 100)

            signals = {
                "kdj_k": round(k_val, 2),
                "kdj_d": round(d_val, 2),
            }
            if j_val is not None:
                signals["kdj_j"] = round(j_val, 2)
            if close_col:
                close = self._safe(row, close_col)
                if close is not None:
                    signals["close"] = round(close, 2)
            if pct_col:
                pct = self._safe(row, pct_col)
                if pct is not None:
                    signals["pct_change"] = round(pct, 2)

            cross_text = "金叉确认" if has_cross else "超卖区反弹"
            results.append(StrategyResult(
                ts_code=ts_code,
                name=stock_name,
                score=total_score,
                signals=signals,
                reason=f"K值{k_val:.1f}（超卖区）{cross_text}；D值{d_val:.1f}",
            ))

        return results
