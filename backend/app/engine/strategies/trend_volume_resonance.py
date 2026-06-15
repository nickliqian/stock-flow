"""趋势+量能共振——均线多头+放量确认的双重验证策略。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class TrendVolumeResonance(BaseStrategy):
    name = "trend_volume_resonance"
    description = "趋势+量能共振：MA5>MA10+量比>1.5+涨幅>1%的共振信号"
    category = "combo"
    icon = "🔥"

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
        close_col = self._find_col(sf, ["close", "cl"])
        pct_col = self._find_col(sf, ["pct_change", "pct_chg", "pct"])
        vol_col_sf = self._find_col(sf, ["vol"])

        dm_ts_col = self._find_col(dm, ["ts_code", "tc"])
        dm_close_col = self._find_col(dm, ["close", "cl"])
        dm_vol_col = self._find_col(dm, ["vol"])

        if not all([ts_col, close_col, pct_col, dm_ts_col, dm_close_col, dm_vol_col]):
            return []

        if "trade_date" not in dm.columns:
            return []

        # 从 daily_multi 计算5日均量
        dm_dates = sorted(dm["trade_date"].unique(), reverse=True)
        recent_5_dates = dm_dates[:5] if len(dm_dates) >= 5 else dm_dates
        if not recent_5_dates:
            return []

        recent_dm = dm[dm["trade_date"].isin(recent_5_dates)]
        avg_vol_5d = recent_dm.groupby(dm_ts_col)[dm_vol_col].mean().to_dict()

        # 从 daily_multi 计算 MA5 和 MA10
        dm_sorted = dm.sort_values([dm_ts_col, "trade_date"])
        ma_data = {}
        for ts_code, group in dm_sorted.groupby(dm_ts_col):
            closes = group[dm_close_col].astype(float).tolist()
            if len(closes) >= 10:
                ma5 = sum(closes[-5:]) / 5
                ma10 = sum(closes[-10:]) / 10
                ma_data[ts_code] = (ma5, ma10)
            elif len(closes) >= 5:
                ma5 = sum(closes[-5:]) / 5
                ma10 = sum(closes) / len(closes)
                ma_data[ts_code] = (ma5, ma10)

        results = []
        for _, row in sf.iterrows():
            ts_code = str(row.get(ts_col, ""))
            stock_name = str(row.get(name_col, "")) if name_col else ts_code

            # 过滤 ST
            if "ST" in stock_name.upper():
                continue

            close = self._safe(row, close_col)
            pct_change = self._safe(row, pct_col)
            today_vol = self._safe(row, vol_col_sf) if vol_col_sf else None

            if close is None or pct_change is None:
                continue

            # 过滤低价股
            if close < 2:
                continue

            # 条件1：涨幅 > 1%
            if pct_change < 1:
                continue

            # 条件2：MA5 > MA10（多头趋势）
            ma = ma_data.get(ts_code)
            if not ma:
                continue
            ma5, ma10 = ma
            if ma5 <= ma10:
                continue

            # 条件3：量比 > 1.5（放量确认）
            avg_vol = avg_vol_5d.get(ts_code)
            if not avg_vol or avg_vol <= 0:
                continue
            if today_vol is None:
                continue
            volume_ratio = today_vol / avg_vol
            if volume_ratio < 1.5:
                continue

            # 评分
            trend_gap = ((ma5 - ma10) / ma10) * 100 if ma10 > 0 else 0
            trend_score = min(trend_gap * 10, 40)  # 趋势间距最多40分
            vol_score = min(volume_ratio * 15, 40)  # 量比最多40分
            pct_score = min(pct_change * 10, 20)    # 涨幅最多20分
            total_score = min(trend_score + vol_score + pct_score, 100)

            signals = {
                "ma5": round(ma5, 2),
                "ma10": round(ma10, 2),
                "trend_gap_pct": round(trend_gap, 2),
                "volume_ratio": round(volume_ratio, 2),
                "pct_change": round(pct_change, 2),
                "close": round(close, 2),
            }

            results.append(StrategyResult(
                ts_code=ts_code,
                name=stock_name,
                score=total_score,
                signals=signals,
                reason=f"MA5({ma5:.2f})>MA10({ma10:.2f})；量比{volume_ratio:.1f}；涨幅{pct_change:.1f}%",
            ))

        return results
