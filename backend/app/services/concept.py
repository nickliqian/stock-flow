# [修改] 问题1+6：使用 BaseService 基类，共享全局单例 TuShareClient 和 CacheService
"""Concept Board Tracking Service."""

import logging
from .base import BaseService
from ..utils import get_latest_trade_date

logger = logging.getLogger(__name__)


class ConceptService(BaseService):
    """Service for concept board tracking."""

    def list_concepts(self, page: int = 1, page_size: int = 20,
                      sort_by: str = "pct_change", sort_order: str = "desc",
                      name: str = None) -> dict:
        """Get concept board list with latest daily data.

        Returns:
            {total, page, page_size, data: [{ts_code, name, exchange, close,
             pct_change, vol, turnover_rate, member_count}]}
        """
        # Get all ths_index records
        all_index = self.cache.get_all_ths_index()
        if not all_index:
            # Try to fetch from TuShare
            self._ensure_ths_index()
            all_index = self.cache.get_all_ths_index()

        # Filter to concept type only (exchange contains 'I' for index)
        concepts = [
            idx for idx in all_index
            if idx.get("index_type") in ("概念", "概念指数")
        ]

        # Get latest sector_daily for each concept
        trade_date = get_latest_trade_date(self.cache)
        daily_map = self._get_latest_sector_daily_batch(
            [c["ts_code"] for c in concepts], trade_date
        )

        # Get member counts
        member_map = self._get_member_counts()

        # Merge daily data into concepts
        result = []
        for concept in concepts:
            tc = concept.get("ts_code", "")
            daily = daily_map.get(tc, {})
            member_count = member_map.get(tc, 0)
            result.append({
                "ts_code": tc,
                "name": concept.get("name", ""),
                "exchange": concept.get("exchange", ""),
                "close": round(daily.get("close", 0) or 0, 2),
                "pct_change": round(daily.get("pct_change", 0) or 0, 2),
                "vol": round(daily.get("vol", 0) or 0, 2),
                "turnover_rate": round(daily.get("turnover_rate", 0) or 0, 2),
                "member_count": member_count,
            })

        # Filter by name
        if name:
            name_upper = name.strip().upper()
            result = [
                c for c in result
                if name_upper in (c.get("name") or "").upper()
                or name_upper in (c.get("ts_code") or "").upper()
            ]

        # Sort
        reverse = sort_order.lower() != "asc"
        sort_field = sort_by if sort_by in ("pct_change", "close", "vol", "turnover_rate", "member_count", "name") else "pct_change"
        try:
            result.sort(key=lambda x: x.get(sort_field, 0) or 0, reverse=reverse)
        except (TypeError, KeyError):
            pass

        # Paginate
        total = len(result)
        start = (page - 1) * page_size
        end = start + page_size
        page_data = result[start:end]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "data": page_data,
        }

    def get_concept_detail(self, ts_code: str) -> dict:
        """Get concept detail with recent 10-day daily data.

        Returns:
            {info: {ts_code, name, exchange, ...}, daily: [{trade_date, close, pct_change, ...}]}
        """
        # Get concept info from ths_index
        all_index = self.cache.get_all_ths_index()
        info = None
        for idx in all_index:
            if idx.get("ts_code") == ts_code:
                info = idx
                break

        if not info:
            return {"info": None, "daily": []}

        # Get recent daily data
        daily = self.cache.get_sector_daily(ts_code, days=10)

        return {
            "info": info,
            "daily": daily,
        }

    def get_concept_members(self, ts_code: str) -> dict:
        """Get concept member stocks with fundamental data.

        Returns:
            {members: [{ts_code, name, industry, close, pe_ttm, pb, total_mv, net_amount}]}
        """
        members = self.cache.get_sector_members(ts_code)
        if not members:
            return {"members": []}

        # Get latest trade date
        trade_date = get_latest_trade_date(self.cache)

        # Enrich with daily_basic data — batch query to avoid N+1
        member_codes = [m.get("member_code", "") for m in members]
        basic_map = {}
        if trade_date and member_codes:
            session = self.cache.Session()
            try:
                from sqlalchemy import text
                placeholders = ", ".join(f":tc{i}" for i in range(len(member_codes)))
                params = {"td": trade_date}
                for i, code in enumerate(member_codes):
                    params[f"tc{i}"] = code
                rows = session.execute(
                    text(f"SELECT * FROM daily_basic WHERE trade_date = :td AND ts_code IN ({placeholders})"),
                    params,
                ).fetchall()
                for row in rows:
                    basic_map[row.ts_code] = dict(row._mapping)
            finally:
                session.close()

        enriched = []
        for member in members:
            mc = member.get("member_code", "")
            basic = basic_map.get(mc)
            enriched.append({
                "ts_code": mc,
                "name": member.get("member_name", ""),
                "industry": "",
                "close": round(basic.get("close", 0) or 0, 2) if basic else 0,
                "pe_ttm": round(basic.get("pe_ttm", 0) or 0, 2) if basic else 0,
                "pb": round(basic.get("pb", 0) or 0, 2) if basic else 0,
                "total_mv": round(basic.get("total_mv", 0) or 0, 2) if basic else 0,
                "net_amount": 0,
            })

        return {"members": enriched}

    def _ensure_ths_index(self):
        """Fetch ths_index from TuShare if not cached."""
        try:
            df = self.client.get_ths_index()
            if df is not None and not df.empty:
                self.cache.upsert_ths_index(df)
                logger.info(f"Cached {len(df)} ths_index records")
        except Exception as e:
            logger.error(f"Error fetching ths_index: {e}")

    def _get_latest_sector_daily_batch(self, ts_codes: list, trade_date: str) -> dict:
        """Get latest sector_daily for a batch of ts_codes using a single SQL query."""
        if not ts_codes:
            return {}
        return self.cache.get_sector_daily_batch(ts_codes, trade_date)

    def _get_member_counts(self) -> dict:
        """Get member count for each sector."""
        session = self.cache.Session()
        try:
            from sqlalchemy import text
            results = session.execute(
                text("SELECT sector_code, COUNT(*) as cnt FROM sector_member GROUP BY sector_code")
            ).fetchall()
            return {r[0]: r[1] for r in results}
        except Exception:
            return {}
        finally:
            session.close()
