"""Seed market_flow table with last 10 trading days of data.

Usage: python seed_market_flow.py
"""

import sys
import os
from datetime import datetime

# Ensure app package is importable
sys.path.insert(0, os.path.dirname(__file__))

from app.clients.tushare import TuShareClient
from app.cache import CacheService
from app.config import TUSHARE_TOKEN, TUSHARE_API_URL
from app.utils import get_last_n_trade_dates, aggregate_moneyflow
import pandas as pd
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    if not TUSHARE_TOKEN:
        logger.error("TUSHARE_TOKEN not set. Check ~/.secrets/tushare.env")
        sys.exit(1)

    client = TuShareClient(TUSHARE_TOKEN, TUSHARE_API_URL)
    cache = CacheService()

    # Use today as end date
    end_date = datetime.now().strftime("%Y%m%d")
    dates = get_last_n_trade_dates(end_date, 10)
    logger.info(f"Fetching market_flow for {len(dates)} dates: {dates[0]} ~ {dates[-1]}")

    success = 0
    skipped = 0
    failed = 0

    for d in dates:
        # Skip if already cached and fresh
        if cache.is_fresh("market_flow", d):
            logger.info(f"[{d}] Already cached, skipping")
            skipped += 1
            continue

        try:
            df = client.get_moneyflow(trade_date=d)
            if df is None or df.empty:
                logger.warning(f"[{d}] No data returned from TuShare")
                failed += 1
                continue

            agg = aggregate_moneyflow(df)
            agg_df = pd.DataFrame([agg])
            cache.upsert_market_flow(agg_df, d)
            logger.info(f"[{d}] OK — {len(df)} stocks aggregated, net_mf_amount={agg['net_mf_amount']:.2f}")
            success += 1
        except Exception as e:
            logger.error(f"[{d}] Failed: {e}")
            failed += 1

    logger.info(f"Done. success={success}, skipped={skipped}, failed={failed}")


if __name__ == "__main__":
    main()
