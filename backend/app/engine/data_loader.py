"""集中式数据加载器——为策略引擎获取并缓存所需数据。"""

import logging
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List

from ..clients.tushare import TuShareClient
from ..cache import CacheService
from ..utils import get_last_n_trade_dates

logger = logging.getLogger(__name__)


class StrategyDataLoader:
    """根据策略所需的 data_keys 一次性加载数据。"""

    def __init__(self, client: TuShareClient, cache: CacheService):
        self.client = client
        self.cache = cache

    # ------------------------------------------------------------------
    # public
    # ------------------------------------------------------------------
    def load(self, trade_date: str, data_keys: List[str]) -> Dict[str, pd.DataFrame]:
        """根据 data_keys 列表加载对应数据，返回 {key: DataFrame}。"""
        loaders = {
            "daily_basic": self._load_daily_basic,
            "moneyflow": self._load_moneyflow,
            "moneyflow_multi": self._load_moneyflow_multi,
            "stk_factor": self._load_stk_factor,
            "daily_multi": self._load_daily_multi,
            "limit_list_d": self._load_limit_list_d,
            "block_trade": self._load_block_trade,
            "daily": self._load_daily,
            "fina_indicator": self._load_fina_indicator,
            "margin_detail": self._load_margin_detail,
            "margin_detail_multi": self._load_margin_detail_multi,
            "stock_basic": self._load_stock_basic,
            "cyq_perf": self._load_cyq_perf,
            "pledge_stat": self._load_pledge_stat,
            "stk_holdertrade": self._load_stk_holdertrade,
            "stk_holdernumber": self._load_stk_holdernumber,
            "top10_holders": self._load_top10_holders,
            "pledge_stat_v2": self._load_pledge_stat_v2,
        }
        result: Dict[str, pd.DataFrame] = {}
        for key in data_keys:
            fn = loaders.get(key)
            if fn is None:
                logger.warning("StrategyDataLoader: unknown data key '%s', skipping", key)
                continue
            try:
                df = fn(trade_date)
                if df is not None and not df.empty:
                    result[key] = df
            except Exception as exc:
                logger.error("StrategyDataLoader: failed to load '%s': %s", key, exc)
        return result

    # ------------------------------------------------------------------
    # private loaders
    # ------------------------------------------------------------------
    def _load_daily_basic(self, trade_date: str) -> pd.DataFrame:
        """获取全市场 daily_basic，优先缓存。"""
        # 检查缓存
        if self.cache.is_fresh("daily_basic", trade_date):
            rows = self.cache.get_all_daily_basic(trade_date)
            if rows:
                return pd.DataFrame(rows)

        # 从 TuShare 拉取
        df = self.client.get_all_daily_basic(trade_date)
        if df is not None and not df.empty:
            try:
                self.cache.batch_upsert_daily_basic(df, trade_date)
            except Exception as exc:
                logger.warning("Failed to cache daily_basic: %s", exc)
        return df if df is not None else pd.DataFrame()

    def _load_moneyflow(self, trade_date: str) -> pd.DataFrame:
        """获取全市场 moneyflow（个股资金流向），始终从 TuShare 拉取。"""
        df = self.client.get_moneyflow(trade_date=trade_date)
        return df if df is not None else pd.DataFrame()

    def _load_moneyflow_multi(self, trade_date: str, days: int = 5) -> pd.DataFrame:
        """获取最近 N 个交易日的 moneyflow 合并数据。"""
        dates = get_last_n_trade_dates(trade_date, days)
        if not dates:
            return pd.DataFrame()
        start_date = dates[0]
        end_date = trade_date
        df = self.client.get_moneyflow(start_date=start_date, end_date=end_date)
        if df is not None and not df.empty:
            return df
        return pd.DataFrame()

    def _load_stk_factor(self, trade_date: str) -> pd.DataFrame:
        """获取全市场 stk_factor 技术指标，优先缓存。"""
        # 检查缓存
        if self.cache.is_fresh("stk_factor", trade_date):
            rows = self.cache.get_stk_factor_all(trade_date)
            if rows:
                return pd.DataFrame(rows)

        # 从 TuShare 拉取
        df = self.client.get_stk_factor(trade_date)
        if df is not None and not df.empty:
            try:
                self.cache.upsert_stk_factor(df, trade_date)
            except Exception as exc:
                logger.warning("Failed to cache stk_factor: %s", exc)
        return df if df is not None else pd.DataFrame()

    # [修改] 问题4：使用 self.client._call_with_retry() 而非直接调用 self.client.pro.daily()，
    # 确保请求经过重试逻辑和全局限流。
    def _load_daily_multi(self, trade_date: str, days: int = 20) -> pd.DataFrame:
        """获取最近 N 个交易日的全市场 daily OHLCV 数据，用于 MA 计算。

        使用 start_date + end_date 范围查询一次性获取多日数据，
        避免逐日调用 TuShare daily API 造成的性能瓶颈。
        """
        dates = get_last_n_trade_dates(trade_date, days)
        if not dates:
            return pd.DataFrame()
        start_date = dates[0]
        end_date = trade_date
        try:
            df = self.client._call_with_retry(
                self.client.pro.daily,
                start_date=start_date,
                end_date=end_date,
            )
            if df is not None and not df.empty:
                return df
        except Exception as exc:
            logger.warning("daily_multi: failed to load %s ~ %s: %s", start_date, end_date, exc)
        return pd.DataFrame()

    def _load_limit_list_d(self, trade_date: str) -> pd.DataFrame:
        """获取当日涨跌停列表。"""
        try:
            df = self.client._call_with_retry(
                self.client.pro.limit_list_d, trade_date=trade_date
            )
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.error("limit_list_d load failed: %s", exc)
            return pd.DataFrame()

    def _load_block_trade(self, trade_date: str) -> pd.DataFrame:
        """获取当日大宗交易数据。"""
        try:
            df = self.client._call_with_retry(
                self.client.pro.block_trade, trade_date=trade_date
            )
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.error("block_trade load failed: %s", exc)
            return pd.DataFrame()

    def _load_daily(self, trade_date: str) -> pd.DataFrame:
        """获取单日全市场 OHLCV（用于大宗交易溢价对比收盘价）。"""
        try:
            df = self.client._call_with_retry(
                self.client.pro.daily, trade_date=trade_date
            )
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.error("daily load failed: %s", exc)
            return pd.DataFrame()

    def _load_fina_indicator(self, trade_date: str) -> pd.DataFrame:
        """根据 trade_date 推断最新报告期，获取全市场财务指标。"""
        try:
            dt = datetime.strptime(trade_date, "%Y%m%d")
            month = dt.month
            year = dt.year
            if month <= 4:
                period = f"{year - 1}1231"
            elif month <= 8:
                period = f"{year}0331"
            elif month <= 10:
                period = f"{year}0630"
            else:
                period = f"{year}0930"

            df = self.client._call_with_retry(
                self.client.pro.fina_indicator, period=period
            )
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.error("fina_indicator load failed: %s", exc)
            return pd.DataFrame()

    def _load_margin_detail(self, trade_date: str) -> pd.DataFrame:
        """获取全市场融资融券明细。"""
        try:
            df = self.client._call_with_retry(
                self.client.pro.margin_detail, trade_date=trade_date
            )
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.error("margin_detail load failed: %s", exc)
            return pd.DataFrame()

    def _load_margin_detail_multi(self, trade_date: str, days: int = 5) -> pd.DataFrame:
        """获取最近 N 个交易日的 margin_detail 合并数据。

        使用 start_date + end_date 范围查询一次性获取多日数据，
        参考 _load_moneyflow_multi 的模式。
        TuShare margin_detail 接口支持 start_date/end_date 参数。
        """
        dates = get_last_n_trade_dates(trade_date, days)
        if not dates:
            return pd.DataFrame()
        start_date = dates[0]
        end_date = trade_date
        try:
            df = self.client._call_with_retry(
                self.client.pro.margin_detail,
                start_date=start_date,
                end_date=end_date,
            )
            if df is not None and not df.empty:
                return df
        except Exception as exc:
            logger.warning("margin_detail_multi: failed to load %s ~ %s: %s", start_date, end_date, exc)
        return pd.DataFrame()

    def _load_stock_basic(self, trade_date: str) -> pd.DataFrame:
        """获取股票基本信息（从数据库缓存读取）。"""
        try:
            from ..models import SessionLocal, StockBasic
            session = SessionLocal()
            try:
                rows = session.query(
                    StockBasic.ts_code, StockBasic.name, StockBasic.industry
                ).all()
                if rows:
                    return pd.DataFrame([{
                        "ts_code": r.ts_code, "name": r.name or "", "industry": r.industry or ""
                    } for r in rows])
            finally:
                session.close()
        except Exception as exc:
            logger.error("stock_basic load failed: %s", exc)
        return pd.DataFrame()

    def _load_cyq_perf(self, trade_date: str) -> pd.DataFrame:
        """获取全市场筹码分布性能指标（cyq_perf）。

        Fields: ts_code, trade_date, his_low, his_high, low_20stk, high_20stk,
                weight_avg, winner_pct, winner_num, cost_5pct, cost_15pct,
                cost_50pct, cost_85pct, cost_95pct, sum_pct_5_15, sum_pct_15_50,
                sum_pct_50_85, sum_pct_85_95, sum_pct_85_100, weight_avg_pct
        """
        try:
            df = self.client._call_with_retry(
                self.client.pro.cyq_perf, trade_date=trade_date
            )
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.error("cyq_perf load failed: %s", exc)
            return pd.DataFrame()

    def _load_pledge_stat(self, trade_date: str) -> pd.DataFrame:
        """获取全市场股权质押统计数据。

        Fields: ts_code, end_date, pledge_ratio, pledge_count, pledge_amount,
                unlimited_count, unlimited_amount, pledgor_count
        """
        try:
            df = self.client._call_with_retry(
                self.client.pro.pledge_stat, end_date=trade_date
            )
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.error("pledge_stat load failed: %s", exc)
            return pd.DataFrame()

    def _load_stk_holdertrade(self, trade_date: str) -> pd.DataFrame:
        """获取全市场股东增减持数据。"""
        try:
            from datetime import timedelta
            dt = datetime.strptime(trade_date, "%Y%m%d")
            start_date = (dt - timedelta(days=30)).strftime("%Y%m%d")
            df = self.client._call_with_retry(
                self.client.pro.stk_holdertrade,
                start_date=start_date,
                end_date=trade_date,
            )
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.error("stk_holdertrade load failed: %s", exc)
            return pd.DataFrame()

    def _load_stk_holdernumber(self, trade_date: str) -> pd.DataFrame:
        """获取全市场股东人数变动数据。"""
        try:
            from datetime import timedelta
            dt = datetime.strptime(trade_date, "%Y%m%d")
            start_date = (dt - timedelta(days=90)).strftime("%Y%m%d")
            df = self.client._call_with_retry(
                self.client.pro.stk_holdernumber,
                start_date=start_date,
                end_date=trade_date,
            )
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.error("stk_holdernumber load failed: %s", exc)
            return pd.DataFrame()

    def _load_top10_holders(self, trade_date: str) -> pd.DataFrame:
        """获取全市场前十大股东数据。"""
        try:
            df = self.client._call_with_retry(
                self.client.pro.top10_holders,
                end_date=trade_date,
            )
            return df if df is not None else pd.DataFrame()
        except Exception as exc:
            logger.error("top10_holders load failed: %s", exc)
            return pd.DataFrame()

    def _load_pledge_stat_v2(self, trade_date: str) -> pd.DataFrame:
        """获取全市场股权质押统计数据 (alias for new strategy)."""
        return self._load_pledge_stat(trade_date)
