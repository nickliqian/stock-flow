"""均线多头排列——筛选MA5>MA10>MA20且收阳线的趋势股。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class MAAlignment(BaseStrategy):
    name = "ma_alignment"
    description = "均线多头排列：MA5>MA10>MA20且收阳线的趋势标的"
    category = "momentum"
    icon = "📈"

    def required_data(self) -> List[str]:
        return ["daily_multi"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        dm = data.get("daily_multi")
        if dm is None or dm.empty:
            return []

        # 确定列名
        ts_col = self._find_col(dm, ["ts_code", "tc"])
        close_col = self._find_col(dm, ["close", "cl"])
        open_col = self._find_col(dm, ["open", "op"])
        pre_close_col = self._find_col(dm, ["pre_close", "pc"])
        name_col = self._find_col(dm, ["name", "nm"])

        if not all([ts_col, close_col]):
            return []

        # 按 stock 分组，按 trade_date 排序
        if "trade_date" not in dm.columns:
            return []

        dm = dm.sort_values([ts_col, "trade_date"])
        grouped = dm.groupby(ts_col)

        results = []
        for ts_code, group in grouped:
            if len(group) < 20:
                continue

            stock_name = str(group[name_col].iloc[-1]) if name_col else ts_code

            # 过滤 ST
            if "ST" in stock_name.upper():
                continue

            # 取最近20个交易日的收盘价
            closes = group[close_col].astype(float).tolist()[-20:]
            opens = group[open_col].astype(float).tolist() if open_col else []
            pre_closes = group[pre_close_col].astype(float).tolist() if pre_close_col else []

            if len(closes) < 20:
                continue

            # 计算 MA
            ma5 = sum(closes[-5:]) / 5
            ma10 = sum(closes[-10:]) / 10
            ma20 = sum(closes[-20:]) / 20

            today_close = closes[-1]

            # 检查多头排列：MA5 > MA10 > MA20
            if not (ma5 > ma10 > ma20):
                continue

            # 检查收阳线：close > open 或 close > pre_close
            today_open = opens[-1] if opens else today_close
            today_pre_close = pre_closes[-1] if pre_closes else today_close
            if not (today_close > today_open or today_close > today_pre_close):
                continue

            # 计算排列强度（均线间距占价格比例）
            alignment_gap_pct = ((ma5 - ma20) / ma20) * 100 if ma20 > 0 else 0

            # 趋势一致性：最近5天收盘价逐日上涨的天数
            recent_5 = closes[-5:]
            trend_up_days = sum(1 for i in range(1, len(recent_5)) if recent_5[i] > recent_5[i - 1])
            trend_consistency = (trend_up_days / 4) * 100 if len(recent_5) >= 2 else 0

            # 评分
            alignment_score = min(alignment_gap_pct * 10, 50)  # 排列间距贡献最多50分
            trend_score = min(trend_consistency * 0.5, 50)  # 趋势一致性贡献最多50分
            total_score = min(alignment_score + trend_score, 100)

            signals = {
                "ma5": round(ma5, 2),
                "ma10": round(ma10, 2),
                "ma20": round(ma20, 2),
                "close": round(today_close, 2),
                "alignment_gap_pct": round(alignment_gap_pct, 2),
            }

            results.append(StrategyResult(
                ts_code=ts_code,
                name=stock_name,
                score=total_score,
                signals=signals,
                reason=f"MA5({ma5:.2f})>MA10({ma10:.2f})>MA20({ma20:.2f})；间距{alignment_gap_pct:.1f}%",
            ))

        return results
