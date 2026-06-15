"""Seed script: Load stock_basic and sector members into the database."""

import sys
import os
import logging

# Add parent to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models import init_db
from app.cache import CacheService
from app.clients.tushare import TuShareClient
from app.config import TUSHARE_TOKEN, TUSHARE_API_URL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def seed_stock_basic():
    """Load all listed stocks from TuShare into stock_basic table."""
    logger.info("Seeding stock_basic...")
    client = TuShareClient(TUSHARE_TOKEN, TUSHARE_API_URL)
    cache = CacheService()

    df = client.get_stock_basic(list_status="L")
    if df is None or df.empty:
        logger.error("Failed to fetch stock_basic from TuShare")
        return

    logger.info(f"Got {len(df)} stocks from TuShare")
    cache.upsert_stock_basic(df)
    logger.info("stock_basic seeded successfully")


def seed_sector_members():
    """Load ths_index and ths_member into the database."""
    logger.info("Seeding sector members...")
    client = TuShareClient(TUSHARE_TOKEN, TUSHARE_API_URL)
    cache = CacheService()

    # Get all ths_index
    index_df = client.get_ths_index()
    if index_df is None or index_df.empty:
        logger.error("Failed to fetch ths_index from TuShare")
        return

    logger.info(f"Got {len(index_df)} sector indices (industry + concept)")

    # Store ths_index
    cache.upsert_ths_index(index_df)

    # Get members for each index
    import pandas as pd
    import time

    all_members = []
    total = len(index_df)
    for i, (_, row) in enumerate(index_df.iterrows()):
        sector_code = row.get("ts_code", "")
        sector_name = row.get("name", "")
        if not sector_code:
            continue

        try:
            members_df = client.get_ths_member(sector_code)
            if members_df is not None and not members_df.empty:
                # Rename TuShare columns to match our schema
                members_df = members_df.rename(columns={
                    'con_code': 'member_code',
                    'con_name': 'member_name',
                })
                members_df["sector_code"] = sector_code
                members_df["sector_name"] = sector_name
                all_members.append(members_df)
                logger.info(f"[{i+1}/{total}] {sector_name}: {len(members_df)} members")
            else:
                logger.info(f"[{i+1}/{total}] {sector_name}: 0 members")
            # Rate limiting - 1 second between calls
            time.sleep(1)
        except Exception as e:
            logger.warning(f"[{i+1}/{total}] Error fetching members for {sector_code}: {e}")
            time.sleep(2)
            continue

    if all_members:
        combined = pd.concat(all_members, ignore_index=True)
        cache.upsert_sector_members(combined)
        logger.info(f"Total sector members seeded: {len(combined)}")
    else:
        logger.warning("No sector members loaded")


if __name__ == "__main__":
    init_db()

    action = sys.argv[1] if len(sys.argv) > 1 else "all"

    if action in ("basic", "all"):
        seed_stock_basic()
    if action in ("sectors", "all"):
        seed_sector_members()
    if action not in ("basic", "sectors", "all"):
        print(f"Usage: python seed.py [basic|sectors|all]")
        sys.exit(1)

    logger.info("Seeding complete!")
