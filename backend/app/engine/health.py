"""股票综合健康度评分引擎。

为任意一只 A 股生成 0-100 的综合健康度评分，聚合以下 5 个维度：
1. 策略信号 (35%) — 评估 22 个策略的关键条件命中情况
2. 技术指标 (20%) — MACD / KDJ / RSI 金叉与超买超卖
3. 资金流向 (25%) — 近 5 日主力净流入趋势、大单占比、流入加速
4. 基本面   (10%) — PE(TTM) / PB / 股息率 / 市值
5. 筹码与风险 (10%) — 筹码穿透率 / 股权质押比例
"""

import logging
import math
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple

from .data_loader import StrategyDataLoader
from ..clients.tushare import TuShareClient
from ..cache import CacheService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 维度权重上限
# ---------------------------------------------------------------------------
DIM_LIMITS: Dict[str, float] = {
    "strategy": 35.0,
    "technical": 20.0,
    "money_flow": 25.0,
    "fundamental": 10.0,
    "chip_risk": 10.0,
}

# ---------------------------------------------------------------------------
# 策略分类与分值 — value:+5, momentum:+4, flow:+4, event:+3
# ---------------------------------------------------------------------------
STRATEGY_CATEGORY_POINTS = {
    "value": 5.0,
    "momentum": 4.0,
    "flow": 4.0,
    "event": 3.0,
}

# 策略名称 → (分类, 条件检查函数名)
STRATEGY_CHECK_MAP: Dict[str, Tuple[str, str]] = {
    # momentum (7)
    "macd_golden_cross":       ("momentum", "_chk_macd_golden"),
    "kdj_oversold_rebound":    ("momentum", "_chk_kdj_oversold"),
    "oversold_bounce":         ("momentum", "_chk_rsi_oversold"),
    "ma_alignment":            ("momentum", "_chk_ma_alignment"),
    "volume_breakthrough":     ("momentum", "_chk_vol_breakout"),
    "trend_volume_resonance":  ("momentum", "_chk_trend_vol"),
    "volume_anomaly":          ("momentum", "_chk_vol_anomaly"),
    # value (5)
    "high_dividend":           ("value", "_chk_high_dividend"),
    "low_valuation_gold":      ("value", "_chk_low_valuation"),
    "broken_net_gold":         ("value", "_chk_broken_net"),
    "value_fund_resonance":    ("value", "_chk_value_fund"),
    "chip_pledge_strategy":    ("value", "_chk_chip_pledge_safe"),
    # flow (5)
    "main_fund_inflow":        ("flow", "_chk_main_fund_inflow"),
    "margin_growth":           ("flow", "_chk_margin_growth"),
    "margin_fund_convergence": ("flow", "_chk_margin_fund_conv"),
    "smart_money_tracker":     ("flow", "_chk_smart_money"),
    "flow_divergence":         ("flow", "_chk_flow_divergence"),
    # event (3)
    "block_trade_premium":     ("event", "_chk_block_premium"),
    "consecutive_limit_up":    ("event", "_chk_consec_limit_up"),
    "limit_up_reseal":         ("event", "_chk_limit_reseal"),
}


class StockHealthEngine:
    """股票综合健康度评分引擎 — 聚合 5 个维度，输出 0-100 分。"""

    def __init__(self, loader: StrategyDataLoader):
        self.loader = loader

    # ==================================================================
    # public
    # ==================================================================

    def score(self, ts_code: str, trade_date: str) -> Dict[str, Any]:
        """为单只股票生成健康度评分。"""
        data = self.loader.load(trade_date, [
            "daily_basic", "stk_factor", "moneyflow_multi",
            "cyq_perf", "pledge_stat", "daily_multi",
        ])

        # 股票名称
        stock_name = ts_code
        try:
            basic_rows = self.loader.cache.get_stock_basic_from_db()
            for r in (basic_rows or []):
                if r.get("ts_code") == ts_code:
                    stock_name = r.get("name", ts_code)
                    break
        except Exception:
            pass

        scores: Dict[str, Dict[str, Any]] = {}

        for dim, limit in DIM_LIMITS.items():
            try:
                fn = getattr(self, f"_score_{dim}")
                scores[dim] = fn(ts_code, data, limit)
            except Exception as exc:
                logger.error("health score dimension '%s' failed for %s: %s", dim, ts_code, exc)
                scores[dim] = {"score": 0.0, "max": limit, "details": {}}

        total = max(0.0, min(100.0, sum(d["score"] for d in scores.values())))

        return {
            "ts_code": ts_code,
            "stock_name": stock_name,
            "trade_date": trade_date,
            "health_score": round(total, 2),
            "dimensions": scores,
        }

    def batch_score(
        self,
        trade_date: str,
        ts_codes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """批量评分 — 数据只加载一次，逐股计算。"""
        data = self.loader.load(trade_date, [
            "daily_basic", "stk_factor", "moneyflow_multi",
            "cyq_perf", "pledge_stat", "daily_multi",
        ])

        # 股票名称映射
        name_map: Dict[str, str] = {}
        try:
            basic_rows = self.loader.cache.get_stock_basic_from_db()
            for r in (basic_rows or []):
                name_map[r["ts_code"]] = r.get("name", r["ts_code"])
        except Exception:
            pass

        # 确定目标股票列表
        basic_df = data.get("daily_basic", pd.DataFrame())
        if ts_codes:
            target_codes = ts_codes
        elif not basic_df.empty:
            target_codes = basic_df["ts_code"].unique().tolist()
        else:
            return {"trade_date": trade_date, "total": 0, "results": []}

        results: List[Dict[str, Any]] = []
        for tc in target_codes:
            scores: Dict[str, Dict[str, Any]] = {}
            for dim, limit in DIM_LIMITS.items():
                try:
                    fn = getattr(self, f"_score_{dim}")
                    scores[dim] = fn(tc, data, limit)
                except Exception as exc:
                    logger.error("batch health '%s' failed for %s: %s", dim, tc, exc)
                    scores[dim] = {"score": 0.0, "max": limit, "details": {}}

            total = max(0.0, min(100.0, sum(d["score"] for d in scores.values())))
            results.append({
                "ts_code": tc,
                "stock_name": name_map.get(tc, tc),
                "health_score": round(total, 2),
                "dimensions": scores,
            })

        results.sort(key=lambda x: x["health_score"], reverse=True)

        return {
            "trade_date": trade_date,
            "total": len(results),
            "results": results,
        }

    # ==================================================================
    # 维度 1 — 策略信号 (35%)
    # ==================================================================

    def _score_strategy(
        self, ts_code: str, data: Dict[str, pd.DataFrame], limit: float,
    ) -> Dict[str, Any]:
        """评估 22 个策略的关键条件命中情况。"""
        # 提取该股票的基本面数据（供策略判断复用）
        basic_df = data.get("daily_basic", pd.DataFrame())
        stock_basic: Dict[str, Any] = {}
        if not basic_df.empty and ts_code in basic_df.get("ts_code", pd.Series()).values:
            row = basic_df[basic_df["ts_code"] == ts_code].iloc[0]
            stock_basic = {
                "pe_ttm": self._safe_val(row, "pe_ttm"),
                "pb": self._safe_val(row, "pb"),
                "dv_ttm": self._safe_val(row, "dv_ttm"),
                "total_mv": self._safe_val(row, "total_mv"),
            }

        matched: List[Dict[str, Any]] = []
        total = 0.0

        for strat_name, (category, check_fn_name) in STRATEGY_CHECK_MAP.items():
            points = STRATEGY_CATEGORY_POINTS.get(category, 3.0)
            try:
                hit = getattr(self, check_fn_name)(ts_code, data, stock_basic)
                if hit:
                    matched.append({
                        "strategy": strat_name,
                        "category": category,
                        "points": points,
                    })
                    total += points
            except Exception as exc:
                logger.debug("strategy check '%s' failed for %s: %s", strat_name, ts_code, exc)

        total = min(total, limit)

        return {
            "score": round(total, 2),
            "max": limit,
            "details": {
                "matched_count": len(matched),
                "matched_strategies": matched,
            },
        }

    # ------------------------------------------------------------------
    # 策略条件检查 — 每个函数返回 True 表示命中
    # ------------------------------------------------------------------

    def _chk_macd_golden(self, ts_code: str, data: Dict, _sb: Dict) -> bool:
        """MACD金叉: DIF > DEA 且 MACD 柱状线 > 0。"""
        df = data.get("stk_factor", pd.DataFrame())
        if df.empty:
            return False
        row = self._get_stock_row(df, ts_code)
        if row is None:
            return False
        dif = self._safe_val(row, "macd_dif")
        dea = self._safe_val(row, "macd_dea")
        macd = self._safe_val(row, "macd")
        return bool(
            dif is not None and dea is not None and macd is not None
            and dif > dea and macd > 0
        )

    def _chk_kdj_oversold(self, ts_code: str, data: Dict, _sb: Dict) -> bool:
        """KDJ超卖反弹: K < 30 且 K > D。"""
        df = data.get("stk_factor", pd.DataFrame())
        if df.empty:
            return False
        row = self._get_stock_row(df, ts_code)
        if row is None:
            return False
        k = self._safe_val(row, "kdj_k")
        d = self._safe_val(row, "kdj_d")
        return bool(k is not None and d is not None and k < 30 and k > d)

    def _chk_rsi_oversold(self, ts_code: str, data: Dict, _sb: Dict) -> bool:
        """RSI超卖反弹: RSI6 < 30。"""
        df = data.get("stk_factor", pd.DataFrame())
        if df.empty:
            return False
        row = self._get_stock_row(df, ts_code)
        if row is None:
            return False
        rsi = self._safe_val(row, "rsi_6")
        return bool(rsi is not None and rsi < 30)

    def _chk_ma_alignment(self, ts_code: str, data: Dict, _sb: Dict) -> bool:
        """均线多头排列: MA5 > MA10 > MA20。"""
        df = data.get("daily_multi", pd.DataFrame())
        if df.empty:
            return False
        stock_df = df[df["ts_code"] == ts_code].sort_values("trade_date")
        if len(stock_df) < 20:
            return False
        closes = stock_df["close"].astype(float)
        ma5 = closes.tail(5).mean()
        ma10 = closes.tail(10).mean()
        ma20 = closes.tail(20).mean()
        return bool(ma5 > ma10 > ma20)

    def _chk_vol_breakout(self, ts_code: str, data: Dict, _sb: Dict) -> bool:
        """放量突破: 成交量 > 5日均量 * 1.5 且涨幅 > 2%。"""
        df = data.get("daily_multi", pd.DataFrame())
        if df.empty:
            return False
        stock_df = df[df["ts_code"] == ts_code].sort_values("trade_date")
        if len(stock_df) < 6:
            return False
        last = stock_df.iloc[-1]
        vol = self._safe_val(last, "vol")
        pct = self._safe_val(last, "pct_chg") or self._safe_val(last, "pct_change")
        if vol is None or pct is None:
            return False
        avg_vol = stock_df["vol"].astype(float).tail(5).mean()
        return bool(avg_vol > 0 and vol > avg_vol * 1.5 and pct > 2)

    def _chk_trend_vol(self, ts_code: str, data: Dict, _sb: Dict) -> bool:
        """趋势量价共振: 近5日连续上涨且放量。"""
        df = data.get("daily_multi", pd.DataFrame())
        if df.empty:
            return False
        stock_df = df[df["ts_code"] == ts_code].sort_values("trade_date")
        if len(stock_df) < 5:
            return False
        recent = stock_df.tail(5)
        all_up = all(
            (self._safe_val(r, "pct_chg") or self._safe_val(r, "pct_change") or 0) > 0
            for _, r in recent.iterrows()
        )
        if not all_up:
            return False
        vols = recent["vol"].astype(float).values
        return bool(all(vols[i] >= vols[i - 1] for i in range(1, len(vols))))

    def _chk_vol_anomaly(self, ts_code: str, data: Dict, _sb: Dict) -> bool:
        """量能异常: 当日成交量 > 10日均量 * 2。"""
        df = data.get("daily_multi", pd.DataFrame())
        if df.empty:
            return False
        stock_df = df[df["ts_code"] == ts_code].sort_values("trade_date")
        if len(stock_df) < 10:
            return False
        last_vol = self._safe_val(stock_df.iloc[-1], "vol")
        if last_vol is None:
            return False
        avg_vol = stock_df["vol"].astype(float).tail(10).mean()
        return bool(avg_vol > 0 and last_vol > avg_vol * 2)

    def _chk_high_dividend(self, _ts_code: str, _data: Dict, sb: Dict) -> bool:
        """高股息: 股息率 > 3% 且 PE(TTM) < 20。"""
        dv = sb.get("dv_ttm")
        pe = sb.get("pe_ttm")
        return bool(
            dv is not None and pe is not None
            and dv > 3 and 0 < pe < 20
        )

    def _chk_low_valuation(self, _ts_code: str, _data: Dict, sb: Dict) -> bool:
        """低估值黄金: PE(TTM) < 15 且 PB < 1.5。"""
        pe = sb.get("pe_ttm")
        pb = sb.get("pb")
        return bool(
            pe is not None and pb is not None
            and 0 < pe < 15 and 0 < pb < 1.5
        )

    def _chk_broken_net(self, _ts_code: str, _data: Dict, sb: Dict) -> bool:
        """破净黄金: PB < 1。"""
        pb = sb.get("pb")
        return bool(pb is not None and 0 < pb < 1)

    def _chk_value_fund(self, _ts_code: str, _data: Dict, sb: Dict) -> bool:
        """价值资金共振: PE(TTM) < 20 且 股息率 > 2%。"""
        pe = sb.get("pe_ttm")
        dv = sb.get("dv_ttm")
        return bool(
            pe is not None and dv is not None
            and 0 < pe < 20 and dv > 2
        )

    def _chk_chip_pledge_safe(self, _ts_code: str, data: Dict, _sb: Dict) -> bool:
        """筹码质押安全: 质押比例 < 20% 且 PB < 2。"""
        pledge_df = data.get("pledge_stat", pd.DataFrame())
        pb = _sb.get("pb")
        if pledge_df.empty or pb is None:
            return False
        code_col = self._find_col(pledge_df, ["ts_code", "tc"])
        ratio_col = self._find_col(pledge_df, ["pledge_ratio", "pr"])
        if not code_col or not ratio_col:
            return False
        match = pledge_df[pledge_df[code_col] == _ts_code]
        if match.empty:
            return False
        ratio = self._safe_val(match.iloc[0], ratio_col)
        return bool(ratio is not None and ratio < 20 and 0 < pb < 2)

    def _chk_main_fund_inflow(self, ts_code: str, data: Dict, _sb: Dict) -> bool:
        """主力资金持续流入: 近3日主力净流入为正。"""
        df = data.get("moneyflow_multi", pd.DataFrame())
        if df.empty:
            return False
        stock_df = df[df["ts_code"] == ts_code].sort_values("trade_date").tail(3)
        if len(stock_df) < 3:
            return False
        return all(
            (self._safe_val(r, "net_mf_amount") or 0) > 0
            for _, r in stock_df.iterrows()
        )

    def _chk_margin_growth(self, ts_code: str, data: Dict, _sb: Dict) -> bool:
        """融资增长: 需要 margin_detail 数据（当前未加载，返回 False）。"""
        return False

    def _chk_margin_fund_conv(self, ts_code: str, data: Dict, _sb: Dict) -> bool:
        """融资资金收敛: 需要 margin_detail 数据（当前未加载，返回 False）。"""
        return False

    def _chk_smart_money(self, ts_code: str, data: Dict, _sb: Dict) -> bool:
        """聪明资金追踪: 超大单净流入 > 0 且 大单净流入 > 0。"""
        df = data.get("moneyflow_multi", pd.DataFrame())
        if df.empty:
            return False
        stock_df = df[df["ts_code"] == ts_code].sort_values("trade_date")
        if stock_df.empty:
            return False
        last = stock_df.iloc[-1]
        elg_net = (self._safe_val(last, "buy_elg_amount") or 0) - (
            self._safe_val(last, "sell_elg_amount") or 0
        )
        lg_net = (self._safe_val(last, "buy_lg_amount") or 0) - (
            self._safe_val(last, "sell_lg_amount") or 0
        )
        return bool(elg_net > 0 and lg_net > 0)

    def _chk_flow_divergence(self, ts_code: str, data: Dict, _sb: Dict) -> bool:
        """资金流背离: 价格下跌但主力资金净流入为正。"""
        daily_df = data.get("daily_multi", pd.DataFrame())
        mf_df = data.get("moneyflow_multi", pd.DataFrame())
        if daily_df.empty or mf_df.empty:
            return False
        price_rows = daily_df[daily_df["ts_code"] == ts_code].sort_values("trade_date").tail(3)
        mf_rows = mf_df[mf_df["ts_code"] == ts_code].sort_values("trade_date").tail(3)
        if len(price_rows) < 3 or len(mf_rows) < 3:
            return False
        price_chg = (
            self._safe_val(price_rows.iloc[-1], "close", 0)
            - self._safe_val(price_rows.iloc[0], "close", 0)
        )
        fund_net = sum(
            (self._safe_val(r, "net_mf_amount") or 0) for _, r in mf_rows.iterrows()
        )
        return bool(price_chg < 0 and fund_net > 0)

    def _chk_block_premium(self, ts_code: str, data: Dict, _sb: Dict) -> bool:
        """大宗交易溢价: 需要 block_trade 数据（当前未加载，返回 False）。"""
        return False

    def _chk_consec_limit_up(self, ts_code: str, data: Dict, _sb: Dict) -> bool:
        """连续涨停: 近3日连续涨停（涨幅 > 9.5%）。"""
        df = data.get("daily_multi", pd.DataFrame())
        if df.empty:
            return False
        stock_df = df[df["ts_code"] == ts_code].sort_values("trade_date").tail(3)
        if len(stock_df) < 3:
            return False
        return all(
            (self._safe_val(r, "pct_chg") or self._safe_val(r, "pct_change") or 0) > 9.5
            for _, r in stock_df.iterrows()
        )

    def _chk_limit_reseal(self, ts_code: str, data: Dict, _sb: Dict) -> bool:
        """涨停封板: 当日涨停（涨幅 > 9.5%）且收盘价 == 最高价。"""
        df = data.get("daily_multi", pd.DataFrame())
        if df.empty:
            return False
        stock_df = df[df["ts_code"] == ts_code].sort_values("trade_date")
        if stock_df.empty:
            return False
        last = stock_df.iloc[-1]
        pct = self._safe_val(last, "pct_chg") or self._safe_val(last, "pct_change") or 0
        close = self._safe_val(last, "close") or 0
        high = self._safe_val(last, "high") or 0
        return bool(pct > 9.5 and close > 0 and high > 0 and abs(close - high) < 0.01)

    # ==================================================================
    # 维度 2 — 技术指标 (20%)
    # ==================================================================

    def _score_technical(
        self, ts_code: str, data: Dict[str, pd.DataFrame], limit: float,
    ) -> Dict[str, Any]:
        """MACD / KDJ / RSI 技术指标评分。"""
        df = data.get("stk_factor", pd.DataFrame())
        if df.empty:
            return {"score": 0.0, "max": limit, "details": {}}

        row = self._get_stock_row(df, ts_code)
        if row is None:
            return {"score": 0.0, "max": limit, "details": {}}

        score = 0.0
        details: Dict[str, Any] = {}

        # --- MACD ---
        macd_dif = self._safe_val(row, "macd_dif")
        macd_dea = self._safe_val(row, "macd_dea")
        macd_val = self._safe_val(row, "macd")
        if macd_dif is not None and macd_dea is not None and macd_val is not None:
            if macd_dif > macd_dea and macd_val > 0:
                score += 8.0
                details["macd"] = "golden_cross"
            elif macd_dif < macd_dea and macd_val < 0:
                score -= 5.0
                details["macd"] = "death_cross"

        # --- KDJ ---
        kdj_k = self._safe_val(row, "kdj_k")
        kdj_d = self._safe_val(row, "kdj_d")
        if kdj_k is not None and kdj_d is not None:
            if kdj_k < 30 and kdj_k > kdj_d:
                score += 6.0
                details["kdj"] = "golden_cross_oversold"
            elif kdj_k > 80:
                score -= 4.0
                details["kdj"] = "overbought"

        # --- RSI ---
        rsi_6 = self._safe_val(row, "rsi_6")
        if rsi_6 is not None:
            if rsi_6 < 30:
                score += 6.0
                details["rsi"] = "oversold_bounce"
            elif rsi_6 > 70:
                score -= 4.0
                details["rsi"] = "overbought"

        score = max(0.0, min(score, limit))

        return {"score": round(score, 2), "max": limit, "details": details}

    # ==================================================================
    # 维度 3 — 资金流向 (25%)
    # ==================================================================

    def _score_money_flow(
        self, ts_code: str, data: Dict[str, pd.DataFrame], limit: float,
    ) -> Dict[str, Any]:
        """近 5 日主力净流入趋势、大单占比、流入加速。"""
        df = data.get("moneyflow_multi", pd.DataFrame())
        if df.empty:
            return {"score": 0.0, "max": limit, "details": {}}

        stock_df = df[df["ts_code"] == ts_code].sort_values("trade_date")
        if stock_df.empty:
            return {"score": 0.0, "max": limit, "details": {}}

        recent = stock_df.tail(5)
        score = 0.0
        details: Dict[str, Any] = {}

        # 1. 连续净流入 / 净流出
        # net == 0 时跳过（continue），不计入也不中断连续天数
        consecutive_in = 0
        consecutive_out = 0
        for _, r in recent.iterrows():
            net = self._safe_val(r, "net_mf_amount") or 0
            if net > 0:
                consecutive_in += 1
            elif net < 0:
                consecutive_out += 1
            else:
                continue

        if consecutive_in >= 5:
            score += 15.0
        elif consecutive_in >= 3:
            score += 10.0
        if consecutive_out >= 3:
            score -= 10.0

        details["consecutive_inflow_days"] = consecutive_in
        details["consecutive_outflow_days"] = consecutive_out

        # 2. 超大 + 大单占比 > 50%
        total_amount = 0.0
        main_amount = 0.0
        for _, r in recent.iterrows():
            buy_lg = self._safe_val(r, "buy_lg_amount") or 0
            sell_lg = self._safe_val(r, "sell_lg_amount") or 0
            buy_elg = self._safe_val(r, "buy_elg_amount") or 0
            sell_elg = self._safe_val(r, "sell_elg_amount") or 0
            buy_sm = self._safe_val(r, "buy_sm_amount") or 0
            sell_sm = self._safe_val(r, "sell_sm_amount") or 0
            buy_md = self._safe_val(r, "buy_md_amount") or 0
            sell_md = self._safe_val(r, "sell_md_amount") or 0

            day_total = buy_lg + sell_lg + buy_elg + sell_elg + buy_sm + sell_sm + buy_md + sell_md
            day_main = buy_lg + sell_lg + buy_elg + sell_elg
            total_amount += day_total
            main_amount += day_main

        main_ratio = main_amount / total_amount if total_amount > 0 else 0
        if main_ratio > 0.5:
            score += 5.0
        details["main_order_ratio"] = round(main_ratio, 4)

        # 3. 资金流入加速: 近2日均值 > 前3日均值 * 1.2
        if len(recent) >= 5:
            days = recent["net_mf_amount"].astype(float).tolist()
            recent_avg = sum(days[-2:]) / 2
            prev_avg = sum(days[:-2]) / 3 if len(days) > 2 else 0
            if prev_avg > 0 and recent_avg > prev_avg * 1.2:
                score += 5.0
                details["inflow_accelerating"] = True
            else:
                details["inflow_accelerating"] = False

        score = max(0.0, min(score, limit))

        return {"score": round(score, 2), "max": limit, "details": details}

    # ==================================================================
    # 维度 4 — 基本面 (10%)
    # ==================================================================

    def _score_fundamental(
        self, ts_code: str, data: Dict[str, pd.DataFrame], limit: float,
    ) -> Dict[str, Any]:
        """PE(TTM) / PB / 股息率 / 市值评分。"""
        df = data.get("daily_basic", pd.DataFrame())
        if df.empty:
            return {"score": 0.0, "max": limit, "details": {}}

        stock_rows = df[df["ts_code"] == ts_code]
        if stock_rows.empty:
            return {"score": 0.0, "max": limit, "details": {}}

        row = stock_rows.iloc[0]
        pe_ttm = self._safe_val(row, "pe_ttm")
        pb = self._safe_val(row, "pb")
        dv_ttm = self._safe_val(row, "dv_ttm")
        total_mv = self._safe_val(row, "total_mv")

        score = 0.0
        details: Dict[str, Any] = {}

        # PE(TTM)
        if pe_ttm is not None and pe_ttm > 0:
            details["pe_ttm"] = round(pe_ttm, 2)
            if pe_ttm < 15:
                score += 3.0
            elif pe_ttm < 25:
                score += 1.0
            elif pe_ttm > 50:
                score -= 2.0

        # PB
        if pb is not None and pb > 0:
            details["pb"] = round(pb, 2)
            if pb < 1.5:
                score += 2.0
            elif pb < 3:
                score += 1.0
            elif pb > 8:
                score -= 2.0

        # 股息率
        if dv_ttm is not None:
            details["dv_ttm"] = round(dv_ttm, 2)
            if dv_ttm > 3:
                score += 3.0
            elif dv_ttm > 1.5:
                score += 1.0

        # 市值（单位：万元）
        if total_mv is not None:
            total_mv_yi = total_mv / 10000
            details["total_mv_yi"] = round(total_mv_yi, 2)
            if total_mv_yi > 100:
                score += 2.0
            elif total_mv_yi > 30:
                score += 1.0

        score = max(0.0, min(score, limit))

        return {"score": round(score, 2), "max": limit, "details": details}

    # ==================================================================
    # 维度 5 — 筹码与风险 (10%)
    # ==================================================================

    def _score_chip_risk(
        self, ts_code: str, data: Dict[str, pd.DataFrame], limit: float,
    ) -> Dict[str, Any]:
        """筹码穿透率 + 股权质押比例评分。"""
        score = 0.0
        details: Dict[str, Any] = {}

        # --- 筹码穿透率 ---
        cyq_df = data.get("cyq_perf", pd.DataFrame())
        if not cyq_df.empty:
            code_col = self._find_col(cyq_df, ["ts_code", "tc"])
            if code_col:
                match = cyq_df[cyq_df[code_col] == ts_code]
                if not match.empty:
                    row = match.iloc[0]
                    # 穿透率 ≈ winner_pct（获利筹码比例越高，上方压力越小）
                    winner_pct = self._safe_val(row, "winner_pct")
                    if winner_pct is not None:
                        details["winner_pct"] = round(winner_pct, 2)
                        if winner_pct > 70:
                            score += 5.0
                        elif winner_pct > 50:
                            score += 3.0

        # --- 股权质押比例 ---
        pledge_df = data.get("pledge_stat", pd.DataFrame())
        if not pledge_df.empty:
            code_col = self._find_col(pledge_df, ["ts_code", "tc"])
            ratio_col = self._find_col(pledge_df, ["pledge_ratio", "pr"])
            if code_col and ratio_col:
                match = pledge_df[pledge_df[code_col] == ts_code]
                if not match.empty:
                    pledge_ratio = self._safe_val(match.iloc[0], ratio_col)
                    if pledge_ratio is not None:
                        details["pledge_ratio"] = round(pledge_ratio, 2)
                        if pledge_ratio < 10:
                            score += 3.0
                        elif pledge_ratio < 30:
                            score += 1.0
                        elif pledge_ratio > 50:
                            score -= 3.0

        score = max(0.0, min(score, limit))

        return {"score": round(score, 2), "max": limit, "details": details}

    # ==================================================================
    # 内部工具方法
    # ==================================================================

    @staticmethod
    def _safe_val(row, col: str, default=None):
        """从 Series / dict 安全提取数值。"""
        try:
            v = row.get(col) if hasattr(row, "get") else row[col]
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return default
            return float(v)
        except (ValueError, TypeError, KeyError):
            return default

    @staticmethod
    def _find_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
        """在 DataFrame 列中查找第一个匹配的候选列名。"""
        for c in candidates:
            if c in df.columns:
                return c
        return None

    @staticmethod
    def _get_stock_row(df: pd.DataFrame, ts_code: str) -> Optional[Any]:
        """从 DataFrame 中提取指定 ts_code 的单行。"""
        if df.empty:
            return None
        code_col = None
        for c in ["ts_code", "tc"]:
            if c in df.columns:
                code_col = c
                break
        if not code_col:
            return None
        match = df[df[code_col] == ts_code]
        if match.empty:
            return None
        return match.iloc[0]
