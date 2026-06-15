# [修改] 问题1+6：使用 BaseService 基类，共享全局单例 TuShareClient 和 CacheService
"""Technical Indicator Stock Screener Service."""

import logging
from .base import BaseService
from ..utils import get_latest_trade_date

logger = logging.getLogger(__name__)


class TechnicalService(BaseService):
    """Service for technical indicator-based stock screening."""

    def screen_by_signals(self, trade_date: str = None, signals: dict = None,
                          page: int = 1, page_size: int = 50) -> dict:
        """Screen stocks by technical indicator signals.

        Args:
            trade_date: Trade date YYYYMMDD. None = latest.
            signals: Dict of signal flags:
                macd_golden: MACD golden cross (DIF crosses above DEA, macd>0, prev macd<=0)
                macd_dead: MACD death cross (DIF crosses below DEA, macd<0, prev macd>=0)
                kdj_golden: KDJ golden cross (K crosses above D)
                kdj_overbought: KDJ overbought (J>80)
                kdj_oversold: KDJ oversold (J<20)
                rsi_oversold: RSI oversold (rsi_6 < 30)
                rsi_overbought: RSI overbought (rsi_6 > 70)
                boll_break_upper: Break above Bollinger upper band
                boll_break_lower: Break below Bollinger lower band
                cci_oversold: CCI oversold (CCI < -100)
                cci_overbought: CCI overbought (CCI > 100)
                ma5_above_ma20: MA5 above MA20 (uptrend)
            page: Page number (1-based)
            page_size: Results per page
        """
        if trade_date is None:
            trade_date = get_latest_trade_date(self.cache)

        # Ensure stk_factor is cached
        self._ensure_stk_factor(trade_date)

        # Get all stk_factor records for this trade date
        all_stocks = self.cache.get_stk_factor_all(trade_date)
        if not all_stocks:
            return {"total": 0, "page": page, "page_size": page_size,
                    "trade_date": trade_date, "data": []}

        # Apply signal filters
        if signals:
            all_stocks = self._apply_signals(all_stocks, signals, trade_date)

        # Paginate
        total = len(all_stocks)
        start = (page - 1) * page_size
        end = start + page_size
        page_data = all_stocks[start:end]

        # Format output
        formatted = []
        for stock in page_data:
            signal_summary = self._get_signal_summary(stock)
            formatted.append({
                "ts_code": stock.get("ts_code", ""),
                "name": stock.get("name", ""),
                "industry": stock.get("industry", ""),
                "close": round(stock.get("close", 0) or 0, 2),
                "pct_change": round(stock.get("pct_change", 0) or 0, 2),
                "macd_dif": round(stock.get("macd_dif", 0) or 0, 4),
                "macd_dea": round(stock.get("macd_dea", 0) or 0, 4),
                "macd": round(stock.get("macd", 0) or 0, 4),
                "kdj_k": round(stock.get("kdj_k", 0) or 0, 2),
                "kdj_d": round(stock.get("kdj_d", 0) or 0, 2),
                "kdj_j": round(stock.get("kdj_j", 0) or 0, 2),
                "rsi_6": round(stock.get("rsi_6", 0) or 0, 2),
                "rsi_12": round(stock.get("rsi_12", 0) or 0, 2),
                "rsi_24": round(stock.get("rsi_24", 0) or 0, 2),
                "boll_upper": round(stock.get("boll_upper", 0) or 0, 2),
                "boll_mid": round(stock.get("boll_mid", 0) or 0, 2),
                "boll_lower": round(stock.get("boll_lower", 0) or 0, 2),
                "cci": round(stock.get("cci", 0) or 0, 2),
                "signal_summary": signal_summary,
            })

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "trade_date": trade_date,
            "data": formatted,
        }

    def _ensure_stk_factor(self, trade_date: str):
        """Fetch stk_factor from TuShare if not cached."""
        cached_count = self.cache.get_stk_factor_count(trade_date)
        if cached_count >= 3000:
            return

        logger.info(f"Fetching stk_factor for {trade_date} from TuShare (cached: {cached_count})")
        try:
            df = self.client.get_stk_factor(trade_date)
            if df is not None and not df.empty:
                self.cache.upsert_stk_factor(df, trade_date)
                logger.info(f"Cached {len(df)} stk_factor records for {trade_date}")
        except Exception as e:
            logger.error(f"Error fetching stk_factor: {e}")

    def _apply_signals(self, stocks: list, signals: dict, trade_date: str) -> list:
        """Apply signal filters to stock list."""
        result = stocks

        # For crossover signals, we need previous day data
        crossover_signals = any(signals.get(k) for k in [
            "macd_golden", "macd_dead", "kdj_golden"
        ])
        prev_data = {}
        if crossover_signals:
            ts_codes = [s.get("ts_code") for s in stocks]
            prev_records = self.cache.get_stk_factor_prev_day(trade_date, ts_codes)
            for r in prev_records:
                prev_data[r["ts_code"]] = r

        # MACD golden cross: DIF > DEA today, macd > 0, prev macd <= 0
        if signals.get("macd_golden"):
            result = [
                s for s in result
                if self._check_macd_golden(s, prev_data.get(s.get("ts_code", ""), {}))
            ]

        # MACD death cross: DIF < DEA today, macd < 0, prev macd >= 0
        if signals.get("macd_dead"):
            result = [
                s for s in result
                if self._check_macd_dead(s, prev_data.get(s.get("ts_code", ""), {}))
            ]

        # KDJ golden cross: K > D today, prev K <= D
        if signals.get("kdj_golden"):
            result = [
                s for s in result
                if self._check_kdj_golden(s, prev_data.get(s.get("ts_code", ""), {}))
            ]

        # KDJ overbought: J > 80
        if signals.get("kdj_overbought"):
            result = [s for s in result if (s.get("kdj_j") or 0) > 80]

        # KDJ oversold: J < 20
        if signals.get("kdj_oversold"):
            result = [s for s in result if (s.get("kdj_j") or 0) < 20]

        # RSI oversold: rsi_6 < 30
        if signals.get("rsi_oversold"):
            result = [s for s in result if (s.get("rsi_6") or 0) < 30]

        # RSI overbought: rsi_6 > 70
        if signals.get("rsi_overbought"):
            result = [s for s in result if (s.get("rsi_6") or 0) > 70]

        # Break above Bollinger upper band: close > boll_upper
        if signals.get("boll_break_upper"):
            result = [
                s for s in result
                if (s.get("close") or 0) > (s.get("boll_upper") or 0)
                and (s.get("boll_upper") or 0) > 0
            ]

        # Break below Bollinger lower band: close < boll_lower
        if signals.get("boll_break_lower"):
            result = [
                s for s in result
                if (s.get("close") or 0) < (s.get("boll_lower") or 0)
                and (s.get("boll_lower") or 0) > 0
            ]

        # CCI oversold: CCI < -100
        if signals.get("cci_oversold"):
            result = [s for s in result if (s.get("cci") or 0) < -100]

        # CCI overbought: CCI > 100
        if signals.get("cci_overbought"):
            result = [s for s in result if (s.get("cci") or 0) > 100]

        # MA5/MA20 golden cross: compute real MA5 and MA20 from daily_price data
        if signals.get("ma5_above_ma20"):
            ma5_above_set = self._batch_check_ma5_above_ma20(
                [s.get("ts_code") for s in result if s.get("ts_code")]
            )
            result = [s for s in result if s.get("ts_code") in ma5_above_set]

        return result

    def _check_macd_golden(self, stock: dict, prev: dict) -> bool:
        """MACD golden cross: current macd > 0 and prev macd <= 0."""
        cur_macd = stock.get("macd") or 0
        prev_macd = prev.get("macd") or 0
        return cur_macd > 0 and prev_macd <= 0

    def _check_macd_dead(self, stock: dict, prev: dict) -> bool:
        """MACD death cross: current macd < 0 and prev macd >= 0."""
        cur_macd = stock.get("macd") or 0
        prev_macd = prev.get("macd") or 0
        return cur_macd < 0 and prev_macd >= 0

    def _check_kdj_golden(self, stock: dict, prev: dict) -> bool:
        """KDJ golden cross: current K > D and prev K <= D."""
        cur_k = stock.get("kdj_k") or 0
        cur_d = stock.get("kdj_d") or 0
        prev_k = prev.get("kdj_k") or 0
        prev_d = prev.get("kdj_d") or 0
        return cur_k > cur_d and prev_k <= prev_d

    def _check_ma5_above_ma20_proxy(self, stock: dict, prev: dict) -> bool:
        """Approximate MA5 > MA20 check — kept for backward compatibility.

        This is a simplified proxy; prefer _batch_check_ma5_above_ma20 for
        accurate golden-cross detection using real daily close data.
        """
        cur_close = stock.get("close") or 0
        prev_close = prev.get("close") if prev else 0
        return cur_close > 0 and prev_close > 0 and cur_close > prev_close

    def _batch_check_ma5_above_ma20(self, ts_codes: list) -> set:
        """Batch-check MA5 golden cross above MA20 for a list of stocks.

        Fetches the last 20 daily closes from the database, computes MA5 and
        MA20 for the current and previous trading days, and returns the set of
        ts_codes where MA5 just crossed above MA20 (golden cross):
            today:  MA5 > MA20
            yesterday: MA5 <= MA20
        """
        if not ts_codes:
            return set()

        closes_map = self.cache.get_daily_closes_batch(ts_codes, days=21)
        golden_cross_set = set()

        for tc, closes in closes_map.items():
            if len(closes) < 20:
                continue
            # closes is ordered most-recent-first
            cur_ma5 = sum(closes[:5]) / 5
            cur_ma20 = sum(closes[:20]) / 20
            prev_ma5 = sum(closes[1:6]) / 5
            prev_ma20 = sum(closes[1:21]) / 20

            if cur_ma5 > cur_ma20 and prev_ma5 <= prev_ma20:
                golden_cross_set.add(tc)

        return golden_cross_set

    def _get_signal_summary(self, stock: dict) -> list:
        """Generate list of triggered signal labels for a stock."""
        signals = []
        macd = stock.get("macd") or 0
        kdj_j = stock.get("kdj_j") or 0
        kdj_k = stock.get("kdj_k") or 0
        kdj_d = stock.get("kdj_d") or 0
        rsi_6 = stock.get("rsi_6") or 0
        cci = stock.get("cci") or 0
        close = stock.get("close") or 0
        boll_upper = stock.get("boll_upper") or 0
        boll_lower = stock.get("boll_lower") or 0

        if macd > 0:
            signals.append("MACD多头")
        elif macd < 0:
            signals.append("MACD空头")

        if kdj_j > 80:
            signals.append("KDJ超买")
        elif kdj_j < 20:
            signals.append("KDJ超卖")

        if kdj_k > kdj_d:
            signals.append("KDJ金叉")
        else:
            signals.append("KDJ死叉")

        if rsi_6 > 70:
            signals.append("RSI超买")
        elif rsi_6 < 30:
            signals.append("RSI超卖")

        if cci > 100:
            signals.append("CCI超买")
        elif cci < -100:
            signals.append("CCI超卖")

        if boll_upper > 0 and close > boll_upper:
            signals.append("突破上轨")
        elif boll_lower > 0 and close < boll_lower:
            signals.append("跌破下轨")

        return signals
