"""APScheduler-based data updater for stock flow data."""

import logging
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .config import UPDATE_HOUR_START, UPDATE_HOUR_END
from .services.market import MarketService
from .services.sector import SectorService
from .services.stock import StockService
from .utils import is_holiday

logger = logging.getLogger(__name__)


def is_trading_hours() -> bool:
    """Check if current time is within trading hours (9:15 - 15:05) + a buffer."""
    now = datetime.now()
    if now.weekday() >= 5:  # Saturday/Sunday
        return False
    if is_holiday(now):
        return False
    hour, minute = now.hour, now.minute
    # Trading hours: 9:15 to 15:05
    if hour == 9:
        return minute >= 15
    if 10 <= hour <= 14:
        return True
    if hour == 15:
        return minute <= 5
    return False


class DataScheduler:
    """Scheduled data updater using APScheduler."""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        # 延迟创建 service 实例，避免模块加载时就创建数据库连接
        self.market_service = None
        self.sector_service = None
        self.stock_service = None
        self._last_update_time = None

    def start(self):
        """Start the scheduler with hourly jobs."""
        # 在启动时才创建 service 实例，确保数据库已初始化
        if self.market_service is None:
            self.market_service = MarketService()
        if self.sector_service is None:
            self.sector_service = SectorService()
        if self.stock_service is None:
            self.stock_service = StockService()

        # Hourly update during trading hours (9:00 - 15:00, from config)
        self.scheduler.add_job(
            self._run_update,
            CronTrigger(minute=0, hour=f"{UPDATE_HOUR_START}-{UPDATE_HOUR_END}", day_of_week="mon-fri"),
            id="hourly_update",
            name="Hourly market data update",
            replace_existing=True,
        )

        # Post-close update at 15:05
        self.scheduler.add_job(
            self._run_update,
            CronTrigger(hour=15, minute=5, day_of_week="mon-fri"),
            id="post_close_update",
            name="Post-close market data update",
            replace_existing=True,
        )

        # 预缓存趋势数据：每小时30分钟时运行，确保 flow-trend/north/turnover 有缓存
        self.scheduler.add_job(
            self._precache_trends,
            CronTrigger(minute=30, hour=f"{UPDATE_HOUR_START}-{UPDATE_HOUR_END}", day_of_week="mon-fri"),
            id="precache_trends",
            name="Pre-cache trend data (30/60/90 days)",
            replace_existing=True,
        )

        self.scheduler.start()
        logger.info("DataScheduler started")

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("DataScheduler stopped")

    def _run_update(self):
        """The actual update job that runs on schedule."""
        if not is_trading_hours():
            logger.info("Skipping update: not trading hours")
            return

        trade_date = datetime.now().strftime("%Y%m%d")

        # Skip if updated too recently (within 5 minutes) to avoid rapid duplicate runs.
        # This still allows the 15:05 post-close update to run after a 15:00 hourly update
        # (5 min gap ≥ threshold), while preventing duplicate triggers in the same window.
        if self._last_update_time is not None:
            elapsed = (datetime.now() - self._last_update_time).total_seconds()
            if elapsed < 300:  # 5 minutes
                logger.info(f"Skipping update for {trade_date}: last update was {int(elapsed)}s ago")
                return

        logger.info(f"Starting scheduled update for {trade_date}")

        try:
            # 1. Update market flow
            logger.info("Updating market flow...")
            self.market_service.get_overview(trade_date)

            # 2. Update north fund
            logger.info("Updating north fund...")
            self.market_service.get_north_fund(trade_date)

            # 3. Update sector flows (includes moneyflow_dc fetch)
            logger.info("Updating sector flows...")
            self.sector_service.refresh_sectors(trade_date)

            # 4. Pre-cache limit list for today
            logger.info("Updating limit list...")
            self.market_service.get_limit_stats(trade_date)

            # 5. Pre-cache index daily for 4 indices
            logger.info("Updating index data...")
            self.market_service.get_market_indices(trade_date)

            self._last_update_time = datetime.now()
            logger.info(f"Scheduled update completed for {trade_date}")
        except Exception as e:
            logger.error(f"Error in scheduled update: {e}", exc_info=True)

    def _precache_trends(self):
        """预缓存趋势数据，确保 30/60/90 天的 flow-trend、north、turnover 数据可用。"""
        if not is_trading_hours():
            return

        trade_date = datetime.now().strftime("%Y%m%d")
        logger.info(f"Pre-caching trend data for {trade_date}")

        try:
            # 预缓存 flow-trend (90天)
            logger.info("Pre-caching flow-trend (90d)...")
            self.market_service.get_market_trend(days=90)

            # 预缓存 north fund trend (90天)
            logger.info("Pre-caching north fund trend (90d)...")
            self.market_service.get_fund_trend(days=90)

            # 预缓存 turnover trend (90天)
            logger.info("Pre-caching turnover trend (90d)...")
            self.market_service.get_turnover_trend(days=90)

            # 预缓存 index daily for all 4 indices (90天)
            for ts_code in ["000001.SH", "399001.SZ", "399006.SZ", "000688.SH"]:
                logger.info(f"Pre-caching index daily for {ts_code}...")
                try:
                    self.market_service.client.get_index_daily(
                        ts_code=ts_code,
                        start_date=(datetime.now() - timedelta(days=120)).strftime("%Y%m%d"),
                        end_date=trade_date,
                    )
                except Exception as e:
                    logger.warning(f"Failed to cache index daily for {ts_code}: {e}")

            logger.info("Trend pre-caching completed")
        except Exception as e:
            logger.error(f"Error in trend pre-caching: {e}", exc_info=True)
