"""通用工具函数。"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def make_lazy(factory: Callable[[], T]) -> Callable[[], T]:
    """修复：提取共享的延迟初始化工厂函数。

    返回一个 getter 函数，首次调用时执行 factory() 创建单例并缓存，
    后续调用直接返回缓存实例。避免在模块导入时创建重量级对象。

    此前 strategy.py 和 alpha.py 各自定义了完全相同的 _make_lazy，
    违反 DRY 原则，现统一提取到 utils.py 共享模块。
    """
    _cache = [None]

    def getter() -> T:
        if _cache[0] is None:
            _cache[0] = factory()
        return _cache[0]

    return getter

# ---------------------------------------------------------------------------
# 中国法定节假日列表（硬编码 fallback：2024-2026年）
# 格式：(年, 月, 日) — 从 scheduler.py 迁移至此，避免循环导入
# ---------------------------------------------------------------------------
_HOLIDAYS_FALLBACK = {
    # 2024年
    (2024, 1, 1),    # 元旦
    (2024, 2, 10), (2024, 2, 11), (2024, 2, 12), (2024, 2, 13), (2024, 2, 14), (2024, 2, 15), (2024, 2, 16), (2024, 2, 17),  # 春节
    (2024, 4, 4), (2024, 4, 5), (2024, 4, 6),  # 清明节
    (2024, 5, 1), (2024, 5, 2), (2024, 5, 3), (2024, 5, 4), (2024, 5, 5),  # 劳动节
    (2024, 6, 8), (2024, 6, 9), (2024, 6, 10),  # 端午节
    (2024, 9, 15), (2024, 9, 16), (2024, 9, 17),  # 中秋节
    (2024, 10, 1), (2024, 10, 2), (2024, 10, 3), (2024, 10, 4), (2024, 10, 5), (2024, 10, 6), (2024, 10, 7),  # 国庆节
    # 2025年（基于国务院办公厅已公布安排）
    (2025, 1, 1),  # 元旦
    (2025, 1, 28), (2025, 1, 29), (2025, 1, 30), (2025, 1, 31), (2025, 2, 1), (2025, 2, 2), (2025, 2, 3), (2025, 2, 4),  # 春节
    (2025, 4, 4), (2025, 4, 5), (2025, 4, 6),  # 清明节
    (2025, 5, 1), (2025, 5, 2), (2025, 5, 3), (2025, 5, 4), (2025, 5, 5),  # 劳动节
    (2025, 5, 31), (2025, 6, 1), (2025, 6, 2),  # 端午节
    (2025, 10, 1), (2025, 10, 2), (2025, 10, 3), (2025, 10, 4), (2025, 10, 5), (2025, 10, 6), (2025, 10, 7),  # 国庆节
    (2025, 10, 8),  # 国庆节+中秋
    # 2026年（基于国务院办公厅已公布安排，待正式公布后需更新）
    (2026, 1, 1), (2026, 1, 2), (2026, 1, 3),  # 元旦
    (2026, 2, 17), (2026, 2, 18), (2026, 2, 19), (2026, 2, 20), (2026, 2, 21), (2026, 2, 22), (2026, 2, 23),  # 春节
    (2026, 4, 5), (2026, 4, 6), (2026, 4, 7),  # 清明节
    (2026, 5, 1), (2026, 5, 2), (2026, 5, 3),  # 劳动节
    (2026, 6, 19), (2026, 6, 20), (2026, 6, 21),  # 端午节
    (2026, 10, 1), (2026, 10, 2), (2026, 10, 3), (2026, 10, 4), (2026, 10, 5), (2026, 10, 6), (2026, 10, 7),  # 国庆节
}


def _fetch_holidays_from_tushare() -> set:
    """从 TuShare API 动态获取中国节假日数据。"""
    try:
        import tushare as ts
        from .config import TUSHARE_TOKEN
        pro = ts.pro_api(TUSHARE_TOKEN)
        today = datetime.now()
        start = f"{today.year - 1}0101"
        end = f"{today.year + 1}1231"
        df = pro.trade_cal(exchange="SSE", start_date=start, end_date=end, is_open="0")
        if df is not None and not df.empty:
            holidays = set()
            for _, row in df.iterrows():
                cal_date = str(row["cal_date"])
                holidays.add((int(cal_date[:4]), int(cal_date[4:6]), int(cal_date[6:8])))
            logger.info(f"Fetched {len(holidays)} holidays from TuShare")
            return holidays
    except Exception as e:
        logger.warning(f"Failed to fetch holidays from TuShare: {e}")
    return set()


def _load_holidays() -> set:
    """加载节假日数据：优先 TuShare API，失败则回退到硬编码。"""
    holidays = _fetch_holidays_from_tushare()
    if holidays:
        return holidays
    logger.info("Using hardcoded holiday fallback")
    return _HOLIDAYS_FALLBACK


# 惰性加载：首次调用 is_holiday() 时才加载节假日数据
_CHINESE_HOLIDAYS = None


def _get_holidays() -> set:
    """获取中国法定节假日集合（惰性加载）。"""
    global _CHINESE_HOLIDAYS
    if _CHINESE_HOLIDAYS is None:
        _CHINESE_HOLIDAYS = _load_holidays()
    return _CHINESE_HOLIDAYS


CHINESE_HOLIDAYS = _HOLIDAYS_FALLBACK  # 默认使用 fallback，启动时不阻塞


def is_holiday(dt: datetime) -> bool:
    """判断给定日期是否为中国法定节假日。"""
    holidays = _get_holidays()
    return (dt.year, dt.month, dt.day) in holidays


def get_latest_trade_date(cache) -> str:
    """获取数据库中最新的交易日期。

    优先从 market_flow 表获取，如果为空则返回最近的交易日（跳过周末和法定节假日）。
    """
    session = cache.Session()
    try:
        result = session.execute(text(
            "SELECT MAX(trade_date) FROM market_flow"
        )).fetchone()
        if result and result[0]:
            return result[0]
    except Exception:
        pass
    finally:
        session.close()
    # 数据库为空时，回溯到最近的交易日
    dt = datetime.now()
    while dt.weekday() >= 5 or is_holiday(dt):
        dt -= timedelta(days=1)
    return dt.strftime("%Y%m%d")


def get_last_n_trade_dates(end_date: str, n: int = 10) -> list:
    """获取最近 N 个交易日（跳过周末和法定节假日），升序返回。"""
    dates = []
    dt = datetime.strptime(end_date, "%Y%m%d")
    while len(dates) < n:
        dt -= timedelta(days=1)
        if dt.weekday() < 5 and not is_holiday(dt):
            dates.append(dt.strftime("%Y%m%d"))
    return sorted(dates)


def aggregate_moneyflow(df: pd.DataFrame) -> dict:
    """将个股资金流向数据按日期聚合为单条汇总记录。"""
    numeric_cols = [
        "buy_sm_vol", "buy_sm_amount", "sell_sm_vol", "sell_sm_amount",
        "buy_md_vol", "buy_md_amount", "sell_md_vol", "sell_md_amount",
        "buy_lg_vol", "buy_lg_amount", "sell_lg_vol", "sell_lg_amount",
        "buy_elg_vol", "buy_elg_amount", "sell_elg_vol", "sell_elg_amount",
        "net_mf_vol", "net_mf_amount",
    ]
    agg = {}
    for col in numeric_cols:
        if col in df.columns:
            agg[col] = float(df[col].sum())
        else:
            agg[col] = 0.0
    if df.empty:
        agg["trade_date"] = ""
    else:
        agg["trade_date"] = df["trade_date"].iloc[0] if "trade_date" in df.columns else ""
    return agg


def net_flow(d: dict, buy_key: str, sell_key: str) -> float:
    """计算某档位的净流入金额。"""
    return round((d.get(buy_key, 0) or 0) - (d.get(sell_key, 0) or 0), 2)
