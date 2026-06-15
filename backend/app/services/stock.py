# [修改] 问题1+6：使用 BaseService 基类，共享全局单例 TuShareClient 和 CacheService
import logging
from datetime import datetime, timedelta
from sqlalchemy import text
import pandas as pd

from .base import BaseService
from ..utils import get_latest_trade_date, get_last_n_trade_dates, net_flow

logger = logging.getLogger(__name__)


class StockService(BaseService):
    """Service for individual stock flow and dragon tiger data."""

    def search_stocks(self, query: str) -> list:
        """Search stocks by name, ts_code, or symbol (fuzzy match)."""
        return self.cache.search_stocks(query)

    def get_stock_flow(self, ts_code: str, trade_date: str = None) -> dict:
        """Get individual stock capital flow details."""
        if trade_date is None:
            trade_date = get_latest_trade_date(self.cache)

        # Check cache
        if self.cache.is_fresh("stock_flow", trade_date):
            cached = self.cache.get_stock_flow(trade_date, ts_code)
            if cached:
                return _format_stock_flow(cached)

        # Fetch from TuShare
        try:
            df = self.client.get_moneyflow(ts_code=ts_code, trade_date=trade_date)
            if df is not None and not df.empty:
                # Single-stock upsert: only write the requested stock's data
                df_single = df[df["ts_code"] == ts_code] if "ts_code" in df.columns else df
                if not df_single.empty:
                    self.cache.upsert_stock_flows(df_single, trade_date)
                cached = self.cache.get_stock_flow(trade_date, ts_code)
                if cached:
                    return _format_stock_flow(cached)
        except Exception as e:
            logger.error(f"Error fetching stock flow for {ts_code}: {e}")

        # Fallback to stale cache
        cached = self.cache.get_stock_flow(trade_date, ts_code)
        if cached:
            return _format_stock_flow(cached)

        return _empty_stock_flow(ts_code, trade_date)

    def get_dragon_tiger(self, ts_code: str, trade_date: str = None) -> list:
        """Get dragon tiger list data for a specific stock."""
        if trade_date is None:
            trade_date = get_latest_trade_date(self.cache)

        # Check cache
        if self.cache.is_fresh("dragon_tiger", trade_date):
            cached_list = self.cache.get_dragon_tiger(trade_date, ts_code)
            if cached_list:
                return [_format_dragon_tiger(item, ts_code, trade_date) for item in cached_list]

        # Fetch from TuShare
        try:
            df = self.client.get_top_list(trade_date=trade_date)
            if df is not None and not df.empty:
                self.cache.upsert_dragon_tiger(df, trade_date)
                cached_list = self.cache.get_dragon_tiger(trade_date, ts_code)
                if cached_list:
                    return [_format_dragon_tiger(item, ts_code, trade_date) for item in cached_list]
        except Exception as e:
            logger.error(f"Error fetching dragon tiger for {ts_code}: {e}")

        # Fallback to stale cache
        cached_list = self.cache.get_dragon_tiger(trade_date, ts_code)
        if cached_list:
            return [_format_dragon_tiger(item, ts_code, trade_date) for item in cached_list]

        return []

    def get_daily_prices(self, ts_code: str, days: int = 20) -> list:
        """Get recent N trading days daily price data for K-line chart."""
        # Check cache first
        if self.cache.is_fresh("daily_price"):
            cached = self.cache.get_daily_prices(ts_code, days)
            if cached and len(cached) >= min(days, 5):
                return _format_daily_prices(cached)

        # Fetch from TuShare (get more days to account for holidays)
        try:
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days * 2)).strftime("%Y%m%d")
            df = self.client.get_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                self.cache.upsert_daily_prices(df, ts_code)
                cached = self.cache.get_daily_prices(ts_code, days)
                if cached:
                    return _format_daily_prices(cached)
        except Exception as e:
            logger.error(f"Error fetching daily prices for {ts_code}: {e}")

        # Fallback to stale cache
        cached = self.cache.get_daily_prices(ts_code, days)
        if cached:
            return _format_daily_prices(cached)

        return []

    def get_stock_flow_trend(self, ts_code: str, days: int = 10) -> dict:
        """Get individual stock capital flow trend for last N trading days.

        Returns:
            {labels: ['MM/DD', ...], series: {main_net: [...], super_large: [...], ...}}
        """
        trade_date = get_latest_trade_date(self.cache)

        # Generate candidate trading dates (skip weekends + holidays)
        candidate_dates = get_last_n_trade_dates(trade_date, days)
        candidate_dates.append(trade_date)
        candidate_dates = sorted(set(candidate_dates))

        # Query DB for existing data (single range query)
        session = self.cache.Session()
        existing = {}
        try:
            results = session.execute(
                text("SELECT * FROM stock_flow WHERE trade_date BETWEEN :start AND :end AND ts_code = :tc"),
                {"start": candidate_dates[0], "end": candidate_dates[-1], "tc": ts_code},
            ).fetchall()
            for row in results:
                td = row._mapping["trade_date"]
                existing[td] = dict(row._mapping)

            # 收集缺失的交易日，一次性批量查询 TuShare
            missing_dates = [d for d in candidate_dates if d not in existing]
            if missing_dates:
                missing_start = missing_dates[0]
                missing_end = missing_dates[-1]
                try:
                    df = self.client.get_moneyflow(
                        ts_code=ts_code,
                        start_date=missing_start,
                        end_date=missing_end,
                    )
                    if df is not None and not df.empty:
                        # 按 trade_date 分组批量写入缓存
                        if "trade_date" in df.columns:
                            for td, group in df.groupby("trade_date"):
                                self.cache.upsert_stock_flows(group, td)
                        else:
                            self.cache.upsert_stock_flows(df, missing_end)
                        # 重新从 DB 读取缺失日期的数据
                        session.expire_all()
                        for d in missing_dates:
                            result = session.execute(
                                text("SELECT * FROM stock_flow WHERE trade_date = :td AND ts_code = :tc"),
                                {"td": d, "tc": ts_code},
                            ).fetchone()
                            if result:
                                existing[d] = dict(result._mapping)
                except Exception as e:
                    logger.error(f"Error fetching stock flow for {ts_code} ({missing_start}~{missing_end}): {e}")
        finally:
            session.close()

        # Build trend data from available records (sorted by date)
        dates_sorted = sorted(existing.keys())
        labels = [d[4:6] + "/" + d[6:8] for d in dates_sorted]

        return {
            "labels": labels,
            "series": {
                "main_net": [round(
                    net_flow(existing[d], "buy_elg_amount", "sell_elg_amount")
                    + net_flow(existing[d], "buy_lg_amount", "sell_lg_amount"), 2
                ) for d in dates_sorted],
                "super_large": [net_flow(existing[d], "buy_elg_amount", "sell_elg_amount") for d in dates_sorted],
                "large": [net_flow(existing[d], "buy_lg_amount", "sell_lg_amount") for d in dates_sorted],
                "medium": [net_flow(existing[d], "buy_md_amount", "sell_md_amount") for d in dates_sorted],
                "small": [net_flow(existing[d], "buy_sm_amount", "sell_sm_amount") for d in dates_sorted],
            },
        }

    def get_stock_basic_info(self, ts_code: str) -> dict:
        """Get stock daily basic info (PE, PB, market cap, etc.)."""
        trade_date = get_latest_trade_date(self.cache)

        # Check cache
        if self.cache.is_fresh("daily_basic"):
            cached = self.cache.get_daily_basic(ts_code, trade_date)
            if cached:
                return _format_daily_basic(cached)

        # Fetch from TuShare
        try:
            df = self.client.get_daily_basic(ts_code=ts_code, trade_date=trade_date)
            if df is not None and not df.empty:
                self.cache.upsert_daily_basic(df, ts_code)
                cached = self.cache.get_daily_basic(ts_code, trade_date)
                if cached:
                    return _format_daily_basic(cached)
        except Exception as e:
            logger.error(f"Error fetching daily_basic for {ts_code}: {e}")

        # Fallback to stale cache
        cached = self.cache.get_daily_basic(ts_code, trade_date)
        if cached:
            return _format_daily_basic(cached)

        return _empty_daily_basic(ts_code)


def _format_stock_flow(data: dict) -> dict:
    """Format stock flow response with computed fields."""
    buy_lg = data.get("buy_lg_amount", 0) or 0
    sell_lg = data.get("sell_lg_amount", 0) or 0
    buy_elg = data.get("buy_elg_amount", 0) or 0
    sell_elg = data.get("sell_elg_amount", 0) or 0

    large_net = buy_lg - sell_lg
    super_large_net = buy_elg - sell_elg
    main_net = large_net + super_large_net

    # Large order ratio (large + super large as proportion of total)
    total_buy = sum([
        data.get("buy_sm_amount", 0) or 0,
        data.get("buy_md_amount", 0) or 0,
        buy_lg, buy_elg,
    ])
    total_sell = sum([
        data.get("sell_sm_amount", 0) or 0,
        data.get("sell_md_amount", 0) or 0,
        sell_lg, sell_elg,
    ])
    total_flow = total_buy + total_sell
    large_pct = (main_net / total_flow * 100) if total_flow > 0 else 0

    return {
        "trade_date": data.get("trade_date", ""),
        "ts_code": data.get("ts_code", ""),
        "name": data.get("name", ""),
        "close": data.get("close", 0),
        "pct_change": data.get("pct_change", 0),
        "turnover_rate": data.get("turnover_rate", 0),
        "main_net_inflow": round(main_net, 2),
        "super_large_net": round(super_large_net, 2),
        "large_net": round(large_net, 2),
        "medium_net": round(
            (data.get("buy_md_amount", 0) or 0) - (data.get("sell_md_amount", 0) or 0), 2
        ),
        "small_net": round(
            (data.get("buy_sm_amount", 0) or 0) - (data.get("sell_sm_amount", 0) or 0), 2
        ),
        "large_net_vol": round(
            (data.get("buy_lg_vol", 0) or 0) - (data.get("sell_lg_vol", 0) or 0), 2
        ),
        "large_pct": round(large_pct, 2),
        "net_mf_vol": data.get("net_mf_vol", 0),
        "net_mf_amount": data.get("net_mf_amount", 0),
        # Raw detail
        "detail": {
            "buy_sm_vol": data.get("buy_sm_vol", 0),
            "buy_sm_amount": data.get("buy_sm_amount", 0),
            "sell_sm_vol": data.get("sell_sm_vol", 0),
            "sell_sm_amount": data.get("sell_sm_amount", 0),
            "buy_md_vol": data.get("buy_md_vol", 0),
            "buy_md_amount": data.get("buy_md_amount", 0),
            "sell_md_vol": data.get("sell_md_vol", 0),
            "sell_md_amount": data.get("sell_md_amount", 0),
            "buy_lg_vol": data.get("buy_lg_vol", 0),
            "buy_lg_amount": data.get("buy_lg_amount", 0),
            "sell_lg_vol": data.get("sell_lg_vol", 0),
            "sell_lg_amount": data.get("sell_lg_amount", 0),
            "buy_elg_vol": data.get("buy_elg_vol", 0),
            "buy_elg_amount": data.get("buy_elg_amount", 0),
            "sell_elg_vol": data.get("sell_elg_vol", 0),
            "sell_elg_amount": data.get("sell_elg_amount", 0),
        },
    }


def _format_dragon_tiger(data: dict, ts_code: str, trade_date: str) -> dict:
    """Format dragon tiger response."""
    if not data:
        return _empty_dragon_tiger(ts_code, trade_date)
    return {
        "trade_date": data.get("trade_date", trade_date),
        "ts_code": data.get("ts_code", ts_code),
        "name": data.get("name", ""),
        "close": data.get("close", 0),
        "pct_change": data.get("pct_change", 0),
        "turnover_rate": data.get("turnover_rate", 0),
        "amount": data.get("amount", 0),
        "net_buy": data.get("net_buy", 0),
        "reason": data.get("reason", ""),
        "net_rate": data.get("net_rate", 0),
    }


def _empty_stock_flow(ts_code: str, trade_date: str) -> dict:
    return {
        "trade_date": trade_date,
        "ts_code": ts_code,
        "name": "",
        "close": 0,
        "pct_change": 0,
        "turnover_rate": 0,
        "main_net_inflow": 0,
        "super_large_net": 0,
        "large_net": 0,
        "medium_net": 0,
        "small_net": 0,
        "large_net_vol": 0,
        "large_pct": 0,
        "net_mf_vol": 0,
        "net_mf_amount": 0,
        "detail": {},
    }


def _empty_dragon_tiger(ts_code: str, trade_date: str) -> dict:
    return {
        "trade_date": trade_date,
        "ts_code": ts_code,
        "name": "",
        "close": 0,
        "pct_change": 0,
        "turnover_rate": 0,
        "amount": 0,
        "net_buy": 0,
        "reason": "",
        "net_rate": 0,
    }


def _format_daily_prices(data: list) -> list:
    """Format daily prices for K-line chart (ascending by date)."""
    # Data comes in descending order, reverse to ascending
    result = []
    for item in reversed(data):
        result.append({
            "trade_date": item.get("trade_date", ""),
            "open": round(item.get("open", 0), 2),
            "high": round(item.get("high", 0), 2),
            "low": round(item.get("low", 0), 2),
            "close": round(item.get("close", 0), 2),
            "pre_close": round(item.get("pre_close", 0), 2),
            "change": round(item.get("change", 0), 2),
            "pct_chg": round(item.get("pct_chg", 0), 2),
            "vol": round(item.get("vol", 0), 2),
            "amount": round(item.get("amount", 0), 2),
        })
    return result


def _format_daily_basic(data: dict) -> dict:
    """Format daily basic response."""
    return {
        "trade_date": data.get("trade_date", ""),
        "ts_code": data.get("ts_code", ""),
        "pe_ttm": round(data.get("pe_ttm", 0) or 0, 2),
        "pe": round(data.get("pe", 0) or 0, 2),
        "pb": round(data.get("pb", 0) or 0, 2),
        "ps_ttm": round(data.get("ps_ttm", 0) or 0, 2),
        "dv_ratio": round(data.get("dv_ratio", 0) or 0, 2),
        "total_share": round(data.get("total_share", 0) or 0, 2),
        "float_share": round(data.get("float_share", 0) or 0, 2),
        "total_mv": round(data.get("total_mv", 0) or 0, 2),
        "circ_mv": round(data.get("circ_mv", 0) or 0, 2),
        "turnover_rate": round(data.get("turnover_rate", 0) or 0, 2),
        "turnover_rate_f": round(data.get("turnover_rate_f", 0) or 0, 2),
        "volume_ratio": round(data.get("volume_ratio", 0) or 0, 2),
    }


def _empty_daily_basic(ts_code: str) -> dict:
    return {
        "trade_date": "",
        "ts_code": ts_code,
        "pe_ttm": 0,
        "pe": 0,
        "pb": 0,
        "ps_ttm": 0,
        "dv_ratio": 0,
        "total_share": 0,
        "float_share": 0,
        "total_mv": 0,
        "circ_mv": 0,
        "turnover_rate": 0,
        "turnover_rate_f": 0,
        "volume_ratio": 0,
    }
