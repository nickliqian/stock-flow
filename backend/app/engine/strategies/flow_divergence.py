"""价格-资金流向背离信号策略。

当价格与主力资金流向出现背离时，往往预示着趋势反转：
- 看涨背离：价格下跌但主力资金持续净流入（机构吸筹）
- 看跌背离：价格上涨但主力资金持续净流出（机构出货）
"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class FlowDivergence(BaseStrategy):
    name = "flow_divergence"
    description = "价格-资金流向背离信号：价格跌但主力吸筹（看涨），价格涨但主力出货（看跌）"
    category = "flow"
    icon = "📊"

    def required_data(self) -> List[str]:
        return ["moneyflow_multi", "daily_multi", "daily_basic", "stock_basic"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        mf_df = data.get("moneyflow_multi")
        daily_df = data.get("daily_multi")
        basic_df = data.get("daily_basic")
        sb_df = data.get("stock_basic")

        if mf_df is None or mf_df.empty:
            return []
        if daily_df is None or daily_df.empty:
            return []

        # 构建名称/行业映射
        name_map: Dict[str, str] = {}
        industry_map: Dict[str, str] = {}
        if sb_df is not None and not sb_df.empty:
            for _, row in sb_df.iterrows():
                code = str(row.get("ts_code", ""))
                if code:
                    name_map[code] = str(row.get("name", ""))
                    industry_map[code] = str(row.get("industry", ""))

        # 构建市值映射
        mv_map: Dict[str, float] = {}
        if basic_df is not None and not basic_df.empty:
            for _, row in basic_df.iterrows():
                code = str(row.get("ts_code", ""))
                mv = self._safe(row, "total_mv")
                if code and mv is not None:
                    mv_map[code] = mv

        # 按股票分组
        if "ts_code" not in mf_df.columns or "ts_code" not in daily_df.columns:
            return []
        mf_grouped = mf_df.groupby("ts_code")
        daily_grouped = daily_df.groupby("ts_code")

        results = []
        lookback = 5  # 5日趋势

        for ts_code in mf_grouped.groups:
            name = name_map.get(ts_code, ts_code)
            industry = industry_map.get(ts_code, "")

            # 过滤 ST
            if "ST" in name.upper():
                continue

            # 市值过滤：>30亿
            mv = mv_map.get(ts_code)
            if mv is not None and mv < 300000:  # 30亿 = 300000万元
                continue

            # 获取该股票的资金流数据
            try:
                stock_mf = mf_grouped.get_group(ts_code)
            except KeyError:
                continue

            if len(stock_mf) < 3:
                continue

            stock_mf = stock_mf.sort_values("trade_date")
            recent_mf = stock_mf.tail(lookback)

            # 获取该股票的日线数据
            try:
                stock_daily = daily_grouped.get_group(ts_code)
            except KeyError:
                continue

            if len(stock_daily) < 3:
                continue

            stock_daily = stock_daily.sort_values("trade_date")
            recent_daily = stock_daily.tail(lookback)

            # 计算价格趋势
            closes = recent_daily["close"].tolist()
            if not closes or len(closes) < 2 or closes[0] is None or closes[0] <= 0:
                continue
            price_trend_pct = (closes[-1] / closes[0] - 1) * 100

            # 计算主力资金净流入趋势
            flow_total = 0.0
            for _, row in recent_mf.iterrows():
                buy_lg = self._safe(row, "buy_lg_amount") or 0
                sell_lg = self._safe(row, "sell_lg_amount") or 0
                buy_elg = self._safe(row, "buy_elg_amount") or 0
                sell_elg = self._safe(row, "sell_elg_amount") or 0
                flow_total += (buy_lg - sell_lg) + (buy_elg - sell_elg)

            # 检测背离
            is_bullish = price_trend_pct < -0.5 and flow_total > 500
            is_bearish = price_trend_pct > 0.5 and flow_total < -500

            if not is_bullish and not is_bearish:
                continue

            signal_type = "bullish" if is_bullish else "bearish"

            # 评分
            price_strength = min(40, abs(price_trend_pct) * 4)
            flow_strength = min(30, abs(flow_total) / 1000 * 5)

            # 持续性
            inflow_days = 0
            for _, row in recent_mf.iterrows():
                buy_lg = self._safe(row, "buy_lg_amount") or 0
                sell_lg = self._safe(row, "sell_lg_amount") or 0
                buy_elg = self._safe(row, "buy_elg_amount") or 0
                sell_elg = self._safe(row, "sell_elg_amount") or 0
                net = (buy_lg - sell_lg) + (buy_elg - sell_elg)
                if net > 0:
                    inflow_days += 1
            outflow_days = len(recent_mf) - inflow_days
            max_dir = max(inflow_days, outflow_days)
            persistence_score = (max_dir / len(recent_mf) * 100) if len(recent_mf) > 0 else 0
            persistence_strength = min(30, persistence_score * 0.3)

            total_score = price_strength + flow_strength + persistence_strength

            signals = {
                "signal_type": signal_type,
                "price_trend_pct": round(price_trend_pct, 2),
                "main_fund_net_wan": round(flow_total, 2),
                "persistence_days": max_dir,
                "persistence_score": round(persistence_score, 1),
                "total_mv_yi": round(mv / 10000, 2) if mv else None,
                "industry": industry,
            }

            if signal_type == "bullish":
                reason = (
                    f"看涨背离: 价格{abs(price_trend_pct):.1f}%"
                    f" + 主力净流入{flow_total:.0f}万"
                    f" + 持续{max_dir}天"
                )
            else:
                reason = (
                    f"看跌背离: 价格+{price_trend_pct:.1f}%"
                    f" + 主力净流出{abs(flow_total):.0f}万"
                    f" + 持续{max_dir}天"
                )

            results.append(StrategyResult(
                ts_code=ts_code,
                name=name,
                score=min(100, total_score),
                signals=signals,
                reason=reason,
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results
