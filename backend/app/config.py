import os
from pathlib import Path
from dotenv import load_dotenv

# Load TuShare token from ~/.secrets/tushare.env
_secrets_path = Path.home() / ".secrets" / "tushare.env"
if _secrets_path.exists():
    load_dotenv(_secrets_path)

TUSHARE_TOKEN: str = os.getenv("TUSHARE_TOKEN", "")
TUSHARE_API_URL: str = os.getenv("TUSHARE_API_URL", "http://124.222.60.121:8020/")

DB_PATH: str = os.getenv("DB_PATH", str(Path(__file__).parent.parent / "data" / "cache.db"))
CACHE_DB_URL: str = f"sqlite:///{DB_PATH}"

# Cache freshness durations (minutes)
FLOW_CACHE_MINUTES: int = 60       # moneyflow, moneyflow_dc, moneyflow_hsgt, top_list
SECTOR_MEMBER_CACHE_MINUTES: int = 24 * 60   # ths_member
STOCK_BASIC_CACHE_MINUTES: int = 7 * 24 * 60  # stock_basic
THS_INDEX_CACHE_MINUTES: int = 24 * 60        # ths_index
DAILY_PRICE_CACHE_MINUTES: int = 60           # daily_price
DAILY_BASIC_CACHE_MINUTES: int = 60           # daily_basic
INDEX_DAILY_CACHE_MINUTES: int = 60           # index_daily
STK_FACTOR_CACHE_MINUTES: int = 60            # stk_factor

# Scheduler
UPDATE_HOUR_START: int = 9
UPDATE_HOUR_END: int = 15
UPDATE_INTERVAL_MINUTES: int = 60
