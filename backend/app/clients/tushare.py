import tushare as ts
import pandas as pd
import logging
import time
import threading
from collections import deque
from typing import Optional

logger = logging.getLogger(__name__)

# 全局限流器：每分钟最多 60 次请求
_rate_lock = threading.Lock()
_request_timestamps: deque = deque()
MAX_REQUESTS_PER_MINUTE = 60


def _rate_limit():
    """全局请求限流：每分钟最多 60 次。"""
    with _rate_lock:
        now = time.time()
        # 清理 60 秒前的时间戳
        while _request_timestamps and _request_timestamps[0] < now - 60:
            _request_timestamps.popleft()
        if len(_request_timestamps) >= MAX_REQUESTS_PER_MINUTE:
            wait_time = _request_timestamps[0] + 60 - now
            if wait_time > 0:
                logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                # sleep 后重新清理并更新 now
                now = time.time()
                while _request_timestamps and _request_timestamps[0] < now - 60:
                    _request_timestamps.popleft()
        _request_timestamps.append(time.time())


class TuShareClient:
    """Wraps TuShare API with error handling and retry logic."""

    def __init__(self, token: str, api_url: str):
        self.token = token
        self.api_url = api_url
        self.pro = ts.pro_api(token)
        # 注意：以下访问私有属性是临时方案，因为 TuShare 未提供公开方法设置自定义 API 端点。
        # 如果后续 TuShare 版本更新导致接口变化，此处需要同步调整。
        try:
            self.pro._DataApi__http_url = api_url
        except AttributeError as e:
            logger.warning(f"无法设置自定义 API 端点，将使用默认端点: {e}")
        logger.info(f"TuShareClient initialized with endpoint: {api_url}")

    def _call_with_retry(self, func, max_retries: int = 5, delay: float = 2.0, **kwargs) -> pd.DataFrame:
        """Call a TuShare function with retry logic.

        - 最多重试 5 次
        - 指数退避：2s, 4s, 6s, 8s
        - 全局限流（60次/分钟）在请求前执行，成功时不额外等待
        """
        for attempt in range(max_retries):
            # 全局限流
            _rate_limit()
            try:
                result = func(**kwargs)
                if result is None:
                    return pd.DataFrame()
                return result
            except Exception as e:
                logger.warning(f"TuShare API call failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    # 指数退避：delay * (attempt + 1)
                    wait = delay * (attempt + 1)
                    logger.info(f"Retrying in {wait}s...")
                    time.sleep(wait)
                else:
                    logger.error(f"TuShare API call failed after {max_retries} attempts: {e}")
                    return pd.DataFrame()

    def get_moneyflow(self, ts_code: Optional[str] = None, trade_date: Optional[str] = None,
                      start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """获取个股资金流向.
        Fields: ts_code, trade_date, buy_sm_vol, buy_sm_amount, sell_sm_vol, sell_sm_amount,
                buy_md_vol, buy_md_amount, sell_md_vol, sell_md_amount,
                buy_lg_vol, buy_lg_amount, sell_lg_vol, sell_lg_amount,
                buy_elg_vol, buy_elg_amount, sell_elg_vol, sell_elg_amount,
                net_mf_vol, net_mf_amount

        支持 date range 模式：同时传入 start_date + end_date 可一次获取多日数据。
        """
        kwargs = {}
        if ts_code:
            kwargs["ts_code"] = ts_code
        if trade_date:
            kwargs["trade_date"] = trade_date
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date
        logger.info(f"Fetching moneyflow: {kwargs}")
        return self._call_with_retry(self.pro.moneyflow, **kwargs)

    def get_moneyflow_hsgt(self, trade_date: Optional[str] = None) -> pd.DataFrame:
        """获取沪深港通资金流向.
        Fields: trade_date, ggt_ss, ggt_sz, hgt, sgt, north_money
        """
        kwargs = {}
        if trade_date:
            kwargs["trade_date"] = trade_date
        logger.info(f"Fetching moneyflow_hsgt: {kwargs}")
        return self._call_with_retry(self.pro.moneyflow_hsgt, **kwargs)

    def get_top_list(self, trade_date: Optional[str] = None) -> pd.DataFrame:
        """获取龙虎榜数据.
        Fields: trade_date, ts_code, name, close, pct_change, turnover_rate,
                amount, net_rate, reason
        """
        kwargs = {}
        if trade_date:
            kwargs["trade_date"] = trade_date
        logger.info(f"Fetching top_list: {kwargs}")
        return self._call_with_retry(self.pro.top_list, **kwargs)

    def get_ths_index(self) -> pd.DataFrame:
        """获取同花顺概念和行业指数列表.
        Fields: ts_code, name, exchange, index_type
        """
        logger.info("Fetching ths_index")
        return self._call_with_retry(self.pro.ths_index)

    def get_ths_member(self, ts_code: str) -> pd.DataFrame:
        """获取同花顺指数成分股.
        Fields: ts_code, con_code, con_name, is_new
        """
        logger.info(f"Fetching ths_member for: {ts_code}")
        return self._call_with_retry(self.pro.ths_member, ts_code=ts_code)

    def get_moneyflow_dc(self, trade_date: Optional[str] = None) -> pd.DataFrame:
        """获取东财资金流向.
        Fields: ts_code, trade_date, close, pct_change,
                net_amount, net_amount_rate,
                buy_elg_amount, buy_elg_amount_rate,
                buy_lg_amount, buy_lg_amount_rate,
                buy_md_amount, buy_md_amount_rate,
                buy_sm_amount, buy_sm_amount_rate
        """
        kwargs = {}
        if trade_date:
            kwargs["trade_date"] = trade_date
        logger.info(f"Fetching moneyflow_dc: {kwargs}")
        return self._call_with_retry(self.pro.moneyflow_dc, **kwargs)

    def get_stock_basic(self, list_status: str = "L") -> pd.DataFrame:
        """获取股票基础信息.
        Fields: ts_code, symbol, name, area, industry, list_date, ...
        """
        logger.info(f"Fetching stock_basic: list_status={list_status}")
        return self._call_with_retry(self.pro.stock_basic, list_status=list_status,
                                     fields="ts_code,symbol,name,industry,list_date")

    def get_ths_daily(self, ts_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """获取同花顺板块/概念指数日线行情.
        Fields: ts_code, trade_date, close, open, high, low, pre_close, avg_price,
                change, pct_change, vol, turnover_rate
        """
        kwargs = {"ts_code": ts_code}
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date
        logger.info(f"Fetching ths_daily: {kwargs}")
        return self._call_with_retry(self.pro.ths_daily, **kwargs)

    def get_daily(self, ts_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """获取日线行情数据.
        Fields: ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount
        """
        kwargs = {"ts_code": ts_code}
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date
        logger.info(f"Fetching daily: {kwargs}")
        return self._call_with_retry(self.pro.daily, **kwargs)

    def get_daily_basic(self, ts_code: str, trade_date: str = None) -> pd.DataFrame:
        """获取个股每日基本面指标.
        Fields: ts_code, trade_date, close, turnover_rate, turnover_rate_f, volume_ratio,
                pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm, total_share, float_share,
                free_share, total_mv, circ_mv
        """
        kwargs = {"ts_code": ts_code}
        if trade_date:
            kwargs["trade_date"] = trade_date
        logger.info(f"Fetching daily_basic: {kwargs}")
        return self._call_with_retry(self.pro.daily_basic, **kwargs)

    def get_all_daily_basic(self, trade_date: str) -> pd.DataFrame:
        """Fetch daily_basic for ALL stocks on a given trade date."""
        try:
            df = self._call_with_retry(
                self.pro.daily_basic,
                trade_date=trade_date,
                fields='ts_code,trade_date,close,turnover_rate,turnover_rate_f,volume_ratio,pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,total_share,float_share,free_share,total_mv,circ_mv'
            )
            return df if df is not None else pd.DataFrame()
        except Exception as e:
            logger.error(f"Error fetching all daily_basic: {e}")
            return pd.DataFrame()

    def get_limit_list(self, trade_date: str) -> pd.DataFrame:
        """获取涨跌停列表.
        Fields: trade_date, ts_code, industry, name, close, pct_chg, amount,
                float_mv, total_mv, turnover_ratio, first_time, last_time,
                open_times, up_stat, limit_times, limit
        """
        kwargs = {"trade_date": trade_date}
        logger.info(f"Fetching limit_list: {kwargs}")
        return self._call_with_retry(self.pro.limit_list_d, **kwargs)

    def get_index_daily(self, ts_code: str, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """获取指数日线行情.
        Fields: ts_code, trade_date, close, open, high, low, pre_close,
                change, pct_chg, vol, amount
        """
        kwargs = {"ts_code": ts_code}
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date
        logger.info(f"Fetching index_daily: {kwargs}")
        return self._call_with_retry(self.pro.index_daily, **kwargs)

    def get_stk_factor(self, trade_date: str) -> pd.DataFrame:
        """获取个股技术指标因子.
        Fields: ts_code, trade_date, close, open, high, low, pre_close, change, pct_change,
                vol, amount, adj_factor, open_hfq, open_qfq, close_hfq, close_qfq,
                high_hfq, high_qfq, low_hfq, low_qfq, pre_close_hfq, pre_close_qfq,
                macd_dif, macd_dea, macd, kdj_k, kdj_d, kdj_j,
                rsi_6, rsi_12, rsi_24, boll_upper, boll_mid, boll_lower, cci
        """
        logger.info(f"Fetching stk_factor: trade_date={trade_date}")
        return self._call_with_retry(
            self.pro.stk_factor,
            trade_date=trade_date,
            fields='ts_code,trade_date,close,open,high,low,pre_close,change,pct_change,vol,amount,adj_factor,macd_dif,macd_dea,macd,kdj_k,kdj_d,kdj_j,rsi_6,rsi_12,rsi_24,boll_upper,boll_mid,boll_lower,cci'
        )

    def get_stk_holdertrade(self, ts_code: str = None, start_date: str = None,
                            end_date: str = None) -> pd.DataFrame:
        """获取股东增减持数据.
        Fields: ts_code, ann_date, end_date, holder_name, hold_type, change_type,
                change_shares, change_ratio, after_shares, after_ratio,
                avg_price, change_reason
        """
        kwargs = {}
        if ts_code:
            kwargs["ts_code"] = ts_code
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date
        logger.info(f"Fetching stk_holdertrade: {kwargs}")
        return self._call_with_retry(self.pro.stk_holdertrade, **kwargs)

    def get_stk_holdernumber(self, ts_code: str = None, start_date: str = None,
                          end_date: str = None) -> pd.DataFrame:
        """获取股东人数变动数据.
        Fields: ts_code, ann_date, end_date, holder_num
        """
        kwargs = {}
        if ts_code:
            kwargs["ts_code"] = ts_code
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date
        logger.info(f"Fetching stk_holdernumber: {kwargs}")
        return self._call_with_retry(self.pro.stk_holdernumber, **kwargs)

    def get_top10_holders(self, ts_code: str = None, end_date: str = None) -> pd.DataFrame:
        """获取前十大股东数据.
        Fields: ts_code, ann_date, end_date, holder_name, hold_amount,
                hold_ratio, hold_floating_ratio, holder_type
        """
        kwargs = {}
        if ts_code:
            kwargs["ts_code"] = ts_code
        if end_date:
            kwargs["end_date"] = end_date
        logger.info(f"Fetching top10_holders: {kwargs}")
        return self._call_with_retry(self.pro.top10_holders, **kwargs)
