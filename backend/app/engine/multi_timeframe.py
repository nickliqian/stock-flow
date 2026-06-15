"""多时间框架动量共振引擎 (Multi-Timeframe Momentum Resonance Engine)

核心功能：
1. 计算 5 日、10 日、20 日三个时间框架的动量
2. 检测多时间框架动量方向一致性
3. 综合评分（alignment_score 0-100）
4. 支持全市场分析和单股深度分析

创新点：当多个时间框架的动量方向一致时，构成强烈的共振确认信号，
这是趋势跟踪和动量策略的重要增强维度。
"""

import logging
import math
from typing import Dict, Any, List, Optional
from collections import defaultdict

import pandas as pd
import numpy as np

from ..models import SessionLocal, StockBasic

logger = logging.getLogger(__name__)

# 时间框架定义
TIMEFRAMES = [
    {"days": 5, "label": "5日", "weight": 0.33},
    {"days": 10, "label": "10日", "weight": 0.33},
    {"days": 20, "label": "20日", "weight": 0.34},
]

# 最大基础分 = 33 * 3 ≈ 99，加上 bonus 最高 100
MAX_BASE_SCORE_PER_TF = 33
VOLUME_CONFIRM_BONUS = 10       # 成交量确认方向奖励
FULL_ALIGNMENT_BONUS = 15       # 三时间框架完全对齐奖励


class MultiTimeframeEngine:
    """多时间框架动量共振引擎。"""

    def __init__(self, loader, cache):
        """
        Args:
            loader: StrategyDataLoader 实例
            cache: CacheService 实例
        """
        self.loader = loader
        self.cache = cache

    # ================================================================
    # 公开方法
    # ================================================================

    def analyze(self, trade_date: str = None) -> Dict[str, Any]:
        """分析全市场多时间框架动量共振。

        Returns:
            {
                "trade_date": str,
                "results": [...],
                "summary": {...},
            }
        """
        if not trade_date:
            trade_date = self._get_latest_trade_date()

        # 加载数据
        data = self.loader.load(trade_date, ["daily_multi", "daily_basic", "stock_basic"])
        daily_multi_df = data.get("daily_multi", pd.DataFrame())
        daily_basic_df = data.get("daily_basic", pd.DataFrame())
        stock_basic_df = data.get("stock_basic", pd.DataFrame())

        if daily_multi_df.empty:
            return {
                "trade_date": trade_date,
                "results": [],
                "summary": {"error": "缺少 daily_multi 数据"},
            }

        # 获取股票名称映射
        name_map = {}
        if not stock_basic_df.empty:
            for _, row in stock_basic_df.iterrows():
                name_map[row.get("ts_code", "")] = row.get("name", "")

        # 按股票分组计算共振评分
        results = []
        grouped = daily_multi_df.groupby("ts_code")

        for ts_code, group in grouped:
            if len(group) < 20:
                continue

            stock_name = name_map.get(ts_code, ts_code)

            # 过滤 ST 股
            if "ST" in stock_name.upper():
                continue

            try:
                result = self._compute_stock_alignment(ts_code, stock_name, group)
                if result is not None:
                    results.append(result)
            except Exception as exc:
                logger.debug("Failed to compute alignment for %s: %s", ts_code, exc)
                continue

        # 按 alignment_score 降序排序
        results.sort(key=lambda x: x.get("alignment_score", 0), reverse=True)

        # 统计摘要
        summary = self._compute_summary(results)

        return {
            "trade_date": trade_date,
            "results": results,
            "summary": summary,
        }

    def analyze_stock(self, ts_code: str, trade_date: str = None) -> Dict[str, Any]:
        """单只股票的深度多时间框架分析。

        Returns:
            {
                "ts_code": str,
                "name": str,
                "alignment_score": float,
                "timeframe_details": [...],
                "signals": {...},
                "daily_data": [...],
            }
        """
        if not trade_date:
            trade_date = self._get_latest_trade_date()

        # 加载数据
        data = self.loader.load(trade_date, ["daily_multi", "daily_basic", "stock_basic"])
        daily_multi_df = data.get("daily_multi", pd.DataFrame())
        daily_basic_df = data.get("daily_basic", pd.DataFrame())
        stock_basic_df = data.get("stock_basic", pd.DataFrame())

        if daily_multi_df.empty:
            return {"error": "缺少 daily_multi 数据", "ts_code": ts_code}

        # 获取股票名称
        stock_name = ts_code
        if not stock_basic_df.empty:
            match = stock_basic_df[stock_basic_df["ts_code"] == ts_code]
            if not match.empty:
                stock_name = match.iloc[0].get("name", ts_code)

        # 筛选该股票数据
        stock_data = daily_multi_df[daily_multi_df["ts_code"] == ts_code].copy()
        if stock_data.empty or len(stock_data) < 5:
            return {"error": "该股票数据不足", "ts_code": ts_code, "name": stock_name}

        stock_data = stock_data.sort_values("trade_date")
        result = self._compute_stock_alignment(ts_code, stock_name, stock_data)

        if result is None:
            return {"error": "无法计算共振评分", "ts_code": ts_code, "name": stock_name}

        # 补充每日明细
        daily_details = []
        for _, row in stock_data.tail(20).iterrows():
            daily_details.append({
                "trade_date": str(row.get("trade_date", "")),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "vol": float(row.get("vol", 0)),
                "amount": float(row.get("amount", 0)),
                "pct_chg": float(row.get("pct_chg", 0)),
            })

        result["daily_data"] = daily_details
        return result

    # ================================================================
    # 内部方法
    # ================================================================

    def _compute_stock_alignment(self, ts_code: str, name: str, group: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """计算单只股票的多时间框架共振评分。"""
        # 确保按日期排序
        if "trade_date" in group.columns:
            group = group.sort_values("trade_date")

        closes = group["close"].astype(float).tolist()
        volumes = group["vol"].astype(float).tolist() if "vol" in group.columns else []

        if len(closes) < 20:
            return None

        latest_close = closes[-1]

        # ---- 计算每个时间框架的指标 ----
        timeframe_details = []
        positive_count = 0  # 正动量的时间框架数量
        total_score = 0
        volume_confirms_count = 0

        for tf in TIMEFRAMES:
            days = tf["days"]
            if len(closes) < days + 1:
                timeframe_details.append({
                    "days": days,
                    "label": tf["label"],
                    "price_momentum": 0,
                    "volume_momentum": 0,
                    "above_ma": False,
                    "direction": "neutral",
                    "score": 0,
                })
                continue

            # 价格动量: (close - close_N) / close_N * 100
            close_n = closes[-(days + 1)]
            price_momentum = ((latest_close - close_n) / close_n * 100) if close_n > 0 else 0

            # 成交量动量: avg_recent / avg_N * 100
            volume_momentum = 0
            if volumes and len(volumes) >= days + 1:
                avg_recent = np.mean(volumes[-days:]) if days > 0 else 0
                avg_old = np.mean(volumes[-(days + 1):-1]) if days > 1 else volumes[-(days + 1)]
                if avg_old > 0:
                    volume_momentum = (avg_recent / avg_old) * 100

            # 趋势方向: close > MA_N
            ma_n = np.mean(closes[-days:])
            above_ma = latest_close > ma_n

            # 方向判定
            if price_momentum > 0 and above_ma:
                direction = "bullish"
                positive_count += 1
            elif price_momentum < 0 and not above_ma:
                direction = "bearish"
            else:
                direction = "neutral"

            # 成交量确认方向: 价涨量增 or 价跌量缩
            volume_confirms = False
            if direction == "bullish" and volume_momentum > 100:
                volume_confirms = True
                volume_confirms_count += 1
            elif direction == "bearish" and volume_momentum < 100:
                volume_confirms = True
                volume_confirms_count += 1

            # 单时间框架基础分（0-33）
            # 价格动量贡献
            pm_score = min(abs(price_momentum) * 3, 20)  # 最多20分
            # 趋势一致性贡献
            trend_score = 8 if above_ma and price_momentum > 0 else (4 if above_ma or price_momentum > 0 else 0)
            # 成交量贡献
            vol_score = 5 if volume_confirms else 0

            tf_score = min(pm_score + trend_score + vol_score, MAX_BASE_SCORE_PER_TF)

            # 正动量方向给满分权重，负方向不扣分但贡献低
            if direction == "bullish":
                tf_score = MAX_BASE_SCORE_PER_TF  # 对齐方向给满分
            elif direction == "neutral":
                tf_score = tf_score * 0.5  # 中性减半
            else:
                tf_score = max(tf_score * 0.2, 0)  # 空头方向保留很少

            total_score += tf_score

            timeframe_details.append({
                "days": days,
                "label": tf["label"],
                "price_momentum": round(price_momentum, 2),
                "volume_momentum": round(volume_momentum, 2),
                "above_ma": above_ma,
                "ma_value": round(ma_n, 2),
                "direction": direction,
                "volume_confirms": volume_confirms,
                "score": round(tf_score, 2),
            })

        # ---- 加分项 ----
        # 成交量确认加分: 如果所有时间框架的成交量都确认方向
        if volume_confirms_count == 3:
            total_score += VOLUME_CONFIRM_BONUS

        # 多时间框架对齐加分: 3/3 同向
        if positive_count == 3:
            total_score += FULL_ALIGNMENT_BONUS
        elif positive_count == 2:
            total_score += 5  # 2/3 对齐也有小幅加分

        # 限制总分 0-100
        alignment_score = min(max(round(total_score, 2), 0), 100)

        # 生成信号
        signals = self._generate_signals(alignment_score, positive_count, timeframe_details)

        return {
            "ts_code": ts_code,
            "name": name,
            "close": round(latest_close, 2),
            "alignment_score": alignment_score,
            "positive_timeframes": positive_count,
            "volume_confirms_count": volume_confirms_count,
            "timeframe_details": timeframe_details,
            "signals": signals,
        }

    def _generate_signals(self, alignment_score: float, positive_count: int, details: List[Dict]) -> Dict[str, Any]:
        """生成综合信号。"""
        # 判断信号方向
        if alignment_score >= 60 and positive_count >= 2:
            direction = "bullish"
            direction_label = "看多"
        elif alignment_score < 40 and positive_count == 0:
            direction = "bearish"
            direction_label = "看空"
        else:
            direction = "neutral"
            direction_label = "中性"

        # 共振等级
        if alignment_score >= 80:
            level = "strong"
            level_label = "强共振"
        elif alignment_score >= 60:
            level = "moderate"
            level_label = "中等共振"
        elif alignment_score >= 40:
            level = "weak"
            level_label = "弱共振"
        else:
            level = "none"
            level_label = "无共振"

        return {
            "direction": direction,
            "direction_label": direction_label,
            "level": level,
            "level_label": level_label,
        }

    def _compute_summary(self, results: List[Dict]) -> Dict[str, Any]:
        """计算全市场分析摘要。"""
        if not results:
            return {
                "total_analyzed": 0,
                "strong_alignment_count": 0,
                "bullish_count": 0,
                "avg_score": 0,
            }

        scores = [r.get("alignment_score", 0) for r in results]
        strong_count = sum(1 for s in scores if s >= 80)
        bullish_count = sum(1 for r in results if r.get("signals", {}).get("direction") == "bullish")
        moderate_count = sum(1 for s in scores if 60 <= s < 80)
        weak_count = sum(1 for s in scores if 40 <= s < 60)
        none_count = sum(1 for s in scores if s < 40)

        return {
            "total_analyzed": len(results),
            "strong_alignment_count": strong_count,
            "moderate_alignment_count": moderate_count,
            "weak_alignment_count": weak_count,
            "no_alignment_count": none_count,
            "bullish_count": bullish_count,
            "bearish_count": sum(1 for r in results if r.get("signals", {}).get("direction") == "bearish"),
            "avg_score": round(np.mean(scores), 2) if scores else 0,
            "max_score": round(max(scores), 2) if scores else 0,
        }

    def _get_latest_trade_date(self) -> str:
        """获取最新交易日。"""
        try:
            from ..utils import get_latest_trade_date
            return get_latest_trade_date(self.cache)
        except Exception:
            from datetime import datetime
            return datetime.now().strftime("%Y%m%d")
