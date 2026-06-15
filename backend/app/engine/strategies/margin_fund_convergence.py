"""融资+资金共振——融资余额连续增长且主力资金净流入的双重确认信号。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class MarginFundConvergence(BaseStrategy):
    name = "margin_fund_convergence"
    description = "融资余额连续增长+主力资金净流入，杠杆多头与机构共振"
    category = "flow"
    icon = "🧠"

    def required_data(self) -> List[str]:
        return ["margin_detail_multi", "moneyflow_multi", "stock_basic"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        md = data.get("margin_detail_multi")
        mf = data.get("moneyflow_multi")
        sb = data.get("stock_basic")

        if md is None or md.empty:
            return []
        if mf is None or mf.empty:
            return []

        # ---- 构建股票名称映射 ----
        name_map: Dict[str, str] = {}
        industry_map: Dict[str, str] = {}
        mv_map: Dict[str, float] = {}
        if sb is not None and not sb.empty:
            ts_col_sb = self._find_col(sb, ["ts_code", "tc"])
            name_col_sb = self._find_col(sb, ["name", "nm"])
            ind_col_sb = self._find_col(sb, ["industry", "ind"])
            mv_col_sb = self._find_col(sb, ["total_mv", "tmv", "market_cap", "mc"])
            if ts_col_sb:
                for _, row in sb.iterrows():
                    code = str(row.get(ts_col_sb, ""))
                    if name_col_sb:
                        name_map[code] = str(row.get(name_col_sb, ""))
                    if ind_col_sb:
                        industry_map[code] = str(row.get(ind_col_sb, ""))
                    if mv_col_sb:
                        mv = self._safe(row, mv_col_sb)
                        if mv is not None:
                            mv_map[code] = mv

        # ---- 处理 margin_detail_multi：找连续3日+融资余额增长 ----
        m_code_col = self._find_col(md, ["ts_code", "tc"])
        m_date_col = self._find_col(md, ["trade_date", "td"])
        rzye_col = self._find_col(md, ["rzye"])

        if not all([m_code_col, m_date_col, rzye_col]):
            return []

        margin_increase_map: Dict[str, Dict] = {}
        margin_grouped = md.groupby(m_code_col)
        for ts_code, group in margin_grouped:
            stock_name = name_map.get(ts_code, ts_code)
            # 过滤 ST
            if "ST" in stock_name.upper():
                continue

            sorted_group = group.sort_values(m_date_col, ascending=False)
            if len(sorted_group) < 3:
                continue

            # 取最近5日找最长连续增长
            recent = sorted_group.head(5)
            rzye_values = []
            for _, r in recent.iterrows():
                val = self._safe(r, rzye_col)
                if val is None:
                    break
                rzye_values.append(val)

            if len(rzye_values) < 3:
                continue

            # 从最旧到最新检查连续增长
            # rzye_values[0]=最新, rzye_values[-1]=最旧
            # 反转为从旧到新
            ascending = list(reversed(rzye_values))
            consecutive = 1
            for i in range(1, len(ascending)):
                if ascending[i] > ascending[i - 1]:
                    consecutive += 1
                else:
                    break

            if consecutive < 3:
                continue

            # 第一日（最旧）rzye > 1亿
            earliest = ascending[0]
            if earliest <= 1e8:
                continue

            # 累计增长幅度
            latest = ascending[consecutive - 1]
            growth_pct = (latest - earliest) / earliest * 100
            if growth_pct <= 3:
                continue

            margin_increase_map[ts_code] = {
                "consecutive_days": consecutive,
                "growth_pct": growth_pct,
                "earliest_rzye": earliest,
                "latest_rzye": latest,
            }

        if not margin_increase_map:
            return []

        # ---- 处理 moneyflow_multi：找连续3日+主力净流入 ----
        f_code_col = self._find_col(mf, ["ts_code", "tc"])
        f_date_col = self._find_col(mf, ["trade_date", "td"])
        net_col = self._find_col(mf, ["net_mf_amount", "nma"])
        buy_lg_col = self._find_col(mf, ["buy_lg_amount", "bla"])
        sell_lg_col = self._find_col(mf, ["sell_lg_amount", "sla"])
        buy_elg_col = self._find_col(mf, ["buy_elg_amount", "bea"])
        sell_elg_col = self._find_col(mf, ["sell_elg_amount", "sea"])

        if not all([f_code_col, f_date_col, net_col]):
            return []

        fund_flow_map: Dict[str, Dict] = {}
        fund_grouped = mf.groupby(f_code_col)
        for ts_code, group in fund_grouped:
            if ts_code not in margin_increase_map:
                continue

            group = group.sort_values(f_date_col, ascending=False)
            if len(group) < 3:
                continue

            recent = group.head(5)
            consecutive_days = 0
            total_main_inflow = 0.0

            for _, row in recent.iterrows():
                net = self._safe(row, net_col)
                if net is None:
                    continue

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
                    break

            if consecutive_days >= 3:
                fund_flow_map[ts_code] = {
                    "consecutive_days": consecutive_days,
                    "total_inflow": total_main_inflow,
                }

        # ---- 共振评分：只取两边都满足的 ----
        results = []
        for ts_code in margin_increase_map:
            fund = fund_flow_map.get(ts_code)
            if fund is None:
                continue

            stock_name = name_map.get(ts_code, ts_code)
            # 市值过滤 > 50亿（单位：万元，50亿 = 500000万）
            mv = mv_map.get(ts_code)
            if mv is not None and mv < 500000:
                continue

            m = margin_increase_map[ts_code]

            # 融资增长幅度分（40分满分）
            # 3% = 10, 5% = 20, 10% = 40
            margin_score = min(40, m["growth_pct"] * 4)

            # 资金流入一致性分（40分满分）
            # 3天 = 24, 5天 = 40
            fund_consistency_score = min(40, fund["consecutive_days"] * 8)

            # 资金流入金额分（20分满分）
            # 1000万=5, 5000万=10, 1亿=20
            fund_amount_score = min(20, fund["total_inflow"] / 5000 * 10)

            total_score = margin_score + fund_consistency_score + fund_amount_score

            signals = {
                "margin_consecutive_days": m["consecutive_days"],
                "margin_growth_pct": round(m["growth_pct"], 2),
                "margin_latest_yi": round(m["latest_rzye"] / 1e8, 2),
                "margin_earliest_yi": round(m["earliest_rzye"] / 1e8, 2),
                "fund_consecutive_days": fund["consecutive_days"],
                "fund_total_inflow_wan": round(fund["total_inflow"], 2),
                "fund_total_inflow_yi": round(fund["total_inflow"] / 10000, 4),
                "total_mv_yi": round(mv / 10000, 2) if mv else None,
            }

            industry = industry_map.get(ts_code, "")
            reason = (
                f"融资余额{m['consecutive_days']}日增长{m['growth_pct']:.1f}%"
                f" + 主力资金{fund['consecutive_days']}日净流入"
            )

            results.append(StrategyResult(
                ts_code=ts_code,
                name=stock_name,
                score=min(100, total_score),
                signals=signals,
                reason=reason,
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results
