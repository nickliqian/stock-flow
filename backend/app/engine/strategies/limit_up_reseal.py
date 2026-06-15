"""涨停板打开后回封——筛选当天涨停有开板但最终封住的股票（分歧转一致信号）。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class LimitUpReseal(BaseStrategy):
    name = "limit_up_reseal"
    description = "涨停开板后回封，分歧转一致的强势信号"
    category = "event"
    icon = "💪"

    def required_data(self) -> List[str]:
        return ["limit_list_d"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        df = data.get("limit_list_d")
        if df is None or df.empty:
            return []

        # 找列名
        code_col = self._find_col(df, ["ts_code"])
        name_col = self._find_col(df, ["name"])
        limit_col = self._find_col(df, ["limit"])
        open_times_col = self._find_col(df, ["open_times"])
        turnover_col = self._find_col(df, ["turnover_ratio"])
        mv_col = self._find_col(df, ["total_mv"])
        close_col = self._find_col(df, ["close"])
        pct_chg_col = self._find_col(df, ["pct_chg"])
        first_time_col = self._find_col(df, ["first_time"])
        amount_col = self._find_col(df, ["amount"])

        if not all([code_col, limit_col, open_times_col]):
            return []

        results = []
        for _, row in df.iterrows():
            # 只看涨停
            limit_val = str(row.get(limit_col, ""))
            if limit_val != "U":
                continue

            stock_name = str(row.get(name_col, "")) if name_col else ""
            # 排除 ST
            if "ST" in stock_name.upper():
                continue

            open_times = self._safe(row, open_times_col)
            if open_times is None or open_times <= 0:
                continue  # 没开过板不算

            ts_code = str(row.get(code_col, ""))
            turnover = self._safe(row, turnover_col)
            total_mv = self._safe(row, mv_col)
            close_price = self._safe(row, close_col)
            pct_chg = self._safe(row, pct_chg_col)
            first_time = str(row.get(first_time_col, "")) if first_time_col else ""
            amount = self._safe(row, amount_col)

            # 评分: 开板1-5次最佳（太少没分歧，太多封不住）
            if 1 <= open_times <= 5:
                open_score = 30
            elif open_times <= 8:
                open_score = 15
            else:
                open_score = 5

            # 换手率: 3-15% 最佳（活跃但不过度投机）
            tr_score = 0
            if turnover is not None:
                if 3 <= turnover <= 15:
                    tr_score = 25
                elif 1 <= turnover < 3 or 15 < turnover <= 25:
                    tr_score = 15
                else:
                    tr_score = 5

            # 成交额: 越大越好
            amount_score = 0
            if amount is not None and amount > 0:
                amount_yi = amount / 10000  # 万元转亿元
                if amount_yi >= 10:
                    amount_score = 20
                elif amount_yi >= 5:
                    amount_score = 15
                elif amount_yi >= 1:
                    amount_score = 10

            # 市值加分
            mv_score = 0
            if total_mv is not None and total_mv > 0:
                mv_yi = total_mv / 10000
                if 30 <= mv_yi <= 300:
                    mv_score = 15
                elif 10 <= mv_yi < 30 or 300 < mv_yi <= 800:
                    mv_score = 10

            total_score = open_score + tr_score + amount_score + mv_score

            signals = {
                "open_times": int(open_times),
            }
            if turnover is not None:
                signals["turnover_ratio"] = round(turnover, 2)
            if total_mv is not None:
                signals["total_mv_wan"] = round(total_mv / 10000, 2)
            if close_price is not None:
                signals["close"] = round(close_price, 2)
            if pct_chg is not None:
                signals["pct_chg"] = round(pct_chg, 2)
            if first_time:
                signals["first_time"] = first_time
            if amount is not None:
                signals["amount_yi"] = round(amount / 10000, 2)

            reason_parts = [
                f"涨停开板{int(open_times)}次后回封",
                "分歧转一致",
            ]
            if turnover is not None:
                reason_parts.append(f"换手率{turnover:.1f}%")
            if total_mv is not None:
                reason_parts.append(f"市值{total_mv/10000:.0f}万")

            results.append(StrategyResult(
                ts_code=ts_code,
                name=stock_name,
                score=min(100, total_score),
                signals=signals,
                reason="；".join(reason_parts),
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results
