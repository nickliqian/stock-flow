"""连板强势股——筛选连续涨停>=2天且封板力度强的股票。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class ConsecutiveLimitUp(BaseStrategy):
    name = "consecutive_limit_up"
    description = "连续涨停>=2天，开板次数少，封板力度强的强势股"
    category = "event"
    icon = "🔥"

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
        limit_times_col = self._find_col(df, ["limit_times"])
        open_times_col = self._find_col(df, ["open_times"])
        mv_col = self._find_col(df, ["total_mv"])
        close_col = self._find_col(df, ["close"])
        pct_chg_col = self._find_col(df, ["pct_chg"])
        first_time_col = self._find_col(df, ["first_time"])
        last_time_col = self._find_col(df, ["last_time"])

        if not all([code_col, limit_col, limit_times_col, open_times_col]):
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

            limit_times = self._safe(row, limit_times_col)
            open_times = self._safe(row, open_times_col)

            if limit_times is None or open_times is None:
                continue
            if limit_times < 2:
                continue
            if open_times >= 3:
                continue

            ts_code = str(row.get(code_col, ""))
            total_mv = self._safe(row, mv_col)
            close_price = self._safe(row, close_col)
            pct_chg = self._safe(row, pct_chg_col)
            first_time = str(row.get(first_time_col, "")) if first_time_col else ""
            last_time = str(row.get(last_time_col, "")) if last_time_col else ""

            # 评分
            # 连板天数: 2天=20, 3天=30, 4天+=40 (max 50)
            days_score = min(50, limit_times * 15 - 10)
            # 开板次数: 0次=30, 1次=20, 2次=10
            open_score = max(0, 30 - open_times * 15)
            # 市值: 50-500亿最佳
            mv_score = 0
            if total_mv is not None and total_mv > 0:
                mv_yi = total_mv / 10000
                if 50 <= mv_yi <= 500:
                    mv_score = 20
                elif 20 <= mv_yi < 50 or 500 < mv_yi <= 1000:
                    mv_score = 10

            total_score = days_score + open_score + mv_score

            signals = {
                "limit_times": int(limit_times),
                "open_times": int(open_times),
            }
            if total_mv is not None:
                signals["total_mv_wan"] = round(total_mv / 10000, 2)
            if close_price is not None:
                signals["close"] = round(close_price, 2)
            if pct_chg is not None:
                signals["pct_chg"] = round(pct_chg, 2)
            if first_time:
                signals["first_time"] = first_time
            if last_time:
                signals["last_time"] = last_time

            reason_parts = [f"连续{int(limit_times)}天涨停", f"开板{int(open_times)}次"]
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
