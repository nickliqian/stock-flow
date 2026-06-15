"""放量突破——筛选今日成交量放大且涨幅靠前的强势股。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class VolumeBreakthrough(BaseStrategy):
    name = "volume_breakthrough"
    description = "放量突破：成交量>5日均量2倍且涨幅>3%的强势标的"
    category = "momentum"
    icon = "🚀"

    def required_data(self) -> List[str]:
        return ["stk_factor", "daily_multi"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        sf = data.get("stk_factor")
        dm = data.get("daily_multi")
        if sf is None or sf.empty or dm is None or dm.empty:
            return []

        # 确定列名
        ts_col = self._find_col(sf, ["ts_code", "tc"])
        name_col = self._find_col(sf, ["name", "nm"])
        vol_col = self._find_col(sf, ["vol"])
        amt_col = self._find_col(sf, ["amount", "amt"])
        pct_col = self._find_col(sf, ["pct_change", "pct_chg", "pct"])
        close_col = self._find_col(sf, ["close", "cl"])

        dm_vol_col = self._find_col(dm, ["vol"])
        dm_ts_col = self._find_col(dm, ["ts_code", "tc"])

        if not all([ts_col, vol_col, pct_col, close_col, dm_vol_col, dm_ts_col]):
            return []

        # 从 daily_multi 计算 5 日平均成交量
        # 取 daily_multi 中 trade_date 的 top 5（最近5个交易日）
        dm_dates = sorted(dm["trade_date"].unique(), reverse=True) if "trade_date" in dm.columns else []
        recent_5_dates = dm_dates[:5] if len(dm_dates) >= 5 else dm_dates
        if not recent_5_dates:
            return []

        recent_dm = dm[dm["trade_date"].isin(recent_5_dates)]
        avg_vol_5d = recent_dm.groupby(dm_ts_col)[dm_vol_col].mean().to_dict()

        results = []
        for _, row in sf.iterrows():
            ts_code = str(row.get(ts_col, ""))
            stock_name = str(row.get(name_col, "")) if name_col else ts_code

            # 过滤 ST
            if "ST" in stock_name.upper():
                continue

            close = self._safe(row, close_col)
            pct_change = self._safe(row, pct_col)
            today_vol = self._safe(row, vol_col)
            avg_vol = avg_vol_5d.get(ts_code)

            if close is None or pct_change is None or today_vol is None or avg_vol is None:
                continue
            if avg_vol <= 0:
                continue

            # 过滤低价股
            if close < 2:
                continue

            # 放量：今日成交量 > 5日均量 * 2
            volume_ratio = today_vol / avg_vol
            if volume_ratio < 2:
                continue

            # 涨幅 > 3%
            if pct_change < 3:
                continue

            # 评分
            vr_score = min(volume_ratio * 20, 60)  # 量比贡献最多60分
            pct_score = min(pct_change * 5, 40)  # 涨幅贡献最多40分
            total_score = min(vr_score + pct_score, 100)

            signals = {
                "volume_ratio": round(volume_ratio, 2),
                "pct_change": round(pct_change, 2),
                "today_vol": round(today_vol, 2),
                "avg_vol_5d": round(avg_vol, 2),
                "close": round(close, 2),
            }
            if amt_col:
                amt = self._safe(row, amt_col)
                if amt is not None:
                    signals["amount"] = round(amt, 2)

            results.append(StrategyResult(
                ts_code=ts_code,
                name=stock_name,
                score=total_score,
                signals=signals,
                reason=f"量比{volume_ratio:.1f}倍(今日{today_vol:.0f}/5日均{avg_vol:.0f})；涨幅{pct_change:.1f}%",
            ))

        return results
