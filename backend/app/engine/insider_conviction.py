"""内部人与机构智能引擎——整合4个数据源生成置信度信号。

整合数据源:
1. stk_holdertrade — 董监高增减持（内部人买入信号）
2. stk_holdernumber — 股东人数变动（筹码集中度）
3. top10_holders — 前十大股东（机构持仓变化）
4. forecast / express_vip — 业绩预告/快报（盈利预期信号）

四维信号加权合成置信度评分 (0-100):
- 内部人买入信号: 30% 权重
- 股东集中度信号: 30% 权重
- 业绩预告信号:   20% 权重
- 质押风险缓解:   20% 权重
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import pandas as pd

from ..clients.tushare import TuShareClient
from ..cache import CacheService
from ..utils import get_latest_trade_date

logger = logging.getLogger(__name__)

# 信号权重
WEIGHT_INSIDER_BUY = 0.30
WEIGHT_CONCENTRATION = 0.30
WEIGHT_FORECAST = 0.20
WEIGHT_PLEDGE_RELIEF = 0.20

# 信号阈值
INSIDER_BUY_MIN_AMOUNT = 1_000_000  # 买入金额 > 100万
FORECAST_GROWTH_THRESHOLD = 20      # 净利润增长 > 20%


class InsiderConvictionEngine:
    """内部人与机构智能引擎——四维信号合成置信度评分。"""

    def __init__(self, client: TuShareClient, cache: CacheService):
        self.client = client
        self.cache = cache

    # ==================================================================
    # Public API
    # ==================================================================

    def get_market_conviction(self, limit: int = 50) -> Dict[str, Any]:
        """全市场置信度扫描——找出置信度最高的股票。

        返回: {stocks: [...], summary: {...}}
        """
        trade_date = get_latest_trade_date(self.cache)
        dt = datetime.strptime(trade_date, "%Y%m%d")
        start_date = (dt - timedelta(days=60)).strftime("%Y%m%d")

        # 加载四维数据
        insider_df = self._load_holdertrade(start_date, trade_date)
        holder_num_df = self._load_holdernumber(start_date, trade_date)
        top10_df = self._load_top10_holders(trade_date)
        pledge_df = self._load_pledge_stat(trade_date)

        # 构建映射
        insider_map = self._build_insider_map(insider_df)
        holder_num_map = self._build_holder_num_map(holder_num_df)
        top10_map = self._build_top10_map(top10_df)
        pledge_map = self._build_pledge_map(pledge_df)

        # 合并所有有数据的股票
        all_codes = set()
        for m in [insider_map, holder_num_map, top10_map, pledge_map]:
            all_codes.update(m.keys())

        # 计算置信度
        stocks = []
        for ts_code in all_codes:
            result = self._compute_conviction(
                ts_code, insider_map.get(ts_code, {}),
                holder_num_map.get(ts_code, {}),
                top10_map.get(ts_code, {}),
                pledge_map.get(ts_code, {}),
            )
            if result:
                stocks.append(result)

        # 按置信度排序
        stocks.sort(key=lambda x: x["conviction_score"], reverse=True)

        # 统计
        strong_buy = sum(1 for s in stocks if s["conviction_level"] == "Strong Buy")
        buy = sum(1 for s in stocks if s["conviction_level"] == "Buy")
        hold = sum(1 for s in stocks if s["conviction_level"] == "Hold")
        sell = sum(1 for s in stocks if s["conviction_level"] == "Sell")

        return {
            "stocks": stocks[:limit],
            "summary": {
                "total_scanned": len(stocks),
                "strong_buy": strong_buy,
                "buy": buy,
                "hold": hold,
                "sell": sell,
                "trade_date": trade_date,
            },
        }

    def get_stock_conviction(self, ts_code: str) -> Dict[str, Any]:
        """单只股票的详细置信度分析。"""
        trade_date = get_latest_trade_date(self.cache)
        dt = datetime.strptime(trade_date, "%Y%m%d")
        start_date = (dt - timedelta(days=90)).strftime("%Y%m%d")

        insider_df = self._load_holdertrade(start_date, trade_date, ts_code)
        holder_num_df = self._load_holdernumber(start_date, trade_date, ts_code)
        top10_df = self._load_top10_holders(trade_date, ts_code)
        pledge_df = self._load_pledge_stat(trade_date)

        insider_map = self._build_insider_map(insider_df, ts_code)
        holder_num_map = self._build_holder_num_map(holder_num_df, ts_code)
        top10_map = self._build_top10_map(top10_df, ts_code)
        pledge_map = self._build_pledge_map(pledge_df, ts_code)

        result = self._compute_conviction(
            ts_code,
            insider_map.get(ts_code, {}),
            holder_num_map.get(ts_code, {}),
            top10_map.get(ts_code, {}),
            pledge_map.get(ts_code, {}),
        )
        if not result:
            return {"ts_code": ts_code, "conviction_score": 0, "conviction_level": "No Data", "signals": {}}

        # 补充详细信息
        result["insider_trades_detail"] = insider_map.get(ts_code, {}).get("trades", [])
        result["holder_num_history"] = holder_num_map.get(ts_code, {}).get("history", [])
        result["top10_holders"] = top10_map.get(ts_code, {}).get("holders", [])
        return result

    def get_insider_trades(self, ts_code: str, days: int = 30) -> Dict[str, Any]:
        """获取指定股票的内部人交易明细。"""
        trade_date = get_latest_trade_date(self.cache)
        dt = datetime.strptime(trade_date, "%Y%m%d")
        start_date = (dt - timedelta(days=days)).strftime("%Y%m%d")

        df = self._load_holdertrade(start_date, trade_date, ts_code)
        trades = []
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                in_de = str(row.get("in_de", ""))
                change_vol = self._safe_float(row, "change_vol") or 0
                avg_price = self._safe_float(row, "avg_price") or 0

                # 始终用 in_de 判断方向
                is_buy = in_de == "IN"
                action = "买入" if is_buy else "卖出"
                change_type_raw = str(row.get("change_type", ""))
                holder_type = str(row.get("holder_type", ""))

                trades.append({
                    "ts_code": str(row.get("ts_code", "")),
                    "ann_date": str(row.get("ann_date", "")),
                    "holder_name": str(row.get("holder_name", "")),
                    "holder_type": holder_type,
                    "change_type": action,
                    "change_shares": round(change_vol, 2),
                    "avg_price": round(avg_price, 2),
                    "change_ratio": self._safe_float(row, "change_ratio"),
                    "after_ratio": self._safe_float(row, "after_ratio"),
                    "amount_wan": round(change_vol * avg_price / 10000, 2) if avg_price else 0,
                })

        trades.sort(key=lambda x: x.get("ann_date", ""), reverse=True)
        return {
            "ts_code": ts_code,
            "trades": trades,
            "summary": {
                "total": len(trades),
                "buy_count": sum(1 for t in trades if t["change_type"] == "买入"),
                "sell_count": sum(1 for t in trades if t["change_type"] == "卖出"),
                "net_amount_wan": sum(
                    t["amount_wan"] if t["change_type"] == "买入" else -t["amount_wan"]
                    for t in trades
                ),
            },
            "period": {"start_date": start_date, "end_date": trade_date},
        }

    def get_shareholder_trend(self, ts_code: str) -> Dict[str, Any]:
        """获取股东人数变动趋势 + 前十大股东变动。"""
        trade_date = get_latest_trade_date(self.cache)
        dt = datetime.strptime(trade_date, "%Y%m%d")
        start_date = (dt - timedelta(days=180)).strftime("%Y%m%d")

        # 股东人数趋势
        hn_df = self._load_holdernumber(start_date, trade_date, ts_code)
        history = []
        if hn_df is not None and not hn_df.empty:
            hn_df_sorted = hn_df.sort_values("end_date")
            for _, row in hn_df_sorted.iterrows():
                hn = self._safe_float(row, "holder_num")
                ed = str(row.get("end_date", ""))
                if hn is not None and ed:
                    history.append({"end_date": ed, "holder_num": int(hn)})

        # 前十大股东
        top10_df = self._load_top10_holders(trade_date, ts_code)
        holders = []
        if top10_df is not None and not top10_df.empty:
            for _, row in top10_df.iterrows():
                holder_name = str(row.get("holder_name", ""))
                is_institutional = any(
                    kw in holder_name
                    for kw in ("基金", "证券", "保险", "社保", "QFII", "券商", "资管", "信托")
                )
                holders.append({
                    "holder_name": holder_name,
                    "hold_ratio": self._safe_float(row, "hold_ratio") or 0,
                    "hold_amount": self._safe_float(row, "hold_amount") or 0,
                    "holder_type": str(row.get("holder_type", "")),
                    "is_institutional": is_institutional,
                })
            holders.sort(key=lambda x: x["hold_ratio"], reverse=True)

        # 趋势计算
        trend = "stable"
        trend_label = "稳定"
        change_pct = 0
        if len(history) >= 2:
            earliest = history[0]["holder_num"]
            latest = history[-1]["holder_num"]
            if earliest > 0:
                change_pct = (latest - earliest) / earliest * 100
                if change_pct < -10:
                    trend = "concentrating"
                    trend_label = "筹码集中"
                elif change_pct > 10:
                    trend = "dispersing"
                    trend_label = "筹码分散"

        return {
            "ts_code": ts_code,
            "history": history,
            "top10_holders": holders,
            "trend": trend,
            "trend_label": trend_label,
            "change_pct": round(change_pct, 2),
        }

    # ==================================================================
    # Signal computation
    # ==================================================================

    def _compute_conviction(
        self,
        ts_code: str,
        insider_data: Dict,
        holder_num_data: Dict,
        top10_data: Dict,
        pledge_data: Dict,
    ) -> Optional[Dict[str, Any]]:
        """计算四维置信度评分。"""
        signals = {}
        total_score = 0.0

        # --- Dimension 1: 内部人买入 (30%) ---
        insider_buy_count = insider_data.get("buy_count", 0)
        insider_sell_count = insider_data.get("sell_count", 0)
        net_buy_amount = insider_data.get("net_buy_amount", 0)
        buy_consistency = insider_data.get("buy_consistency", 0)

        insider_score = 0
        if insider_buy_count > 0 and net_buy_amount > INSIDER_BUY_MIN_AMOUNT:
            # 净买入为正且金额 > 100万
            insider_score = min(100, 50 + (net_buy_amount / 1000000) * 10 + insider_buy_count * 5)
        elif insider_buy_count > 0:
            insider_score = min(60, 30 + insider_buy_count * 5)

        if insider_sell_count > insider_buy_count * 2:
            insider_score = max(0, insider_score - 30)  # 大量卖出扣分

        signals["insider_buying"] = {
            "score": round(insider_score, 2),
            "buy_count": insider_buy_count,
            "sell_count": insider_sell_count,
            "net_buy_amount_wan": round(net_buy_amount / 10000, 2),
            "buy_consistency": round(buy_consistency, 2),
        }
        total_score += insider_score * WEIGHT_INSIDER_BUY

        # --- Dimension 2: 股东集中度 (30%) ---
        holder_count_change = holder_num_data.get("change_pct", 0)
        top10_institutional_ratio = top10_data.get("institutional_ratio", 0)

        concentration_score = 50  # 基础分
        if holder_count_change < -20:
            concentration_score += 30  # 筹码大幅集中
        elif holder_count_change < -10:
            concentration_score += 20
        elif holder_count_change < 0:
            concentration_score += 10
        elif holder_count_change > 20:
            concentration_score -= 20  # 筹码大幅分散
        elif holder_count_change > 10:
            concentration_score -= 10

        if top10_institutional_ratio > 30:
            concentration_score += 15
        elif top10_institutional_ratio > 15:
            concentration_score += 8

        concentration_score = max(0, min(100, concentration_score))
        signals["shareholder_concentration"] = {
            "score": round(concentration_score, 2),
            "holder_count_change_pct": round(holder_count_change, 2),
            "top10_institutional_ratio": round(top10_institutional_ratio, 2),
        }
        total_score += concentration_score * WEIGHT_CONCENTRATION

        # --- Dimension 3: 业绩预告信号 (20%) ---
        forecast_growth = top10_data.get("forecast_growth", 0)
        express_growth = top10_data.get("express_growth", 0)

        forecast_score = 40  # 默认中性
        effective_growth = max(forecast_growth, express_growth)
        if effective_growth > 50:
            forecast_score = 90
        elif effective_growth > FORECAST_GROWTH_THRESHOLD:
            forecast_score = 70
        elif effective_growth > 0:
            forecast_score = 55
        elif effective_growth > -20:
            forecast_score = 35
        else:
            forecast_score = 15

        signals["forecast_surprise"] = {
            "score": round(forecast_score, 2),
            "forecast_growth_pct": round(forecast_growth, 2),
            "express_growth_pct": round(express_growth, 2),
        }
        total_score += forecast_score * WEIGHT_FORECAST

        # --- Dimension 4: 质押缓解 (20%) ---
        pledge_ratio = pledge_data.get("pledge_ratio")
        pledge_score = 50  # 默认中性

        if pledge_ratio is not None:
            if pledge_ratio < 5:
                pledge_score = 90
            elif pledge_ratio < 10:
                pledge_score = 75
            elif pledge_ratio < 20:
                pledge_score = 60
            elif pledge_ratio < 30:
                pledge_score = 45
            elif pledge_ratio < 50:
                pledge_score = 30
            else:
                pledge_score = 10
        else:
            pledge_score = 70  # 无质押视为安全

        signals["pledge_relief"] = {
            "score": round(pledge_score, 2),
            "pledge_ratio": pledge_ratio,
        }
        total_score += pledge_score * WEIGHT_PLEDGE_RELIEF

        # --- 综合 ---
        total_score = round(total_score, 2)
        total_score = max(0, min(100, total_score))

        if total_score >= 80:
            level = "Strong Buy"
            level_cn = "强烈看多"
        elif total_score >= 60:
            level = "Buy"
            level_cn = "看多"
        elif total_score >= 40:
            level = "Hold"
            level_cn = "持有"
        else:
            level = "Sell"
            level_cn = "看空"

        return {
            "ts_code": ts_code,
            "conviction_score": total_score,
            "conviction_level": level,
            "conviction_level_cn": level_cn,
            "signals": signals,
            "insider_buying_count": insider_buy_count,
            "insider_buying_consistency": buy_consistency,
        }

    # ==================================================================
    # Data loaders
    # ==================================================================

    def _load_holdertrade(self, start_date: str, end_date: str, ts_code: str = None) -> pd.DataFrame:
        """加载股东增减持数据。"""
        try:
            kwargs = {"start_date": start_date, "end_date": end_date}
            if ts_code:
                kwargs["ts_code"] = ts_code
            df = self.client._call_with_retry(self.client.pro.stk_holdertrade, **kwargs)
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.warning("stk_holdertrade load failed: %s", exc)
            return pd.DataFrame()

    def _load_holdernumber(self, start_date: str, end_date: str, ts_code: str = None) -> pd.DataFrame:
        """加载股东人数数据。"""
        try:
            kwargs = {"start_date": start_date, "end_date": end_date}
            if ts_code:
                kwargs["ts_code"] = ts_code
            df = self.client._call_with_retry(self.client.pro.stk_holdernumber, **kwargs)
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.warning("stk_holdernumber load failed: %s", exc)
            return pd.DataFrame()

    def _load_top10_holders(self, end_date: str, ts_code: str = None) -> pd.DataFrame:
        """加载前十大股东数据。"""
        try:
            kwargs = {"end_date": end_date}
            if ts_code:
                kwargs["ts_code"] = ts_code
            df = self.client._call_with_retry(self.client.pro.top10_holders, **kwargs)
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.warning("top10_holders load failed: %s", exc)
            return pd.DataFrame()

    def _load_pledge_stat(self, end_date: str) -> pd.DataFrame:
        """加载股权质押数据。"""
        try:
            df = self.client._call_with_retry(self.client.pro.pledge_stat, end_date=end_date)
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.warning("pledge_stat load failed: %s", exc)
            return pd.DataFrame()

    # ==================================================================
    # Map builders
    # ==================================================================

    def _build_insider_map(self, df: pd.DataFrame, filter_code: str = None) -> Dict[str, Dict]:
        """构建内部人交易映射: ts_code -> {buy_count, sell_count, net_buy_amount, ...}"""
        result = {}
        if df is None or df.empty:
            return result

        code_col = "ts_code" if "ts_code" in df.columns else None
        if not code_col:
            return result

        for _, row in df.iterrows():
            tc = str(row.get(code_col, ""))
            if filter_code and tc != filter_code:
                continue
            if not tc:
                continue

            in_de = str(row.get("in_de", ""))
            change_vol = self._safe_float(row, "change_vol") or 0
            avg_price = self._safe_float(row, "avg_price") or 0
            amount = change_vol * avg_price  # 金额

            is_buy = in_de == "IN"

            if tc not in result:
                result[tc] = {
                    "buy_count": 0,
                    "sell_count": 0,
                    "net_buy_amount": 0,
                    "trades": [],
                    "buy_dates": [],
                }

            entry = result[tc]
            if is_buy:
                entry["buy_count"] += 1
                entry["net_buy_amount"] += amount
                entry["buy_dates"].append(str(row.get("ann_date", "")))
            else:
                entry["sell_count"] += 1
                entry["net_buy_amount"] -= amount

            entry["trades"].append({
                "ann_date": str(row.get("ann_date", "")),
                "holder_name": str(row.get("holder_name", "")),
                "in_de": "IN" if is_buy else "DE",
                "change_vol": change_vol,
                "avg_price": avg_price,
                "amount_wan": round(amount / 10000, 2),
            })

        # 计算买入一致性（多次买入的一致性加分）
        for tc, entry in result.items():
            buy_count = entry["buy_count"]
            if buy_count >= 3:
                entry["buy_consistency"] = min(100, buy_count * 20)
            elif buy_count >= 2:
                entry["buy_consistency"] = 60
            elif buy_count >= 1:
                entry["buy_consistency"] = 30
            else:
                entry["buy_consistency"] = 0

        return result

    def _build_holder_num_map(self, df: pd.DataFrame, filter_code: str = None) -> Dict[str, Dict]:
        """构建股东人数变动映射。"""
        result = {}
        if df is None or df.empty:
            return result

        code_col = "ts_code" if "ts_code" in df.columns else None
        if not code_col:
            return result

        for ts_code_val, group in df.groupby(code_col):
            if filter_code and ts_code_val != filter_code:
                continue
            group_sorted = group.sort_values("end_date")
            history = []
            for _, row in group_sorted.iterrows():
                hn = self._safe_float(row, "holder_num")
                ed = str(row.get("end_date", ""))
                if hn is not None and ed:
                    history.append({"end_date": ed, "holder_num": int(hn)})

            if len(history) < 2:
                result[ts_code_val] = {"change_pct": 0, "history": history}
                continue

            earliest = history[0]["holder_num"]
            latest = history[-1]["holder_num"]
            change_pct = ((latest - earliest) / earliest * 100) if earliest > 0 else 0

            result[ts_code_val] = {
                "change_pct": change_pct,
                "history": history[-12:],
                "latest": latest,
                "earliest": earliest,
            }

        return result

    def _build_top10_map(self, df: pd.DataFrame, filter_code: str = None) -> Dict[str, Dict]:
        """构建前十大股东映射。"""
        result = {}
        if df is None or df.empty:
            return result

        code_col = "ts_code" if "ts_code" in df.columns else None
        if not code_col:
            return result

        for ts_code_val, group in df.groupby(code_col):
            if filter_code and ts_code_val != filter_code:
                continue

            total_ratio = 0
            institutional_ratio = 0
            holders = []

            for _, row in group.iterrows():
                holder_name = str(row.get("holder_name", ""))
                hold_ratio = self._safe_float(row, "hold_ratio") or 0
                hold_amount = self._safe_float(row, "hold_amount") or 0

                total_ratio += hold_ratio
                is_institutional = any(
                    kw in holder_name
                    for kw in ("基金", "证券", "保险", "社保", "QFII", "券商", "资管", "信托")
                )
                if is_institutional:
                    institutional_ratio += hold_ratio

                holders.append({
                    "holder_name": holder_name,
                    "hold_ratio": round(hold_ratio, 4),
                    "hold_amount": round(hold_amount, 2),
                    "is_institutional": is_institutional,
                })

            result[ts_code_val] = {
                "total_ratio": round(total_ratio, 2),
                "institutional_ratio": round(institutional_ratio, 2),
                "holders": holders,
            }

        return result

    def _build_pledge_map(self, df: pd.DataFrame) -> Dict[str, Dict]:
        """构建质押数据映射。"""
        result = {}
        if df is None or df.empty:
            return result

        code_col = "ts_code" if "ts_code" in df.columns else None
        ratio_col = "pledge_ratio" if "pledge_ratio" in df.columns else None
        if not code_col or not ratio_col:
            return result

        for _, row in df.iterrows():
            tc = str(row.get(code_col, ""))
            ratio = self._safe_float(row, ratio_col)
            if tc and ratio is not None:
                result[tc] = {
                    "pledge_ratio": ratio,
                    "pledge_count": self._safe_float(row, "pledge_count"),
                    "pledge_amount": self._safe_float(row, "pledge_amount"),
                }

        return result

    # ==================================================================
    # Helpers
    # ==================================================================

    @staticmethod
    def _safe_float(row, col):
        try:
            v = row.get(col) if hasattr(row, "get") else row[col]
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            return float(v)
        except (ValueError, TypeError, KeyError):
            return None
