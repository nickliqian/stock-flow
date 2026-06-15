"""成交量异动选股——筛选换手率异常放大、量比突出且价格正向的活跃标的。

设计说明：
Tushare 的 fina_indicator 接口需要逐股查询（必填 ts_code），
无法批量加载全市场财务数据。因此本策略改为基于 daily_basic
的「量价异动」筛选，利用可批量加载的换手率、量比、市值等字段。
"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class VolumeAnomaly(BaseStrategy):
    name = "volume_anomaly"
    description = "换手率>5%+量比>1.5+正涨幅+市值>30亿，量价异动的活跃标的"
    category = "momentum"
    icon = "📊"

    def required_data(self) -> List[str]:
        return ["daily_basic", "daily"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        db = data.get("daily_basic")
        if db is None or db.empty:
            return []

        daily = data.get("daily")

        # Build daily lookup: ts_code -> pct_chg
        daily_map: Dict[str, float] = {}
        if daily is not None and not daily.empty:
            d_code = self._find_col(daily, ["ts_code"])
            d_pct = self._find_col(daily, ["pct_chg", "pct_change"])
            if d_code and d_pct:
                for _, r in daily.iterrows():
                    tc = str(r.get(d_code, ""))
                    pct = self._safe(r, d_pct)
                    if tc and pct is not None:
                        daily_map[tc] = pct

        # Find columns in daily_basic
        code_col = self._find_col(db, ["ts_code"])
        name_col = self._find_col(db, ["name", "nm"])
        tr_col = self._find_col(db, ["turnover_rate", "tr"])
        vr_col = self._find_col(db, ["volume_ratio", "vr"])
        mv_col = self._find_col(db, ["total_mv", "tmv"])
        close_col = self._find_col(db, ["close", "cl"])

        if not all([code_col, tr_col]):
            return []

        results = []
        for _, row in db.iterrows():
            ts_code = str(row.get(code_col, ""))
            stock_name = str(row.get(name_col, "")) if name_col else ts_code

            # Skip ST
            if "ST" in stock_name.upper():
                continue

            turnover = self._safe(row, tr_col)
            if turnover is None or turnover < 5:
                continue  # Not active enough

            # Volume ratio filter
            vr = self._safe(row, vr_col) if vr_col else None
            if vr is not None and vr < 1.5:
                continue

            # Market cap filter (> 30亿)
            mv = self._safe(row, mv_col) if mv_col else None
            if mv is not None and mv < 3000000:  # 30亿 in 万元
                continue

            # Positive price momentum
            pct = daily_map.get(ts_code)
            if pct is not None and pct <= 0:
                continue

            close = self._safe(row, close_col) if close_col else None

            # Scoring
            # Higher turnover → higher score (0-40)
            tr_score = min(40, max(0, (turnover - 5) / 20 * 40))
            # Higher volume ratio → higher score (0-30)
            vr_score = min(30, max(0, ((vr or 1.5) - 1.5) / 3 * 30))
            # Positive momentum → higher score (0-20)
            pct_score = min(20, max(0, (pct or 0) / 5 * 20)) if pct is not None else 10
            # Moderate market cap preferred (smaller = more弹性) (0-10)
            mv_score = min(10, max(0, (50000000 - (mv or 50000000)) / 47000000 * 10))

            total_score = tr_score + vr_score + pct_score + mv_score

            signals: Dict[str, Any] = {
                "turnover_rate": round(turnover, 2),
            }
            if vr is not None:
                signals["volume_ratio"] = round(vr, 2)
            if mv is not None:
                signals["total_mv_yi"] = round(mv / 10000, 2)
            if pct is not None:
                signals["pct_chg"] = round(pct, 2)
            if close is not None:
                signals["close"] = round(close, 2)

            reason_parts = [f"换手率{turnover:.1f}%"]
            if vr is not None:
                reason_parts.append(f"量比{vr:.1f}")
            if pct is not None:
                reason_parts.append(f"涨幅{pct:.1f}%")
            if mv is not None:
                reason_parts.append(f"市值{mv/10000:.0f}亿")

            results.append(StrategyResult(
                ts_code=ts_code,
                name=stock_name,
                score=min(100, total_score),
                signals=signals,
                reason="；".join(reason_parts),
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results
