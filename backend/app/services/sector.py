# [修改] 问题1+6：使用 BaseService 基类，共享全局单例 TuShareClient 和 CacheService
import logging
from datetime import datetime
import pandas as pd

from .base import BaseService
from ..utils import get_latest_trade_date

logger = logging.getLogger(__name__)


class SectorService(BaseService):
    """Service for sector capital flow aggregation."""

    # [修改] 问题8：接受 sort_order 参数，传递给 cache 查询层
    def get_sectors(self, trade_date: str = None, page: int = 1, size: int = 20, sort_order: str = "desc", sort_by: str = "net_inflow") -> dict:
        """Get paginated sector flow list, sorted by net_inflow."""
        if trade_date is None:
            trade_date = get_latest_trade_date(self.cache)

        # Check if sector_flow data is fresh
        if not self.cache.is_fresh("sector_flow", trade_date):
            self._update_sector_flows(trade_date)

        return self.cache.get_sector_flows(trade_date, page, size, sort_order=sort_order, sort_by=sort_by)

    def search_sectors(self, query: str, trade_date: str = None) -> list:
        """Search sectors by name or code (fuzzy match)."""
        if trade_date is None:
            trade_date = get_latest_trade_date(self.cache)
        return self.cache.search_sectors(query, trade_date)

    def refresh_sectors(self, trade_date: str = None):
        """Force refresh sector flow data."""
        if trade_date is None:
            trade_date = get_latest_trade_date(self.cache)
        self._update_sector_flows(trade_date)

    def get_sector_members(self, sector_code: str, trade_date: str = None) -> dict:
        """Get sector member stocks with capital flow data.

        Args:
            sector_code: Sector code (e.g., '885338')
            trade_date: Trade date, defaults to latest trade date

        Returns:
            Dict with sector info and member list sorted by net_mf_amount DESC
        """
        if trade_date is None:
            trade_date = get_latest_trade_date(self.cache)

        # Get sector name from sector_flow (query directly for this sector)
        sector_name = ""
        session = self.cache.Session()
        try:
            from sqlalchemy import text
            result = session.execute(
                text("SELECT sector_name FROM sector_flow WHERE trade_date = :td AND sector_code = :sc LIMIT 1"),
                {"td": trade_date, "sc": sector_code}
            ).fetchone()
            if result:
                sector_name = result[0] or ""
        finally:
            session.close()

        # Get sector member records (single query for both sector_name and member_codes)
        member_records = self.cache.get_sector_members(sector_code)
        member_codes = [m["member_code"] for m in member_records] if member_records else []

        # If not found in sector_flow, try to get from sector_member
        if not sector_name and member_records:
            sector_name = member_records[0].get("sector_name", "")

        # Query only this sector's member stocks from moneyflow_dc (SQL-level filtering)
        if member_codes:
            # Check if moneyflow_dc data exists for this date; fetch from API if not
            cache_exists = self.cache.has_moneyflow_dc(trade_date)
            if not cache_exists:
                all_flows = self.client.get_moneyflow_dc(trade_date=trade_date)
                if all_flows is not None and not all_flows.empty:
                    self.cache.upsert_moneyflow_dc(all_flows, trade_date)

            # Use targeted SQL query for only this sector's member codes
            filtered_rows = self.cache.get_moneyflow_dc_by_codes(trade_date, member_codes)
            sector_flows = pd.DataFrame(filtered_rows) if filtered_rows else pd.DataFrame()
        else:
            sector_flows = pd.DataFrame()

        # Convert to list of dicts, sorted by net_mf_amount DESC
        members = []
        if not sector_flows.empty:
            # Sort by net amount (moneyflow_dc uses net_amount, moneyflow uses net_mf_amount)
            sort_col = "net_amount" if "net_amount" in sector_flows.columns else "net_mf_amount"
            if sort_col in sector_flows.columns:
                sector_flows = sector_flows.sort_values(sort_col, ascending=False)

            for _, row in sector_flows.iterrows():
                members.append({
                    "ts_code": str(row.get("ts_code", "")),
                    "member_name": str(row.get("name", "")),
                    "close": float(row.get("close", 0) or 0),
                    "pct_change": float(row.get("pct_change", 0) or 0),
                    "net_mf_amount": float(row.get(sort_col, 0) or 0),
                    "buy_sm_amount": float(row.get("buy_sm_amount", 0) or 0),
                    "sell_sm_amount": float(row.get("sell_sm_amount", 0) or 0),
                    "buy_md_amount": float(row.get("buy_md_amount", 0) or 0),
                    "sell_md_amount": float(row.get("sell_md_amount", 0) or 0),
                    "buy_lg_amount": float(row.get("buy_lg_amount", 0) or 0),
                    "sell_lg_amount": float(row.get("sell_lg_amount", 0) or 0),
                    "buy_elg_amount": float(row.get("buy_elg_amount", 0) or 0),
                    "sell_elg_amount": float(row.get("sell_elg_amount", 0) or 0),
                    "net_mf_vol": float(row.get("net_mf_vol", 0) or 0),
                    "turnover_rate": float(row.get("turnover_rate", 0) or 0),
                })

        return {
            "sector_code": sector_code,
            "sector_name": sector_name,
            "trade_date": trade_date,
            "members": members,
        }

    def get_sector_trend(self, sector_code: str, days: int = 30) -> dict:
        """Get multi-dimensional historical trend for a sector.

        Merges sector_flow (fund flow) data with sector_daily (price/volume) data.
        Returns combined data sorted by trade_date ASC.
        """
        # 1. Get existing sector_flow data (fund flow — may be sparse)
        flow_rows = self.cache.get_sector_trend(sector_code, days)
        flow_by_date = {r["trade_date"]: r for r in flow_rows}

        sector_name = ""
        if flow_rows:
            sector_name = flow_rows[0].get("sector_name", "")

        # 2. Fetch and cache sector_daily data (price/volume/turnover)
        # Determine the sector's ts_code (TuShare uses .TI suffix for THS indices)
        ts_code = sector_code if ".TI" in sector_code else f"{sector_code}.TI"

        # Check if we need to refresh sector_daily for the latest trade date
        latest_trade_date = get_latest_trade_date(self.cache)
        if not self.cache.is_fresh("sector_daily", latest_trade_date):
            self._update_sector_daily(ts_code)

        # 3. Get sector_daily records
        daily_rows = self.cache.get_sector_daily(ts_code, days)

        # If no daily data cached and no flow data, return empty
        if not daily_rows and not flow_rows:
            return {"sector_code": sector_code, "sector_name": sector_name, "data": []}

        # 4. Merge: start from daily data (usually more complete), overlay flow data
        daily_by_date = {r["trade_date"]: r for r in daily_rows}
        all_dates = sorted(set(list(flow_by_date.keys()) + list(daily_by_date.keys())))

        merged = []
        for date in all_dates:
            flow = flow_by_date.get(date, {})
            daily = daily_by_date.get(date, {})
            merged.append({
                "trade_date": date,
                # Fund flow data (may be None/missing)
                "net_inflow": flow.get("net_inflow"),
                "large_net": flow.get("large_net"),
                "large_pct": flow.get("large_pct"),
                # Price/volume data (may be None/missing)
                "close": daily.get("close"),
                "pct_change": daily.get("pct_change"),
                "vol": daily.get("vol"),
                "turnover_rate": daily.get("turnover_rate"),
                "open": daily.get("open"),
                "high": daily.get("high"),
                "low": daily.get("low"),
                "change": daily.get("change"),
            })

        return {
            "sector_code": sector_code,
            "sector_name": sector_name,
            "data": merged,
        }

    def _update_sector_daily(self, ts_code: str):
        """Fetch ths_daily data for a sector and cache it."""
        try:
            from datetime import datetime, timedelta
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")

            logger.info(f"Fetching ths_daily for {ts_code}: {start_date} - {end_date}")
            df = self.client.get_ths_daily(ts_code, start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                self.cache.upsert_sector_daily(df, ts_code)
                logger.info(f"Cached {len(df)} sector_daily records for {ts_code}")
            else:
                logger.warning(f"No ths_daily data for {ts_code}")
        except Exception as e:
            logger.error(f"Error updating sector_daily for {ts_code}: {e}", exc_info=True)

    def _update_sector_flows(self, trade_date: str):
        """Aggregate sector flows from moneyflow_dc + sector members."""
        logger.info(f"Updating sector flows for {trade_date}")

        try:
            # 1. Ensure sector members are loaded
            if not self.cache.is_fresh("sector_member"):
                self._load_sector_members()

            # 2. Get all sector members mapping
            sector_map = self.cache.get_all_sector_members()
            if not sector_map:
                logger.warning("No sector members found. Run seed.py first.")
                return

            # 3. Fetch all market moneyflow_dc data
            all_flows = self.client.get_moneyflow_dc(trade_date=trade_date)
            if all_flows is None or all_flows.empty:
                logger.warning(f"No moneyflow_dc data for {trade_date}")
                return

            # 4. Build reverse mapping: ts_code -> (sector_code, sector_name) for single-pass aggregation
            stock_to_sector = {}
            for sc, info in sector_map.items():
                for mc in info["members"]:
                    stock_to_sector[mc] = (sc, info["name"])

            # 5. Single-pass: assign each flow to its sector via vectorized map, then groupby
            all_flows["_sector_code"] = all_flows["ts_code"].map(
                lambda x: stock_to_sector.get(x, (None, None))[0]
            )
            all_flows["_sector_name"] = all_flows["ts_code"].map(
                lambda x: stock_to_sector.get(x, (None, None))[1]
            )
            sector_flows = all_flows[all_flows["_sector_code"].notna()]

            if sector_flows.empty:
                logger.warning("No sector-matched flows found")
                return

            flow_col = "net_amount" if "net_amount" in sector_flows.columns else "net_mf_amount"
            sector_records = []
            for (sector_code, sector_name), group in sector_flows.groupby(["_sector_code", "_sector_name"]):
                net_inflow = float(group[flow_col].sum()) if flow_col in group.columns else 0

                if "buy_lg_amount" in group.columns and "sell_lg_amount" in group.columns:
                    large_net = float((group["buy_lg_amount"] - group["sell_lg_amount"]).sum())
                elif "buy_lg_amount" in group.columns:
                    large_net = float(group["buy_lg_amount"].sum())
                else:
                    large_net = 0

                total_abs = float(group[flow_col].abs().sum()) if flow_col in group.columns else 0
                large_pct = (large_net / total_abs * 100) if total_abs > 0 else 0

                lead_stock = ""
                lead_stock_name = ""
                lead_chg = 0
                if flow_col in group.columns and not group.empty:
                    try:
                        valid_flow = group[flow_col].dropna()
                        if not valid_flow.empty:
                            max_idx = valid_flow.idxmax()
                            lead_stock = str(group.loc[max_idx, "ts_code"])
                            if "pct_change" in group.columns:
                                lead_chg = float(group.loc[max_idx, "pct_change"])
                            if "name" in group.columns:
                                name_val = group.loc[max_idx, "name"]
                                lead_stock_name = str(name_val) if pd.notna(name_val) else ""
                    except Exception:
                        pass

                sector_records.append({
                    "sector_code": sector_code,
                    "sector_name": sector_name,
                    "net_inflow": round(net_inflow, 2),
                    "large_net": round(large_net, 2),
                    "large_pct": round(large_pct, 2),
                    "lead_stock": lead_stock,
                    "lead_stock_name": lead_stock_name,
                    "lead_chg": round(lead_chg, 2),
                })

            # 6. Write aggregated results
            if sector_records:
                self.cache.upsert_sector_flows(sector_records, trade_date)
                logger.info(f"Updated {len(sector_records)} sector flows for {trade_date}")
            else:
                logger.warning("No sector records to update")

        except Exception as e:
            logger.error(f"Error updating sector flows: {e}", exc_info=True)

    def _load_sector_members(self):
        """Load all ths_index and ths_member data.

        当板块数量超过阈值时，使用缓存优先策略：只对已缓存的板块刷新成分股，
        避免数百个 API 调用导致的 N+1 问题。未缓存的板块按需加载（通过
        get_sector_members 单独触发）。
        """
        SECTOR_LOAD_THRESHOLD = 50
        logger.info("Loading sector members...")

        try:
            # Get all ths_index
            index_df = self.client.get_ths_index()
            if index_df is None or index_df.empty:
                logger.warning("No ths_index data")
                return

            # Store ths_index
            self.cache.upsert_ths_index(index_df)

            sector_count = len(index_df)

            # If total sectors exceed threshold, use cache-first strategy:
            # only refresh sectors that already have cached member data.
            existing_sector_map = self.cache.get_all_sector_members() if sector_count > SECTOR_LOAD_THRESHOLD else {}
            cached_sector_codes = set(existing_sector_map.keys()) if existing_sector_map else set()

            # Get members for each index
            all_members = []
            skipped = 0
            for _, row in index_df.iterrows():
                sector_code = row.get("ts_code", "")
                sector_name = row.get("name", "")
                if not sector_code:
                    continue

                # Cache-first: skip sectors without cached data when above threshold
                if sector_count > SECTOR_LOAD_THRESHOLD and sector_code not in cached_sector_codes:
                    skipped += 1
                    continue

                try:
                    members_df = self.client.get_ths_member(sector_code)
                    if members_df is not None and not members_df.empty:
                        # Rename TuShare columns to match our schema
                        members_df = members_df.rename(columns={
                            'con_code': 'member_code',
                            'con_name': 'member_name',
                        })
                        members_df["sector_code"] = sector_code
                        members_df["sector_name"] = sector_name
                        all_members.append(members_df)
                    # Rate limiting - use TuShare client's built-in rate limiter
                except Exception as e:
                    logger.warning(f"Error fetching members for {sector_code}: {e}")
                    continue

            if skipped:
                logger.info(f"Cache-first mode: skipped {skipped} uncached sectors "
                            f"(total {sector_count} > threshold {SECTOR_LOAD_THRESHOLD})")

            if all_members:
                combined = pd.concat(all_members, ignore_index=True)
                self.cache.upsert_sector_members(combined)
                logger.info(f"Loaded {len(combined)} sector members")
            else:
                logger.warning("No sector members loaded")

        except Exception as e:
            logger.error(f"Error loading sector members: {e}", exc_info=True)
