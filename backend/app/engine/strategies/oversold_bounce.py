"""超跌反弹——筛选近20日跌幅大、换手率高的中小市值反弹标的。

基于 daily_multi（最近20个交易日OHLCV）计算区间跌幅，
配合换手率和市值筛选，寻找超跌后可能出现反弹的标的。
"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class OversoldBounce(BaseStrategy):
    name = "oversold_bounce"
    description = "近20日跌幅≥15%，日均换手率≥3%，市值30~500亿的超跌反弹标的"
    category = "momentum"
    icon = "🔥"

    def required_data(self) -> List[str]:
        return ["daily_multi", "daily_basic"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        dm = data.get("daily_multi")
        if dm is None or dm.empty:
            return []

        db = data.get("daily_basic")

        # 找列名
        code_col = self._find_col(dm, ["ts_code"])
        close_col = self._find_col(dm, ["close", "cl"])
        pct_col = self._find_col(dm, ["pct_change", "pct_chg", "pct"])
        turnover_col = self._find_col(dm, ["turnover_rate", "tr"])

        if not all([code_col, close_col]):
            return []

        # 市值查找表
        mv_map: Dict[str, float] = {}
        name_map: Dict[str, str] = {}
        if db is not None and not db.empty:
            db_code_col = self._find_col(db, ["ts_code"])
            db_mv_col = self._find_col(db, ["total_mv", "tmv"])
            db_name_col = self._find_col(db, ["name", "nm"])
            if db_code_col and db_mv_col:
                for _, r in db.iterrows():
                    tc = str(r.get(db_code_col, ""))
                    mv = self._safe(r, db_mv_col)
                    if tc and mv is not None:
                        mv_map[tc] = mv
                    if db_name_col:
                        nm = str(r.get(db_name_col, ""))
                        if tc and nm:
                            name_map[tc] = nm

        # 按股票分组，计算60日跌幅和平均换手率
        grouped = dm.groupby(code_col)
        results = []
        for ts_code, gdf in grouped:
            ts_code = str(ts_code)
            if len(gdf) < 2:
                continue

            # 市值筛选
            mv = mv_map.get(ts_code)
            if mv is None:
                continue
            if mv < 3000000 or mv > 50000000:
                continue

            # 按日期排序取首尾计算跌幅
            closes = gdf[close_col].dropna().tolist()
            if len(closes) < 2:
                continue
            first_close = closes[0]
            last_close = closes[-1]
            if first_close <= 0:
                continue
            drop_pct = (last_close - first_close) / first_close * 100

            if drop_pct >= -15:
                continue  # 跌幅不够（20日窗口，15%已显著）

            # 平均换手率
            avg_turnover = None
            if turnover_col:
                turnovers = gdf[turnover_col].dropna()
                if not turnovers.empty:
                    avg_turnover = turnovers.mean()

            if avg_turnover is not None and avg_turnover < 3:
                continue

            stock_name = name_map.get(ts_code, ts_code)

            # 排除 ST
            if "ST" in stock_name.upper():
                continue

            # 评分
            drop_score = min(50, max(0, abs(drop_pct) / 30 * 50))
            turnover_score = min(30, max(0, (avg_turnover or 0) / 10 * 30))
            mv_score = min(20, max(0, (50000000 - mv) / 47000000 * 20))
            total_score = drop_score + turnover_score + mv_score

            signals: Dict[str, Any] = {
                "drop_pct_60d": round(drop_pct, 2),
                "total_mv_yi": round(mv / 10000, 2),
            }
            if avg_turnover is not None:
                signals["avg_turnover_rate"] = round(avg_turnover, 2)

            reason_parts = [
                f"60日跌幅{abs(drop_pct):.1f}%",
                f"市值{mv/10000:.0f}亿",
            ]
            if avg_turnover is not None:
                reason_parts.append(f"日均换手{avg_turnover:.1f}%")

            results.append(StrategyResult(
                ts_code=ts_code,
                name=stock_name,
                score=min(100, total_score),
                signals=signals,
                reason="；".join(reason_parts),
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results
