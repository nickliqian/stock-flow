# [修改] 问题1+6：使用 BaseService 基类，共享全局单例 TuShareClient 和 CacheService
import logging
from datetime import datetime, timedelta
from sqlalchemy import text
import pandas as pd

from .base import BaseService
from ..utils import get_latest_trade_date, get_last_n_trade_dates, is_holiday, aggregate_moneyflow, net_flow

logger = logging.getLogger(__name__)


def _get_prev_trade_date(trade_date: str, n: int = 1) -> str:
    """从 trade_date 向前回溯 n 个交易日（跳过周末和法定节假日）。"""
    dt = datetime.strptime(trade_date, "%Y%m%d")
    result = dt
    count = 0
    while count < n:
        result -= timedelta(days=1)
        if result.weekday() < 5 and not is_holiday(result):
            count += 1
    return result.strftime("%Y%m%d")


class MarketService(BaseService):
    """Service for market overview and north fund data."""

    def get_overview(self, trade_date: str = None) -> dict:
        """Get market capital flow overview."""
        if trade_date is None:
            trade_date = get_latest_trade_date(self.cache)

        # Try cache first
        if self.cache.is_fresh("market_flow", trade_date):
            cached = self.cache.get_market_flow(trade_date)
            if cached:
                return _format_overview(cached, trade_date)

        # Fetch from TuShare
        try:
            df = self.client.get_moneyflow(trade_date=trade_date)
            if df is None or df.empty:
                # Try to return stale cache
                cached = self.cache.get_market_flow(trade_date)
                if cached:
                    return _format_overview(cached, trade_date)
                return _empty_overview(trade_date)

            # Aggregate across all stocks for this date
            agg = aggregate_moneyflow(df)
            # Store aggregated result as a single row
            agg_df = pd.DataFrame([agg])
            self.cache.upsert_market_flow(agg_df, trade_date)
            return _format_overview(agg, trade_date)
        except Exception as e:
            logger.error(f"Error fetching market overview: {e}")
            cached = self.cache.get_market_flow(trade_date)
            if cached:
                return _format_overview(cached, trade_date)
            return _empty_overview(trade_date)

    def get_north_fund(self, trade_date: str = None) -> dict:
        """Get north fund flow with historical comparison."""
        if trade_date is None:
            trade_date = get_latest_trade_date(self.cache)

        prev_date = _get_prev_trade_date(trade_date, 1)
        last_5_dates = get_last_n_trade_dates(trade_date, 5)
        oldest_5_date = min(last_5_dates)

        # Build a deduplicated set of all dates we need
        needed_dates = {trade_date, prev_date} | set(last_5_dates)

        # Check cache for all needed dates in one range query
        cached_range = self.cache.get_north_fund_range(oldest_5_date, trade_date)
        cached_by_date = {}
        for d in cached_range:
            td = d.get("trade_date")
            if td:
                cached_by_date[td] = d

        # Fetch only missing dates from TuShare (no duplicate calls)
        fetched_any = False
        for date_str in sorted(needed_dates):
            if date_str not in cached_by_date:
                try:
                    df = self.client.get_moneyflow_hsgt(trade_date=date_str)
                    if df is not None and not df.empty:
                        self.cache.upsert_north_fund(df, date_str)
                        fetched_any = True
                except Exception as e:
                    logger.error(f"Error fetching north fund for {date_str}: {e}")

        # Re-read from cache after fetching new data
        if fetched_any:
            cached_range = self.cache.get_north_fund_range(oldest_5_date, trade_date)
            cached_by_date = {d.get("trade_date"): d for d in cached_range if d.get("trade_date")}

        today_data = cached_by_date.get(trade_date)
        yesterday_data = cached_by_date.get(prev_date)
        last_5_data = [cached_by_date[d] for d in last_5_dates if d in cached_by_date]

        return _format_north_fund(today_data, yesterday_data, last_5_data, trade_date)

    def get_market_trend(self, trade_date: str = None, days: int = 10) -> dict:
        """Get market capital flow trend for last N trading days.

        Returns:
            {labels: ['MM/DD', ...], series: {main_net: [...], super_large: [...], ...}}
        """
        if trade_date is None:
            trade_date = get_latest_trade_date(self.cache)

        # Generate candidate trading dates (skip weekends)
        candidate_dates = get_last_n_trade_dates(trade_date, days)
        # Include trade_date itself
        candidate_dates.append(trade_date)
        candidate_dates = sorted(set(candidate_dates))

        # Query DB for existing data (single range query)
        existing = {}
        with self.cache._session() as session:
            results = session.execute(
                text("SELECT * FROM market_flow WHERE trade_date BETWEEN :start AND :end"),
                {"start": candidate_dates[0], "end": candidate_dates[-1]},
            ).fetchall()
            for row in results:
                td = row._mapping["trade_date"]
                existing[td] = dict(row._mapping)

        # Fill gaps from TuShare — 一次性调用覆盖整段日期范围，避免逐日调用
        missing_dates = [d for d in candidate_dates if d not in existing]
        if missing_dates:
            try:
                start_d = min(missing_dates)
                end_d = max(missing_dates)
                df = self.client.get_moneyflow(start_date=start_d, end_date=end_d)
                if df is not None and not df.empty:
                    # 按 trade_date 分组聚合，分别缓存
                    for td, group in df.groupby("trade_date"):
                        agg = aggregate_moneyflow(group)
                        agg_df = pd.DataFrame([agg])
                        self.cache.upsert_market_flow(agg_df, td)
                        existing[td] = agg
            except Exception as e:
                logger.error(f"Error fetching moneyflow for range {start_d}-{end_d}: {e}")

        # Build trend data from available records (sorted by date)
        dates_sorted = sorted(existing.keys())
        labels = [d[4:6] + "/" + d[6:8] for d in dates_sorted]

        return {
            "labels": labels,
            "series": {
                # 主力 = 超大单 + 大单
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

    def get_stock_ranking(self, trade_date: str = None, ranking_type: str = "net_inflow", limit: int = 20) -> dict:
        """Get stock ranking by net capital flow (moneyflow_dc, eastmoney).

        Args:
            trade_date: YYYYMMDD, defaults to latest
            ranking_type: "net_inflow" (top inflow) or "net_outflow" (top outflow)
            limit: number of results, default 20
        """
        if trade_date is None:
            trade_date = get_latest_trade_date(self.cache)

        try:
            # Try cache first — use lightweight COUNT check instead of loading all rows
            cache_exists = self.cache.has_moneyflow_dc(trade_date)

            if not cache_exists:
                # Cache miss — fetch from TuShare and store
                df = self.client.get_moneyflow_dc(trade_date=trade_date)
                if df is not None and not df.empty:
                    self.cache.upsert_moneyflow_dc(df, trade_date)
                    cache_exists = self.cache.has_moneyflow_dc(trade_date)

            if not cache_exists:
                return {"trade_date": trade_date, "type": ranking_type, "items": []}

            # Use SQL-level sorting + LIMIT instead of loading all records
            sorted_rows = self.cache.get_moneyflow_dc_ranking(trade_date, ranking_type, limit)

            # Build stock name cache — 优先从数据库读取，不调用 API
            name_map = {}
            try:
                # 检查 stock_basic 缓存是否有效（60分钟内）
                if self.cache.is_fresh("stock_basic"):
                    basic_rows = self.cache.get_stock_basic_from_db()
                    if basic_rows:
                        name_map = {r["ts_code"]: r["name"] for r in basic_rows}
                if not name_map:
                    # 数据库无数据或过期，从 API 获取并缓存
                    basic_df = self.client.get_stock_basic()
                    if basic_df is not None and not basic_df.empty:
                        self.cache.upsert_stock_basic(basic_df)
                        name_map = dict(zip(basic_df["ts_code"], basic_df["name"]))
            except Exception as e:
                logger.warning(f"Error fetching stock_basic for names: {e}")

            records = []
            for row in sorted_rows:
                ts_code = row.get("ts_code", "")
                net_amount = float(row.get("net_mf_amount", 0))
                records.append({
                    "ts_code": ts_code,
                    "name": name_map.get(ts_code, ""),
                    "close": float(row.get("close", 0)),
                    "pct_change": float(row.get("pct_change", 0)),
                    "net_amount": net_amount,
                    "buy_elg_amount": float(row.get("buy_elg_amount", 0)),
                    "buy_lg_amount": float(row.get("buy_lg_amount", 0)),
                })

            return {
                "trade_date": trade_date,
                "type": ranking_type,
                "items": records,
            }
        except Exception as e:
            logger.error(f"Error fetching stock ranking: {e}")
            return {"trade_date": trade_date, "type": ranking_type, "items": []}

    def get_fund_trend(self, days: int = 10) -> dict:
        """Get north fund trend for last N trading days.

        Returns:
            {labels: ['MM/DD', ...], series: {north_money: [...], hgt: [...], sgt: [...]}}
        """
        with self.cache._session() as session:
            results = session.execute(text("""
                SELECT trade_date, north_money, hgt, sgt
                FROM north_fund_flow
                ORDER BY trade_date DESC
                LIMIT :days
            """), {"days": days}).fetchall()

            if not results:
                return {"labels": [], "series": {}}

            # Reverse to chronological order
            results = list(reversed(results))

            labels = [r[0][4:6] + '/' + r[0][6:8] for r in results]  # MM/DD format
            north_money = [round(r[1], 2) for r in results]
            hgt = [round(r[2], 2) for r in results]
            sgt = [round(r[3], 2) for r in results]

            return {
                "labels": labels,
                "series": {
                    "north_money": north_money,
                    "hgt": hgt,
                    "sgt": sgt,
                }
            }

    def get_turnover_trend(self, days: int = 30) -> dict:
        """Get total market turnover trend for last N trading days.

        Total turnover = sum of all buy + sell amounts from market_flow table.
        Returns:
            {labels: ['MM/DD', ...], values: [float, ...]}
        """
        with self.cache._session() as session:
            results = session.execute(text("""
                SELECT trade_date,
                       (buy_sm_amount + buy_md_amount
                        + buy_lg_amount + buy_elg_amount) as total_turnover
                FROM market_flow
                ORDER BY trade_date DESC
                LIMIT :days
            """), {"days": days}).fetchall()

            if not results:
                return {"labels": [], "values": []}

            # Reverse to chronological order
            results = list(reversed(results))

            labels = [r[0][4:6] + '/' + r[0][6:8] for r in results]
            values = [round(r[1], 2) for r in results]

            return {
                "labels": labels,
                "values": values,
                "latest": values[-1] if values else 0,
            }

    # [修改] 问题3：优先使用 limit_list 表数据判断涨停/跌停，fallback 到百分比阈值
    def get_market_breadth(self, trade_date: str = None) -> dict:
        """获取全市场涨跌分布（Market Breadth）."""
        if trade_date is None:
            trade_date = get_latest_trade_date(self.cache)

        try:
            # Use lightweight check to decide whether to fetch from API
            cache_exists = self.cache.has_moneyflow_dc(trade_date)
            if not cache_exists:
                fetched_df = self.client.get_moneyflow_dc(trade_date=trade_date)
                if fetched_df is not None and not fetched_df.empty:
                    self.cache.upsert_moneyflow_dc(fetched_df, trade_date)
                    cache_exists = True

            if not cache_exists:
                return {"trade_date": trade_date, "total_stocks": 0}

            # Load data only after confirming cache has records
            cached_rows = self.cache.get_moneyflow_dc(trade_date)
            df = pd.DataFrame(cached_rows)
            pct_changes = df["pct_change"].dropna()

            total = len(pct_changes)
            up = int((pct_changes > 0).sum())
            down = int((pct_changes < 0).sum())
            flat = int((pct_changes == 0).sum())

            # 优先使用 limit_list 表数据（更准确），fallback 到百分比阈值判断
            limit_up = 0
            limit_down = 0
            try:
                limit_rows = self.cache.get_limit_list(trade_date)
                if limit_rows:
                    limit_up = sum(1 for r in limit_rows if r.get("limit_type") == "U")
                    limit_down = sum(1 for r in limit_rows if r.get("limit_type") == "D")
                else:
                    # limit_list 为空时 fallback 到百分比阈值
                    limit_up = int((pct_changes >= 9.9).sum())
                    limit_down = int((pct_changes <= -9.9).sum())
            except Exception:
                # fallback 到百分比阈值
                limit_up = int((pct_changes >= 9.9).sum())
                limit_down = int((pct_changes <= -9.9).sum())

            bins = [float("-inf"), -9, -5, -3, 0, 3, 5, 9, float("inf")]
            labels = ["<-9%", "-9%~-5%", "-5%~-3%", "-3%~0%", "0%~3%", "3%~5%", "5%~9%", ">9%"]
            counts = pd.cut(pct_changes, bins=bins, labels=labels, right=False).value_counts().reindex(labels, fill_value=0)

            distribution = [{"range": label, "count": int(counts[label])} for label in labels]

            return {
                "trade_date": trade_date,
                "total_stocks": total,
                "up_count": up,
                "down_count": down,
                "flat_count": flat,
                "limit_up": limit_up,
                "limit_down": limit_down,
                "distribution": distribution,
                "avg_pct_change": round(float(pct_changes.mean()), 2),
            }
        except Exception as e:
            logger.error(f"Error fetching market breadth: {e}")
            return {"trade_date": trade_date, "total_stocks": 0}

    def get_limit_stats(self, trade_date: str = None) -> dict:
        """获取涨跌停统计数据。"""
        if trade_date is None:
            trade_date = get_latest_trade_date(self.cache)

        # Try cache first
        if self.cache.is_fresh("limit_list", trade_date):
            cached = self.cache.get_limit_list(trade_date)
            if cached:
                return _format_limit_stats(cached, trade_date)

        # Fetch from TuShare
        try:
            df = self.client.get_limit_list(trade_date=trade_date)
            if df is None or df.empty:
                cached = self.cache.get_limit_list(trade_date)
                if cached:
                    return _format_limit_stats(cached, trade_date)
                return _empty_limit_stats(trade_date)

            self.cache.upsert_limit_list(df, trade_date)
            cached = self.cache.get_limit_list(trade_date)
            return _format_limit_stats(cached, trade_date)
        except Exception as e:
            logger.error(f"Error fetching limit list: {e}")
            cached = self.cache.get_limit_list(trade_date)
            if cached:
                return _format_limit_stats(cached, trade_date)
            return _empty_limit_stats(trade_date)

    def get_market_indices(self, trade_date: str = None) -> dict:
        """获取三大指数（上证指数、深证成指、创业板指）实时行情。"""
        if trade_date is None:
            trade_date = get_latest_trade_date(self.cache)

        # 四大指数代码
        indices = {
            "000001.SH": "上证指数",
            "399001.SZ": "深证成指",
            "399006.SZ": "创业板指",
            "000688.SH": "科创50",
        }

        result = {}
        for ts_code, name in indices.items():
            # Try cache first
            cached = self.cache.get_index_daily(ts_code, trade_date)
            if cached:
                result[ts_code] = _format_index_data(cached, name)
                continue

            # Fetch from TuShare
            try:
                df = self.client.get_index_daily(ts_code=ts_code, start_date=trade_date, end_date=trade_date)
                if df is not None and not df.empty:
                    self.cache.upsert_index_daily(df, ts_code)
                    cached = self.cache.get_index_daily(ts_code, trade_date)
                    if cached:
                        result[ts_code] = _format_index_data(cached, name)
                    else:
                        result[ts_code] = _empty_index_data(name)
                else:
                    result[ts_code] = _empty_index_data(name)
            except Exception as e:
                logger.error(f"Error fetching index {ts_code}: {e}")
                result[ts_code] = _empty_index_data(name)

        return {
            "trade_date": trade_date,
            "indices": result,
        }

    def get_index_kline(self, ts_code: str, days: int = 30) -> dict:
        """获取指数最近N日K线数据（用于 Drawer 趋势图）。"""
        session = self.cache.Session()
        try:
            # 查询最近 N+10 个自然日以覆盖周末
            end_dt = datetime.now()
            start_dt = end_dt - timedelta(days=days * 2)  # 足够覆盖非交易日
            start_date = start_dt.strftime("%Y%m%d")
            end_date = end_dt.strftime("%Y%m%d")

            results = session.execute(text("""
                SELECT trade_date, ts_code, open, high, low, close,
                       pre_close, change, pct_chg, vol, amount
                FROM index_daily
                WHERE ts_code = :tc AND trade_date BETWEEN :sd AND :ed
                ORDER BY trade_date DESC
                LIMIT :days
            """), {"tc": ts_code, "sd": start_date, "ed": end_date, "days": days}).fetchall()

            data = [dict(r._mapping) for r in results]
            data.reverse()  # 按日期升序

            # 如果缓存数据不足，从 TuShare 获取
            if len(data) < days:
                try:
                    df = self.client.get_index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                    if df is not None and not df.empty:
                        self.cache.upsert_index_daily(df, ts_code)
                        # 重新查询
                        results = session.execute(text("""
                            SELECT trade_date, ts_code, open, high, low, close,
                                   pre_close, change, pct_chg, vol, amount
                            FROM index_daily
                            WHERE ts_code = :tc AND trade_date BETWEEN :sd AND :ed
                            ORDER BY trade_date DESC
                            LIMIT :days
                        """), {"tc": ts_code, "sd": start_date, "ed": end_date, "days": days}).fetchall()
                        data = [dict(r._mapping) for r in results]
                        data.reverse()
                except Exception as e:
                    logger.error(f"Error fetching index kline for {ts_code}: {e}")

            return {"ts_code": ts_code, "data": data}
        finally:
            session.close()


def _format_overview(data: dict, trade_date: str) -> dict:
    """Format market overview response.

    Total turnover = sum of buy amounts only (buy = sell in aggregate,
    counting both doubles the actual value).
    """
    total_turnover = (
        data.get("buy_sm_amount", 0)
        + data.get("buy_md_amount", 0)
        + data.get("buy_lg_amount", 0)
        + data.get("buy_elg_amount", 0)
    )
    return {
        "trade_date": trade_date,
        "main_net_inflow": data.get("net_mf_amount", 0),
        "total_turnover": total_turnover,
        "super_large_net": (
            data.get("buy_elg_amount", 0) - data.get("sell_elg_amount", 0)
        ),
        "large_net": (
            data.get("buy_lg_amount", 0) - data.get("sell_lg_amount", 0)
        ),
        "medium_net": (
            data.get("buy_md_amount", 0) - data.get("sell_md_amount", 0)
        ),
        "small_net": (
            data.get("buy_sm_amount", 0) - data.get("sell_sm_amount", 0)
        ),
        "main_net_vol": data.get("net_mf_vol", 0),
        "updated_at": data.get("updated_at", ""),
    }


def _empty_overview(trade_date: str) -> dict:
    return {
        "trade_date": trade_date,
        "main_net_inflow": 0,
        "total_turnover": 0,
        "super_large_net": 0,
        "large_net": 0,
        "medium_net": 0,
        "small_net": 0,
        "main_net_vol": 0,
        "updated_at": "",
    }


def _format_north_fund(today, yesterday, last_5_data, trade_date) -> dict:
    """Format north fund response with comparison."""
    today_nm = today.get("north_money", 0) if today else 0
    yesterday_nm = yesterday.get("north_money", 0) if yesterday else 0

    # Calculate 5-day average
    nm_values = [d.get("north_money", 0) for d in last_5_data if d.get("north_money")]
    avg_5day = sum(nm_values) / len(nm_values) if nm_values else 0

    vs_yesterday = today_nm - yesterday_nm if yesterday else 0
    vs_yesterday_pct = (vs_yesterday / abs(yesterday_nm) * 100) if yesterday and yesterday_nm != 0 else 0
    vs_5day_pct = ((today_nm - avg_5day) / abs(avg_5day) * 100) if avg_5day != 0 else 0

    return {
        "trade_date": trade_date,
        "hgt": today.get("hgt", 0) if today else 0,
        "sgt": today.get("sgt", 0) if today else 0,
        "ggt_ss": today.get("ggt_ss", 0) if today else 0,
        "ggt_sz": today.get("ggt_sz", 0) if today else 0,
        "north_money": today_nm,
        "yesterday_north_money": yesterday_nm,
        "vs_yesterday": vs_yesterday,
        "vs_yesterday_pct": round(vs_yesterday_pct, 2),
        "avg_5day": round(avg_5day, 2),
        "vs_5day_pct": round(vs_5day_pct, 2),
        "last_5_days": last_5_data,
    }


def _format_limit_stats(data: list, trade_date: str) -> dict:
    """Format limit list response."""
    up_list = [d for d in data if d.get("limit_type") == "U"]
    down_list = [d for d in data if d.get("limit_type") == "D"]

    def _format_item(item: dict) -> dict:
        # 时间格式转换 HHMMSS/HMMSS -> HH:MM:SS
        def fmt_time(t):
            if not t:
                return ""
            t = str(t).strip()
            if len(t) == 5:
                t = "0" + t
            if len(t) == 6:
                return f"{t[:2]}:{t[2:4]}:{t[4:6]}"
            return t

        first_time = fmt_time(item.get("first_time", ""))
        last_time = fmt_time(item.get("last_time", ""))
        return {
            "ts_code": item.get("ts_code", ""),
            "name": item.get("name", ""),
            "close": item.get("close", 0),
            "pct_chg": item.get("pct_chg", 0),
            "amount": item.get("amount", 0),
            "first_time": first_time,
            "open_times": item.get("open_times", 0),
            "limit_times": item.get("limit_times", 0),
        }

    return {
        "trade_date": trade_date,
        "up_count": len(up_list),
        "down_count": len(down_list),
        "up_list": [_format_item(d) for d in up_list],
        "down_list": [_format_item(d) for d in down_list],
    }


def _empty_limit_stats(trade_date: str) -> dict:
    return {
        "trade_date": trade_date,
        "up_count": 0,
        "down_count": 0,
        "up_list": [],
        "down_list": [],
    }


def _format_index_data(data: dict, name: str) -> dict:
    """Format index daily data."""
    # vol 单位是手（100股），amount 单位是元
    vol = data.get("vol", 0)
    amount = data.get("amount", 0)
    return {
        "ts_code": data.get("ts_code", ""),
        "name": name,
        "close": data.get("close", 0),
        "change": data.get("change", 0),
        "pct_chg": data.get("pct_chg", 0),
        "vol": vol,  # 手
        "amount": amount,  # 元
        "trade_date": data.get("trade_date", ""),
    }


def _empty_index_data(name: str) -> dict:
    """Return empty index data."""
    return {
        "ts_code": "",
        "name": name,
        "close": 0,
        "change": 0,
        "pct_chg": 0,
        "vol": 0,
        "amount": 0,
        "trade_date": "",
    }
