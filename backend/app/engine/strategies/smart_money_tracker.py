"""聪明钱追踪——大宗交易溢价+大单资金主导的机构级交易模式。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class SmartMoneyTracker(BaseStrategy):
    name = "smart_money_tracker"
    description = "大宗交易溢价成交+大单资金主导，追踪机构级聪明钱动向"
    category = "flow"
    icon = "🐋"

    def required_data(self) -> List[str]:
        return ["block_trade", "moneyflow", "daily", "stock_basic"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        bt_df = data.get("block_trade")
        mf_df = data.get("moneyflow")
        daily_df = data.get("daily")
        sb = data.get("stock_basic")

        if bt_df is None or bt_df.empty:
            return []
        if mf_df is None or mf_df.empty:
            return []

        # ---- 构建股票名称映射 ----
        name_map: Dict[str, str] = {}
        mv_map: Dict[str, float] = {}
        if sb is not None and not sb.empty:
            ts_col_sb = self._find_col(sb, ["ts_code", "tc"])
            name_col_sb = self._find_col(sb, ["name", "nm"])
            mv_col_sb = self._find_col(sb, ["total_mv", "tmv", "market_cap", "mc"])
            if ts_col_sb:
                for _, row in sb.iterrows():
                    code = str(row.get(ts_col_sb, ""))
                    if name_col_sb:
                        name_map[code] = str(row.get(name_col_sb, ""))
                    if mv_col_sb:
                        mv = self._safe(row, mv_col_sb)
                        if mv is not None:
                            mv_map[code] = mv

        # ---- 构建收盘价查找表 ----
        close_map: Dict[str, float] = {}
        if daily_df is not None and not daily_df.empty:
            code_col_d = self._find_col(daily_df, ["ts_code"])
            close_col_d = self._find_col(daily_df, ["close"])
            if code_col_d and close_col_d:
                for _, row in daily_df.iterrows():
                    tc = str(row.get(code_col_d, ""))
                    cl = self._safe(row, close_col_d)
                    if tc and cl is not None:
                        close_map[tc] = cl

        # ---- 处理 block_trade：找溢价大宗交易 ----
        bt_code_col = self._find_col(bt_df, ["ts_code"])
        bt_price_col = self._find_col(bt_df, ["price"])
        bt_amount_col = self._find_col(bt_df, ["amount"])

        if not all([bt_code_col, bt_price_col, bt_amount_col]):
            return []

        premium_map: Dict[str, Dict] = {}
        for _, row in bt_df.iterrows():
            ts_code = str(row.get(bt_code_col, ""))
            block_price = self._safe(row, bt_price_col)
            trade_amount = self._safe(row, bt_amount_col)

            if not ts_code or block_price is None or trade_amount is None:
                continue
            # 过滤小额交易 (< 500万)
            if trade_amount < 500:
                continue

            close_price = close_map.get(ts_code)
            if close_price is None or close_price <= 0:
                continue

            premium_pct = (block_price / close_price - 1) * 100
            if premium_pct <= 0:
                continue  # 只看溢价

            if ts_code not in premium_map:
                premium_map[ts_code] = {
                    "max_premium_pct": premium_pct,
                    "total_amount": trade_amount,
                    "count": 1,
                    "block_price": block_price,
                    "close_price": close_price,
                }
            else:
                g = premium_map[ts_code]
                g["max_premium_pct"] = max(g["max_premium_pct"], premium_pct)
                g["total_amount"] += trade_amount
                g["count"] += 1
                if premium_pct == g["max_premium_pct"]:
                    g["block_price"] = block_price
                    g["close_price"] = close_price

        if not premium_map:
            return []

        # ---- 处理 moneyflow：找大单主导 ----
        mf_code_col = self._find_col(mf_df, ["ts_code", "tc"])
        mf_date_col = self._find_col(mf_df, ["trade_date", "td"])
        buy_lg_col = self._find_col(mf_df, ["buy_lg_amount", "bla"])
        sell_lg_col = self._find_col(mf_df, ["sell_lg_amount", "sla"])
        buy_elg_col = self._find_col(mf_df, ["buy_elg_amount", "bea"])
        sell_elg_col = self._find_col(mf_df, ["sell_elg_amount", "sea"])
        buy_sm_col = self._find_col(mf_df, ["buy_sm_amount", "bsm"])
        sell_sm_col = self._find_col(mf_df, ["sell_sm_amount", "ssm"])
        buy_md_col = self._find_col(mf_df, ["buy_md_amount", "bmd"])
        sell_md_col = self._find_col(mf_df, ["sell_md_amount", "smd"])

        if not all([mf_code_col]):
            return []

        large_order_map: Dict[str, Dict] = {}
        mf_grouped = mf_df.groupby(mf_code_col)

        for ts_code, group in mf_grouped:
            if ts_code not in premium_map:
                continue

            # 取最新一天
            if mf_date_col:
                group = group.sort_values(mf_date_col, ascending=False)
            latest_row = group.iloc[0]

            # 计算大单买入总额
            buy_lg = self._safe(latest_row, buy_lg_col) or 0 if buy_lg_col else 0
            buy_elg = self._safe(latest_row, buy_elg_col) or 0 if buy_elg_col else 0
            sell_lg = self._safe(latest_row, sell_lg_col) or 0 if sell_lg_col else 0
            sell_elg = self._safe(latest_row, sell_elg_col) or 0 if sell_elg_col else 0

            large_order_buy = buy_lg + buy_elg

            # 计算总成交额
            buy_sm = self._safe(latest_row, buy_sm_col) or 0 if buy_sm_col else 0
            sell_sm = self._safe(latest_row, sell_sm_col) or 0 if sell_sm_col else 0
            buy_md = self._safe(latest_row, buy_md_col) or 0 if buy_md_col else 0
            sell_md = self._safe(latest_row, sell_md_col) or 0 if sell_md_col else 0

            # 总量 = 各类买入+各类卖出
            total_amount = (buy_lg + sell_lg + buy_elg + sell_elg +
                            buy_sm + sell_sm + buy_md + sell_md)

            if total_amount <= 0:
                continue

            # 大单占比
            large_order_dominance = large_order_buy / total_amount * 100

            # 大单占比 > 50%
            if large_order_dominance <= 50:
                continue

            # 大单净流入
            net_large = (buy_lg - sell_lg) + (buy_elg - sell_elg)

            large_order_map[ts_code] = {
                "large_order_dominance": large_order_dominance,
                "large_order_buy": large_order_buy,
                "total_amount": total_amount,
                "net_large": net_large,
            }

        # ---- 评分：取两边都满足的 ----
        results = []
        for ts_code in premium_map:
            lo = large_order_map.get(ts_code)
            if lo is None:
                continue

            stock_name = name_map.get(ts_code, ts_code)
            # 过滤 ST
            if "ST" in stock_name.upper():
                continue

            # 市值过滤
            mv = mv_map.get(ts_code)
            if mv is not None and mv < 500000:  # < 50亿
                continue

            p = premium_map[ts_code]

            # 大宗交易溢价分（30分满分）
            # 1% = 10, 3% = 30
            premium_score = min(30, p["max_premium_pct"] * 10)

            # 大单占比分（40分满分）
            # 50% = 20, 70% = 40
            dominance_score = min(40, (lo["large_order_dominance"] - 50) / 20 * 40)

            # 资金流入金额分（30分满分）
            # 5000万 = 15, 1亿 = 30
            fund_amount_score = min(30, lo["large_order_buy"] / 5000 * 15)

            total_score = premium_score + dominance_score + fund_amount_score

            signals = {
                "max_premium_pct": round(p["max_premium_pct"], 2),
                "block_price": round(p["block_price"], 2),
                "close_price": round(p["close_price"], 2),
                "block_total_amount_wan": round(p["total_amount"], 2),
                "block_trade_count": p["count"],
                "large_order_dominance_pct": round(lo["large_order_dominance"], 2),
                "large_order_buy_wan": round(lo["large_order_buy"], 2),
                "net_large_wan": round(lo["net_large"], 2),
                "total_mv_yi": round(mv / 10000, 2) if mv else None,
            }

            reason = (
                f"大宗交易溢价{p['max_premium_pct']:.1f}%"
                f" + 大单占比{lo['large_order_dominance']:.1f}%"
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
