"""主力资金持续流入——筛选连续3天以上主力净流入为正的股票。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class MainFundInflow(BaseStrategy):
    name = "main_fund_inflow"
    description = "连续3日+主力资金净流入，大单与超大单共振"
    category = "flow"
    icon = "💰"

    def required_data(self) -> List[str]:
        return ["moneyflow_multi"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        df = data.get("moneyflow_multi")
        if df is None or df.empty:
            return []

        # 找列名
        code_col = self._find_col(df, ["ts_code", "tc"])
        date_col = self._find_col(df, ["trade_date", "td"])
        name_col = self._find_col(df, ["name", "nm"])
        net_col = self._find_col(df, ["net_mf_amount", "nma"])
        buy_lg_col = self._find_col(df, ["buy_lg_amount", "bla"])
        sell_lg_col = self._find_col(df, ["sell_lg_amount", "sla"])
        buy_elg_col = self._find_col(df, ["buy_elg_amount", "bea"])
        sell_elg_col = self._find_col(df, ["sell_elg_amount", "sea"])

        if not all([code_col, date_col, net_col]):
            return []

        # 按股票分组
        grouped = df.groupby(code_col)

        results = []
        for ts_code, group in grouped:
            # 按日期升序
            group = group.sort_values(date_col)
            if len(group) < 3:
                continue

            # 取最近5天
            recent = group.tail(5)

            # 统计连续正流入天数（从最新一天往前数）
            consecutive_days = 0
            total_main_inflow = 0  # 大单+超大单净额合计
            for _, row in recent.iterrows():
                net = self._safe(row, net_col)
                if net is None:
                    continue

                # 计算主力净流入（大单+超大单）
                main_net = net
                if buy_lg_col and sell_lg_col:
                    buy_lg = self._safe(row, buy_lg_col) or 0
                    sell_lg = self._safe(row, sell_lg_col) or 0
                    if buy_elg_col and sell_elg_col:
                        buy_elg = self._safe(row, buy_elg_col) or 0
                        sell_elg = self._safe(row, sell_elg_col) or 0
                        main_net = (buy_lg - sell_lg) + (buy_elg - sell_elg)
                    else:
                        main_net = buy_lg - sell_lg

                if main_net > 0:
                    consecutive_days += 1
                    total_main_inflow += main_net
                else:
                    break  # 断了就停

            if consecutive_days < 3:
                continue

            stock_name = ""
            if name_col:
                # 取最新一行的name
                stock_name = str(recent.iloc[-1].get(name_col, ""))

            # 评分：连续天数 + 总流入金额
            days_score = min(40, consecutive_days * 10)
            amount_score = min(40, total_main_inflow / 5000 * 10)  # 5000万为满分段
            bonus = min(20, consecutive_days * 5 - 10) if consecutive_days >= 4 else 0
            total_score = days_score + amount_score + bonus

            signals = {
                "consecutive_days": consecutive_days,
                "total_main_inflow_wan": round(total_main_inflow, 2),
                "total_main_inflow_yi": round(total_main_inflow / 10000, 4),
                "days_analyzed": len(recent),
            }

            results.append(StrategyResult(
                ts_code=str(ts_code),
                name=stock_name,
                score=min(100, total_score),
                signals=signals,
                reason=f"连续{consecutive_days}日主力净流入；累计{total_main_inflow/10000:.2f}亿",
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results
