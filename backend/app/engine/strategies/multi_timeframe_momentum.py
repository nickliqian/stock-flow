"""多时间框架动量共振策略。

筛选多时间框架（5日/10日/20日）动量方向一致的标的，
当 alignment_score >= 60 且 2+ 时间框架正向动量时触发。
"""

from typing import List, Dict, Any
import pandas as pd
import numpy as np

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class MultiTimeframeMomentum(BaseStrategy):
    name = "multi_timeframe_momentum"
    description = "多时间框架动量共振：5日/10日/20日动量方向一致时触发"
    category = "momentum"
    icon = "📐"

    # 时间框架定义
    TIMEFRAMES = [5, 10, 20]

    def required_data(self) -> List[str]:
        return ["daily_multi"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        dm = data.get("daily_multi")
        if dm is None or dm.empty:
            return []

        # 确定列名
        ts_col = self._find_col(dm, ["ts_code", "tc"])
        close_col = self._find_col(dm, ["close", "cl"])
        vol_col = self._find_col(dm, ["vol", "volume"])
        name_col = self._find_col(dm, ["name", "nm"])

        if not all([ts_col, close_col]):
            return []

        if "trade_date" not in dm.columns:
            return []

        dm = dm.sort_values([ts_col, "trade_date"])
        grouped = dm.groupby(ts_col)

        results = []
        for ts_code, group in grouped:
            if len(group) < 21:
                continue

            stock_name = str(group[name_col].iloc[-1]) if name_col else ts_code

            # 过滤 ST
            if "ST" in stock_name.upper():
                continue

            closes = group[close_col].astype(float).tolist()
            volumes = group[vol_col].astype(float).tolist() if vol_col else []

            if len(closes) < 21:
                continue

            latest_close = closes[-1]

            # 计算三个时间框架的动量
            positive_count = 0
            total_score = 0
            timeframe_scores = []

            for days in self.TIMEFRAMES:
                if len(closes) < days + 1:
                    timeframe_scores.append(0)
                    continue

                close_n = closes[-(days + 1)]
                price_momentum = ((latest_close - close_n) / close_n * 100) if close_n > 0 else 0

                ma_n = np.mean(closes[-days:])
                above_ma = latest_close > ma_n

                # 成交量动量
                volume_momentum = 0
                if volumes and len(volumes) >= days + 1:
                    avg_recent = np.mean(volumes[-days:])
                    avg_old = np.mean(volumes[-(days + 1):-1]) if days > 1 else volumes[-(days + 1)]
                    if avg_old > 0:
                        volume_momentum = (avg_recent / avg_old) * 100

                # 方向判定
                is_bullish = price_momentum > 0 and above_ma
                if is_bullish:
                    positive_count += 1

                # 单时间框架评分
                pm_score = min(abs(price_momentum) * 3, 20)
                trend_score = 8 if is_bullish else (4 if above_ma or price_momentum > 0 else 0)
                vol_score = 5 if volume_momentum > 100 and is_bullish else 0

                tf_score = min(pm_score + trend_score + vol_score, 33)
                if is_bullish:
                    tf_score = 33
                elif price_momentum > 0 or above_ma:
                    tf_score = tf_score * 0.5
                else:
                    tf_score = max(tf_score * 0.2, 0)

                total_score += tf_score
                timeframe_scores.append(tf_score)

            # 加分项
            if positive_count == 3:
                total_score += 15
            elif positive_count == 2:
                total_score += 5

            alignment_score = min(max(round(total_score, 2), 0), 100)

            # 筛选条件: alignment_score >= 60 且至少 2 个时间框架正向动量
            if alignment_score < 60 or positive_count < 2:
                continue

            signals = {
                "alignment_score": alignment_score,
                "positive_timeframes": positive_count,
                "5d_score": round(timeframe_scores[0], 2),
                "10d_score": round(timeframe_scores[1], 2),
                "20d_score": round(timeframe_scores[2], 2),
            }

            # 生成理由
            tf_labels = []
            for i, days in enumerate(self.TIMEFRAMES):
                if timeframe_scores[i] >= 25:
                    tf_labels.append(f"{days}日强")
                elif timeframe_scores[i] >= 15:
                    tf_labels.append(f"{days}日中")

            reason = f"共振评分{alignment_score}；{'+'.join(tf_labels) if tf_labels else '多框架对齐'}"

            results.append(StrategyResult(
                ts_code=ts_code,
                name=stock_name,
                score=alignment_score,
                signals=signals,
                reason=reason,
            ))

        return results
