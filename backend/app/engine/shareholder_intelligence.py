"""股东情报引擎——从股东增减持、股东人数变动、前十大股东三个维度分析。

分析维度:
1. 股东增减持分析 — 检测大股东增减持行为，判断内情人信号
2. 股东人数变动分析 — 通过股东人数变化判断筹码集中/分散
3. 前十大股东分析 — 分析股权结构、机构持仓变化
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import pandas as pd

from ..clients.tushare import TuShareClient
from ..cache import CacheService
from ..utils import get_latest_trade_date

logger = logging.getLogger(__name__)


class ShareholderIntelligenceEngine:
    """股东情报引擎——分析股东增减持、人数变动和前十大股东结构。"""

    def __init__(self, client: TuShareClient, cache: CacheService):
        self.client = client
        self.cache = cache

    # ------------------------------------------------------------------
    # 1. 股东增减持分析
    # ------------------------------------------------------------------
    def analyze_holder_trade(
        self,
        start_date: str = None,
        end_date: str = None,
        lookback_days: int = 30,
        min_change_amount: float = 0,
    ) -> Dict[str, Any]:
        """分析股东增减持行为。

        从 TuShare stk_holdertrade API 获取数据，分析大股东增减持动态。
        返回: {stocks: [...], summary: {...}}
        """
        if not end_date:
            end_date = get_latest_trade_date(self.cache)
        if not start_date:
            dt = datetime.strptime(end_date, "%Y%m%d")
            start_dt = dt - timedelta(days=lookback_days)
            start_date = start_dt.strftime("%Y%m%d")

        try:
            df = self.client.get_stk_holdertrade(
                start_date=start_date, end_date=end_date
            )
        except Exception as exc:
            logger.warning("stk_holdertrade load failed: %s", exc)
            df = None

        if df is None or df.empty:
            return {
                "stocks": [],
                "summary": {
                    "total_records": 0,
                    "increase_count": 0,
                    "decrease_count": 0,
                    "net_increase_amount": 0,
                },
                "period": {"start_date": start_date, "end_date": end_date},
            }

        # 解析增减持类型
        # stk_holdertrade 字段: ts_code, ann_date, holder_name, holder_type,
        #   in_de (IN=增持, DE=减持), change_vol, change_ratio, after_share,
        #   after_ratio, avg_price, total_share
        stocks = []
        for _, row in df.iterrows():
            ts_code = str(row.get("ts_code", ""))
            holder_name = str(row.get("holder_name", ""))
            in_de = str(row.get("in_de", ""))
            change_shares = self._safe_float(row, "change_vol")
            change_ratio = self._safe_float(row, "change_ratio")
            after_ratio = self._safe_float(row, "after_ratio")
            avg_price = self._safe_float(row, "avg_price")
            ann_date = str(row.get("ann_date", ""))
            holder_type = str(row.get("holder_type", ""))

            # 判断增减方向: in_de == "IN" → 增持, "DE" → 减持
            # change_vol 始终为正数，不能用来判断方向，必须用 in_de
            if in_de:
                is_increase = in_de == "IN"
            else:
                # in_de 为空时的 fallback（不太可能遇到）
                is_increase = change_shares is not None and change_shares > 0

            stocks.append({
                "ts_code": ts_code,
                "holder_name": holder_name,
                "holder_type": holder_type,
                "change_type": "increase" if is_increase else "decrease",
                "change_shares": round(change_shares, 2) if change_shares else 0,
                "change_ratio_pct": round(change_ratio, 4) if change_ratio else 0,
                "after_ratio_pct": round(after_ratio, 4) if after_ratio else 0,
                "avg_price": round(avg_price, 2) if avg_price else 0,
                "ann_date": ann_date,
            })

        # 按绝对增减持金额排序
        stocks.sort(key=lambda x: abs(x["change_shares"]), reverse=True)

        increase_count = sum(1 for s in stocks if s["change_type"] == "increase")
        decrease_count = sum(1 for s in stocks if s["change_type"] == "decrease")
        net_amount = sum(
            s["change_shares"] for s in stocks if s["change_type"] == "increase"
        ) - sum(
            abs(s["change_shares"]) for s in stocks if s["change_type"] == "decrease"
        )

        return {
            "stocks": stocks[:200],
            "summary": {
                "total_records": len(stocks),
                "increase_count": increase_count,
                "decrease_count": decrease_count,
                "net_increase_amount": round(net_amount, 2),
            },
            "period": {"start_date": start_date, "end_date": end_date},
        }

    # ------------------------------------------------------------------
    # 2. 股东人数变动分析
    # ------------------------------------------------------------------
    def analyze_holder_num(
        self,
        ts_code: str = None,
        start_date: str = None,
        end_date: str = None,
        lookback_days: int = 90,
    ) -> Dict[str, Any]:
        """分析股东人数变动趋势。

        股东人数减少 → 筹码集中（可能有主力吸筹）
        股东人数增加 → 筹码分散（可能有主力派发）
        返回: {stocks: [...], summary: {...}}
        """
        if not end_date:
            end_date = get_latest_trade_date(self.cache)
        if not start_date:
            dt = datetime.strptime(end_date, "%Y%m%d")
            start_dt = dt - timedelta(days=lookback_days)
            start_date = start_dt.strftime("%Y%m%d")

        try:
            df = self.client.get_stk_holdernumber(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
            )
        except Exception as exc:
            logger.warning("stk_holdernum load failed: %s", exc)
            df = None

        if df is None or df.empty:
            return {
                "stocks": [],
                "summary": {
                    "total_stocks": 0,
                    "concentrating_count": 0,
                    "dispersing_count": 0,
                },
                "period": {"start_date": start_date, "end_date": end_date},
            }

        # 按股票分组，分析人数变动趋势
        stock_analysis = []
        code_col = "ts_code" if "ts_code" in df.columns else None
        if not code_col:
            return {
                "stocks": [],
                "summary": {
                    "total_stocks": 0,
                    "concentrating_count": 0,
                    "dispersing_count": 0,
                },
                "period": {"start_date": start_date, "end_date": end_date},
            }

        for ts_code_val, group in df.groupby(code_col):
            group_sorted = group.sort_values("end_date")
            holder_nums = []
            for _, row in group_sorted.iterrows():
                hn = self._safe_float(row, "holder_num")
                ed = str(row.get("end_date", ""))
                if hn is not None and ed:
                    holder_nums.append({"end_date": ed, "holder_num": int(hn)})

            if len(holder_nums) < 2:
                continue

            latest = holder_nums[-1]["holder_num"]
            earliest = holder_nums[0]["holder_num"]
            change_pct = ((latest - earliest) / earliest * 100) if earliest > 0 else 0

            # 趋势判断
            if change_pct < -10:
                trend = "concentrating"  # 筹码集中
                trend_label = "筹码集中"
            elif change_pct > 10:
                trend = "dispersing"  # 筹码分散
                trend_label = "筹码分散"
            else:
                trend = "stable"
                trend_label = "稳定"

            stock_analysis.append({
                "ts_code": ts_code_val,
                "latest_holder_num": latest,
                "earliest_holder_num": earliest,
                "change_pct": round(change_pct, 2),
                "trend": trend,
                "trend_label": trend_label,
                "history": holder_nums[-6:],  # 最近6期
            })

        # 按变动幅度排序（集中优先）
        stock_analysis.sort(key=lambda x: x["change_pct"])

        concentrating = sum(1 for s in stock_analysis if s["trend"] == "concentrating")
        dispersing = sum(1 for s in stock_analysis if s["trend"] == "dispersing")

        return {
            "stocks": stock_analysis[:200],
            "summary": {
                "total_stocks": len(stock_analysis),
                "concentrating_count": concentrating,
                "dispersing_count": dispersing,
            },
            "period": {"start_date": start_date, "end_date": end_date},
        }

    # ------------------------------------------------------------------
    # 3. 前十大股东分析
    # ------------------------------------------------------------------
    def analyze_top_holders(
        self,
        ts_code: str = None,
        end_date: str = None,
    ) -> Dict[str, Any]:
        """分析前十大股东结构。

        分析维度:
        - 股权集中度 (前十大股东持股比例合计)
        - 机构持仓占比
        - 国有资本占比
        返回: {stocks: [...], summary: {...}}
        """
        if not end_date:
            end_date = get_latest_trade_date(self.cache)

        try:
            df = self.client.get_top10_holders(
                ts_code=ts_code, end_date=end_date
            )
        except Exception as exc:
            logger.warning("top10_holders load failed: %s", exc)
            df = None

        if df is None or df.empty:
            return {
                "stocks": [],
                "summary": {
                    "total_stocks": 0,
                    "avg_concentration": 0,
                    "institutional_heavy_count": 0,
                },
                "end_date": end_date,
            }

        code_col = "ts_code" if "ts_code" in df.columns else None
        if not code_col:
            return {
                "stocks": [],
                "summary": {
                    "total_stocks": 0,
                    "avg_concentration": 0,
                    "institutional_heavy_count": 0,
                },
                "end_date": end_date,
            }

        stock_analysis = []
        for ts_code_val, group in df.groupby(code_col):
            total_ratio = 0
            holders = []
            institutional_ratio = 0
            state_ratio = 0

            for _, row in group.iterrows():
                holder_name = str(row.get("holder_name", ""))
                hold_ratio = self._safe_float(row, "hold_ratio") or 0
                hold_amount = self._safe_float(row, "hold_amount") or 0
                holder_type = str(row.get("holder_type", ""))

                total_ratio += hold_ratio

                # 判断是否机构
                is_institutional = any(
                    kw in holder_name
                    for kw in ("基金", "证券", "保险", "社保", "QFII", "券商", "资管", "信托")
                )
                is_state = any(
                    kw in holder_name
                    for kw in ("国有", "集团", "控股", "国资委", "财政", "中央", "省")
                )

                if is_institutional:
                    institutional_ratio += hold_ratio
                if is_state:
                    state_ratio += hold_ratio

                holders.append({
                    "holder_name": holder_name,
                    "hold_ratio_pct": round(hold_ratio, 4),
                    "hold_amount": round(hold_amount, 2),
                    "is_institutional": is_institutional,
                    "is_state": is_state,
                })

            holders.sort(key=lambda x: x["hold_ratio_pct"], reverse=True)

            # 集中度等级
            if total_ratio >= 70:
                concentration_level = "high"
            elif total_ratio >= 50:
                concentration_level = "medium"
            else:
                concentration_level = "low"

            stock_analysis.append({
                "ts_code": ts_code_val,
                "top10_ratio_pct": round(total_ratio, 2),
                "concentration_level": concentration_level,
                "institutional_ratio_pct": round(institutional_ratio, 2),
                "state_ratio_pct": round(state_ratio, 2),
                "holders": holders,
            })

        # 按集中度降序
        stock_analysis.sort(key=lambda x: x["top10_ratio_pct"], reverse=True)

        avg_concentration = (
            sum(s["top10_ratio_pct"] for s in stock_analysis) / len(stock_analysis)
            if stock_analysis else 0
        )
        institutional_heavy = sum(
            1 for s in stock_analysis if s["institutional_ratio_pct"] > 20
        )

        return {
            "stocks": stock_analysis[:200],
            "summary": {
                "total_stocks": len(stock_analysis),
                "avg_concentration": round(avg_concentration, 2),
                "institutional_heavy_count": institutional_heavy,
            },
            "end_date": end_date,
        }

    # ------------------------------------------------------------------
    # 综合分析
    # ------------------------------------------------------------------
    def get_comprehensive_analysis(
        self,
        ts_code: str = None,
        trade_date: str = None,
        lookback_days: int = 30,
    ) -> Dict[str, Any]:
        """综合股东情报分析——整合三个维度给出综合评分。"""
        if not trade_date:
            trade_date = get_latest_trade_date(self.cache)

        holder_trade = self.analyze_holder_trade(
            end_date=trade_date, lookback_days=lookback_days
        )
        holder_num = self.analyze_holder_num(
            ts_code=ts_code, end_date=trade_date, lookback_days=90
        )
        top_holders = self.analyze_top_holders(
            ts_code=ts_code, end_date=trade_date
        )

        # 综合评分
        score = 50  # 中性基础分

        # 增减持影响
        net_increase = holder_trade["summary"]["net_increase_amount"]
        if net_increase > 0:
            score += min(20, net_increase / 1000000)  # 增持加分
        elif net_increase < 0:
            score -= min(20, abs(net_increase) / 1000000)  # 减持减分

        # 筹码集中度影响
        concentrating = holder_num["summary"]["concentrating_count"]
        dispersing = holder_num["summary"]["dispersing_count"]
        if concentrating > dispersing:
            score += 10  # 集中趋势加分
        elif dispersing > concentrating:
            score -= 10  # 分散趋势减分

        # 机构持仓影响
        avg_inst = top_holders["summary"]["avg_concentration"]
        if avg_inst > 50:
            score += 10
        elif avg_inst < 30:
            score -= 5

        score = max(0, min(100, score))

        # 信号判定
        if score >= 70:
            signal = "bullish"
            signal_label = "看多"
        elif score <= 30:
            signal = "bearish"
            signal_label = "看空"
        else:
            signal = "neutral"
            signal_label = "中性"

        return {
            "trade_date": trade_date,
            "score": round(score, 1),
            "signal": signal,
            "signal_label": signal_label,
            "components": {
                "holder_trade": {
                    "net_increase": holder_trade["summary"]["net_increase_amount"],
                    "increase_count": holder_trade["summary"]["increase_count"],
                    "decrease_count": holder_trade["summary"]["decrease_count"],
                },
                "holder_num": {
                    "concentrating": holder_num["summary"]["concentrating_count"],
                    "dispersing": holder_num["summary"]["dispersing_count"],
                },
                "top_holders": {
                    "avg_concentration": top_holders["summary"]["avg_concentration"],
                    "institutional_heavy": top_holders["summary"]["institutional_heavy_count"],
                },
            },
            "details": {
                "holder_trade": holder_trade,
                "holder_num": holder_num,
                "top_holders": top_holders,
            },
        }

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_float(row, col):
        try:
            v = row.get(col) if hasattr(row, "get") else row[col]
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            return float(v)
        except (ValueError, TypeError, KeyError):
            return None
