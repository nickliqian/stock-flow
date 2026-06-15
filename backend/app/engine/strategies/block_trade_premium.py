"""大宗交易溢价——筛选大宗交易价格高于收盘价的股票（买方愿意溢价接货）。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class BlockTradePremium(BaseStrategy):
    name = "block_trade_premium"
    description = "大宗交易溢价成交，买方看好后市愿意高价接货"
    category = "event"
    icon = "🐋"

    def required_data(self) -> List[str]:
        return ["block_trade", "daily"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        bt_df = data.get("block_trade")
        daily_df = data.get("daily")

        if bt_df is None or bt_df.empty:
            return []

        # 构建收盘价查找表
        close_map = {}
        if daily_df is not None and not daily_df.empty:
            code_col_d = self._find_col(daily_df, ["ts_code"])
            close_col_d = self._find_col(daily_df, ["close"])
            if code_col_d and close_col_d:
                for _, row in daily_df.iterrows():
                    tc = str(row.get(code_col_d, ""))
                    cl = self._safe(row, close_col_d)
                    if tc and cl is not None:
                        close_map[tc] = cl

        # 找列名
        code_col = self._find_col(bt_df, ["ts_code"])
        price_col = self._find_col(bt_df, ["price"])
        vol_col = self._find_col(bt_df, ["vol"])
        amount_col = self._find_col(bt_df, ["amount"])
        buyer_col = self._find_col(bt_df, ["buyer"])

        if not all([code_col, price_col, amount_col]):
            return []

        # 按股票分组合并大宗交易
        grouped = {}
        for _, row in bt_df.iterrows():
            ts_code = str(row.get(code_col, ""))
            block_price = self._safe(row, price_col)
            trade_amount = self._safe(row, amount_col)

            if ts_code is None or block_price is None or trade_amount is None:
                continue
            # 过滤小额交易 (< 500万)
            if trade_amount < 500:
                continue

            close_price = close_map.get(ts_code)
            if close_price is None or close_price <= 0:
                continue

            premium_rate = (block_price / close_price - 1) * 100
            if premium_rate <= 0:
                continue  # 只看溢价

            buyer = str(row.get(buyer_col, "")) if buyer_col else ""

            if ts_code not in grouped:
                grouped[ts_code] = {
                    "max_premium": premium_rate,
                    "total_amount": trade_amount,
                    "count": 1,
                    "has_buyer": bool(buyer),
                    "block_price": block_price,
                    "close_price": close_price,
                }
            else:
                g = grouped[ts_code]
                g["max_premium"] = max(g["max_premium"], premium_rate)
                g["total_amount"] += trade_amount
                g["count"] += 1
                if buyer:
                    g["has_buyer"] = True
                # 保留最大溢价那笔的价格
                if premium_rate == g["max_premium"]:
                    g["block_price"] = block_price
                    g["close_price"] = close_price

        results = []
        # 获取股票名称
        name_map = {}
        name_col_bt = self._find_col(bt_df, ["name"])
        if name_col_bt:
            for _, row in bt_df.iterrows():
                tc = str(row.get(code_col, ""))
                nm = str(row.get(name_col_bt, ""))
                if tc and nm:
                    name_map[tc] = nm

        for ts_code, g in grouped.items():
            # 评分
            # 溢价率: 1%=10, 3%=30, 5%+=50
            premium_score = min(50, g["max_premium"] * 10)
            # 金额: 1000万=10, 5000万=20, 1亿+=30
            amount_score = min(30, g["total_amount"] / 10000 * 10)
            # 有买家名称 +20
            buyer_score = 20 if g["has_buyer"] else 0

            total_score = premium_score + amount_score + buyer_score

            stock_name = name_map.get(ts_code, "")

            signals = {
                "premium_rate": round(g["max_premium"], 2),
                "block_price": round(g["block_price"], 2),
                "close_price": round(g["close_price"], 2),
                "total_amount_wan": round(g["total_amount"], 2),
                "trade_count": g["count"],
            }

            reason_parts = [
                f"溢价{g['max_premium']:.1f}%",
                f"累计{g['total_amount']/10000:.2f}亿",
            ]
            if g["count"] > 1:
                reason_parts.append(f"{g['count']}笔交易")

            results.append(StrategyResult(
                ts_code=ts_code,
                name=stock_name,
                score=min(100, total_score),
                signals=signals,
                reason="；".join(reason_parts),
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results
