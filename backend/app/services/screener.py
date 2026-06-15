# [修改] 问题1+6：使用 BaseService 基类，共享全局单例 TuShareClient 和 CacheService
"""Stock Screener Service — multi-dimensional stock filtering."""

import logging
from .base import BaseService
from ..utils import get_latest_trade_date

logger = logging.getLogger(__name__)


class ScreenerService(BaseService):
    """Service for multi-dimensional stock screening."""

    def screen_stocks(self, trade_date: str = None, filters: dict = None,
                      sort_by: str = "total_mv", sort_order: str = "desc",
                      page: int = 1, page_size: int = 50) -> dict:
        """Screen stocks with multi-dimensional filters.

        Args:
            trade_date: Trade date YYYYMMDD. None = latest.
            filters: Dict of filter conditions:
                pe_min, pe_max: PE(TTM) range
                pb_min, pb_max: PB range
                mv_min, mv_max: Total market cap (亿元) range
                circ_mv_min, circ_mv_max: Circulating market cap (亿元) range
                turnover_min, turnover_max: Turnover rate (%) range
                volume_ratio_min, volume_ratio_max: Volume ratio range
                dv_min, dv_max: Dividend yield (%) range
                net_inflow_min: Min net fund inflow (万元)
                name: Stock name contains
                industry: Industry equals
            sort_by: Sort field (close, pe_ttm, pb, total_mv, circ_mv,
                    turnover_rate, volume_ratio, dv_ttm, net_amount)
            sort_order: 'asc' or 'desc'
            page: Page number (1-based)
            page_size: Results per page
        """
        if trade_date is None:
            trade_date = get_latest_trade_date(self.cache)

        # Ensure daily_basic is cached for this trade date
        self._ensure_daily_basic(trade_date)

        # Get all daily_basic records with SQL-level filtering
        # (numeric filters pushed to SQL, net_inflow still in Python)
        result = self.cache.get_filtered_daily_basic(trade_date, filters)
        if not result:
            return {"total": 0, "page": page, "page_size": page_size, "data": []}

        # Get moneyflow_dc data for net fund flow (if available)
        moneyflow = {}
        try:
            mf_data = self.cache.get_moneyflow_dc(trade_date)
            for item in mf_data:
                moneyflow[item["ts_code"]] = item
        except Exception:
            pass

        # Merge moneyflow data into stocks
        for stock in result:
            tc = stock.get("ts_code", "")
            mf = moneyflow.get(tc, {})
            stock["net_amount"] = mf.get("net_amount", 0) or 0
            stock["net_amount_rate"] = mf.get("net_amount_rate", 0) or 0

        # Apply remaining Python-only filters (net_inflow_min)
        if filters:
            result = self._apply_python_filters(result, filters)

        # Sort
        reverse = sort_order.lower() != "asc"
        sort_field = self._normalize_sort_field(sort_by)
        try:
            result.sort(key=lambda x: x.get(sort_field, 0) or 0, reverse=reverse)
        except (TypeError, KeyError):
            pass

        # Paginate
        total = len(result)
        start = (page - 1) * page_size
        end = start + page_size
        page_data = result[start:end]

        # Format output
        formatted = []
        for stock in page_data:
            total_mv = stock.get("total_mv", 0) or 0
            circ_mv = stock.get("circ_mv", 0) or 0
            formatted.append({
                "ts_code": stock.get("ts_code", ""),
                "name": stock.get("name", ""),
                "industry": stock.get("industry", ""),
                "close": round(stock.get("close", 0) or 0, 2),
                "pe_ttm": round(stock.get("pe_ttm", 0) or 0, 2),
                "pb": round(stock.get("pb", 0) or 0, 2),
                "ps_ttm": round(stock.get("ps_ttm", 0) or 0, 2),
                "total_mv": round(total_mv, 2),
                "circ_mv": round(circ_mv, 2),
                "turnover_rate": round(stock.get("turnover_rate", 0) or 0, 2),
                "volume_ratio": round(stock.get("volume_ratio", 0) or 0, 2),
                "dv_ttm": round(stock.get("dv_ttm", 0) or 0, 2),
                "net_amount": round(stock.get("net_amount", 0) or 0, 2),
                "net_amount_rate": round(stock.get("net_amount_rate", 0) or 0, 2),
            })

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "trade_date": trade_date,
            "data": formatted,
        }

    def _ensure_daily_basic(self, trade_date: str):
        """Fetch daily_basic from TuShare if not enough cached data."""
        cached_count = self.cache.get_all_daily_basic_count(trade_date)
        if cached_count >= 3000:  # Most A-shares covered
            return

        logger.info(f"Fetching daily_basic for {trade_date} from TuShare (cached: {cached_count})")
        try:
            df = self.client.get_all_daily_basic(trade_date)
            if df is not None and not df.empty:
                self.cache.batch_upsert_daily_basic(df, trade_date)
                logger.info(f"Cached {len(df)} daily_basic records for {trade_date}")
        except Exception as e:
            logger.error(f"Error fetching batch daily_basic: {e}")

    def _apply_python_filters(self, stocks: list, filters: dict) -> list:
        """Apply Python-only filters (after SQL-level filtering).

        Only filters that require joined/multi-table data not available in SQL
        are kept here. Numeric filters on daily_basic are pushed to SQL.
        """
        result = stocks

        # Net fund inflow minimum (万元) — requires moneyflow data merged in Python
        nif_min = filters.get("net_inflow_min")
        if nif_min is not None:
            result = [s for s in result if (s.get("net_amount") or 0) >= float(nif_min)]

        return result

    def _normalize_sort_field(self, sort_by: str) -> str:
        """Map API sort field names to DB column names."""
        mapping = {
            "close": "close",
            "pe": "pe_ttm",
            "pe_ttm": "pe_ttm",
            "pb": "pb",
            "ps": "ps_ttm",
            "total_mv": "total_mv",
            "circ_mv": "circ_mv",
            "turnover_rate": "turnover_rate",
            "volume_ratio": "volume_ratio",
            "dv_ttm": "dv_ttm",
            "net_amount": "net_amount",
            "net_inflow": "net_amount",
            "name": "name",
        }
        return mapping.get(sort_by, sort_by)
