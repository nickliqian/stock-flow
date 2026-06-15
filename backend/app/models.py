import os
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, UniqueConstraint, Index, create_engine, event
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timezone
from .config import DB_PATH

Base = declarative_base()

# Lazy-initialized database objects — populated by init_db()
engine = None
SessionLocal = None


class MarketFlow(Base):
    __tablename__ = "market_flow"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(8), nullable=False)
    buy_sm_vol = Column(Float, default=0)
    buy_sm_amount = Column(Float, default=0)
    sell_sm_vol = Column(Float, default=0)
    sell_sm_amount = Column(Float, default=0)
    buy_md_vol = Column(Float, default=0)
    buy_md_amount = Column(Float, default=0)
    sell_md_vol = Column(Float, default=0)
    sell_md_amount = Column(Float, default=0)
    buy_lg_vol = Column(Float, default=0)
    buy_lg_amount = Column(Float, default=0)
    sell_lg_vol = Column(Float, default=0)
    sell_lg_amount = Column(Float, default=0)
    buy_elg_vol = Column(Float, default=0)
    buy_elg_amount = Column(Float, default=0)
    sell_elg_vol = Column(Float, default=0)
    sell_elg_amount = Column(Float, default=0)
    net_mf_vol = Column(Float, default=0)
    net_mf_amount = Column(Float, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("trade_date", name="uq_market_flow_date"),
        Index("ix_market_flow_date", "trade_date"),
    )


class NorthFundFlow(Base):
    __tablename__ = "north_fund_flow"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(8), nullable=False)
    ggt_ss = Column(Float, default=0)
    ggt_sz = Column(Float, default=0)
    hgt = Column(Float, default=0)
    sgt = Column(Float, default=0)
    north_money = Column(Float, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("trade_date", name="uq_north_fund_date"),
        Index("ix_north_fund_date", "trade_date"),
    )


class SectorFlow(Base):
    __tablename__ = "sector_flow"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(8), nullable=False)
    sector_code = Column(String(32), nullable=False)
    sector_name = Column(String(64), nullable=False)
    net_inflow = Column(Float, default=0)
    large_net = Column(Float, default=0)
    large_pct = Column(Float, default=0)
    lead_stock = Column(String(32), default="")
    lead_stock_name = Column(String(32), default="")
    lead_chg = Column(Float, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("trade_date", "sector_code", name="uq_sector_flow_date_code"),
        Index("ix_sector_flow_date", "trade_date"),
        Index("ix_sector_flow_net", "trade_date", "net_inflow"),
    )


class StockFlow(Base):
    __tablename__ = "stock_flow"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(8), nullable=False)
    ts_code = Column(String(16), nullable=False)
    name = Column(String(32), default="")
    close = Column(Float, default=0)
    pct_change = Column(Float, default=0)
    turnover_rate = Column(Float, default=0)
    buy_sm_vol = Column(Float, default=0)
    buy_sm_amount = Column(Float, default=0)
    sell_sm_vol = Column(Float, default=0)
    sell_sm_amount = Column(Float, default=0)
    buy_md_vol = Column(Float, default=0)
    buy_md_amount = Column(Float, default=0)
    sell_md_vol = Column(Float, default=0)
    sell_md_amount = Column(Float, default=0)
    buy_lg_vol = Column(Float, default=0)
    buy_lg_amount = Column(Float, default=0)
    sell_lg_vol = Column(Float, default=0)
    sell_lg_amount = Column(Float, default=0)
    buy_elg_vol = Column(Float, default=0)
    buy_elg_amount = Column(Float, default=0)
    sell_elg_vol = Column(Float, default=0)
    sell_elg_amount = Column(Float, default=0)
    net_mf_vol = Column(Float, default=0)
    net_mf_amount = Column(Float, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("trade_date", "ts_code", name="uq_stock_flow_date_code"),
        Index("ix_stock_flow_date", "trade_date"),
        Index("ix_stock_flow_code", "ts_code"),
        Index("ix_stock_flow_date_code", "trade_date", "ts_code"),
    )


class MoneyflowDc(Base):
    """个股资金流向（东财 moneyflow_dc）缓存表。

    列名与 TuShare moneyflow_dc API 返回值一致：
    net_amount, net_amount_rate, buy_{elg,lg,md,sm}_amount, buy_{elg,lg,md,sm}_amount_rate
    """
    __tablename__ = "moneyflow_dc"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(8), nullable=False)
    ts_code = Column(String(16), nullable=False)
    close = Column(Float, default=0)
    pct_change = Column(Float, default=0)
    net_amount = Column(Float, default=0)
    net_amount_rate = Column(Float, default=0)
    buy_elg_amount = Column(Float, default=0)
    buy_elg_amount_rate = Column(Float, default=0)
    buy_lg_amount = Column(Float, default=0)
    buy_lg_amount_rate = Column(Float, default=0)
    buy_md_amount = Column(Float, default=0)
    buy_md_amount_rate = Column(Float, default=0)
    buy_sm_amount = Column(Float, default=0)
    buy_sm_amount_rate = Column(Float, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("trade_date", "ts_code", name="uq_moneyflow_dc_date_code"),
        Index("ix_moneyflow_dc_date", "trade_date"),
        Index("ix_moneyflow_dc_code", "ts_code"),
    )


class DragonTiger(Base):
    __tablename__ = "dragon_tiger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(8), nullable=False)
    ts_code = Column(String(16), nullable=False)
    name = Column(String(32), default="")
    close = Column(Float, default=0)
    pct_change = Column(Float, default=0)
    turnover_rate = Column(Float, default=0)
    amount = Column(Float, default=0)
    net_buy = Column(Float, default=0)
    reason = Column(String(128), default="")
    net_rate = Column(Float, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("trade_date", "ts_code", name="uq_dragon_tiger_date_code"),
        Index("ix_dragon_tiger_date", "trade_date"),
    )


class LimitList(Base):
    """涨跌停列表缓存表。"""
    __tablename__ = "limit_list"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(8), nullable=False)
    ts_code = Column(String(16), nullable=False)
    industry = Column(String(32), default="")
    name = Column(String(32), default="")
    close = Column(Float, default=0)
    pct_chg = Column(Float, default=0)
    amount = Column(Float, default=0)
    float_mv = Column(Float, default=0)
    total_mv = Column(Float, default=0)
    turnover_ratio = Column(Float, default=0)
    first_time = Column(String(8), default="")
    last_time = Column(String(8), default="")
    open_times = Column(Integer, default=0)
    up_stat = Column(String(32), default="")
    limit_times = Column(Integer, default=0)
    limit_type = Column(String(1), default="")  # 'U'=涨停, 'D'=跌停
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("trade_date", "ts_code", name="uq_limit_list_date_code"),
        Index("ix_limit_list_date", "trade_date"),
        Index("ix_limit_list_limit", "trade_date", "limit_type"),
    )


class StockBasic(Base):
    __tablename__ = "stock_basic"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(16), nullable=False, unique=True)
    symbol = Column(String(16), default="")
    name = Column(String(32), default="")
    industry = Column(String(32), default="")
    list_date = Column(String(8), default="")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_stock_basic_name", "name"),
        Index("ix_stock_basic_code", "ts_code"),
        Index("ix_stock_basic_symbol", "symbol"),
    )


class DailyPrice(Base):
    """个股日线行情表。"""
    __tablename__ = "daily_price"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(8), nullable=False)
    ts_code = Column(String(16), nullable=False)
    open = Column(Float, default=0)
    high = Column(Float, default=0)
    low = Column(Float, default=0)
    close = Column(Float, default=0)
    pre_close = Column(Float, default=0)
    change = Column(Float, default=0)
    pct_chg = Column(Float, default=0)
    vol = Column(Float, default=0)
    amount = Column(Float, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("trade_date", "ts_code", name="uq_daily_price_date_code"),
        Index("ix_daily_price_code", "ts_code"),
        Index("ix_daily_price_date", "trade_date"),
    )


class SectorMember(Base):
    __tablename__ = "sector_member"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sector_code = Column(String(32), nullable=False)
    sector_name = Column(String(64), nullable=False)
    member_code = Column(String(16), nullable=False)
    member_name = Column(String(32), default="")
    is_new = Column(String(1), default="0")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("sector_code", "member_code", name="uq_sector_member"),
        Index("ix_sector_member_sector", "sector_code"),
    )


class IndexDaily(Base):
    """大盘指数日线行情缓存表（index_daily）。"""
    __tablename__ = "index_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(8), nullable=False)
    ts_code = Column(String(32), nullable=False)
    close = Column(Float, default=0)
    open = Column(Float, default=0)
    high = Column(Float, default=0)
    low = Column(Float, default=0)
    pre_close = Column(Float, default=0)
    change = Column(Float, default=0)
    pct_chg = Column(Float, default=0)
    vol = Column(Float, default=0)
    amount = Column(Float, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("trade_date", "ts_code", name="uq_index_daily_date_code"),
        Index("ix_index_daily_code", "ts_code"),
        Index("ix_index_daily_date", "trade_date"),
    )


class SectorDaily(Base):
    """板块/概念指数日线行情缓存表（ths_daily）。"""
    __tablename__ = "sector_daily"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(8), nullable=False)
    ts_code = Column(String(32), nullable=False)
    close = Column(Float, default=0)
    open = Column(Float, default=0)
    high = Column(Float, default=0)
    low = Column(Float, default=0)
    pre_close = Column(Float, default=0)
    change = Column(Float, default=0)
    pct_change = Column(Float, default=0)
    vol = Column(Float, default=0)
    turnover_rate = Column(Float, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("trade_date", "ts_code", name="uq_sector_daily_date_code"),
        Index("ix_sector_daily_code", "ts_code"),
        Index("ix_sector_daily_date", "trade_date"),
    )


class ThsIndex(Base):
    """同花顺指数表。"""
    __tablename__ = "ths_index"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(32), nullable=False, unique=True)
    name = Column(String(64), default="")
    exchange = Column(String(16), default="")
    index_type = Column(String(32), default="")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_ths_index_code", "ts_code"),
    )


class StkFactor(Base):
    """个股技术指标缓存表（stk_factor）。"""
    __tablename__ = "stk_factor"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(8), nullable=False)
    ts_code = Column(String(16), nullable=False)
    close = Column(Float, default=0)
    open = Column(Float, default=0)
    high = Column(Float, default=0)
    low = Column(Float, default=0)
    pre_close = Column(Float, default=0)
    change = Column(Float, default=0)
    pct_change = Column(Float, default=0)
    vol = Column(Float, default=0)
    amount = Column(Float, default=0)
    adj_factor = Column(Float, default=0)
    macd_dif = Column(Float, default=0)
    macd_dea = Column(Float, default=0)
    macd = Column(Float, default=0)
    kdj_k = Column(Float, default=0)
    kdj_d = Column(Float, default=0)
    kdj_j = Column(Float, default=0)
    rsi_6 = Column(Float, default=0)
    rsi_12 = Column(Float, default=0)
    rsi_24 = Column(Float, default=0)
    boll_upper = Column(Float, default=0)
    boll_mid = Column(Float, default=0)
    boll_lower = Column(Float, default=0)
    cci = Column(Float, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("trade_date", "ts_code", name="uq_stk_factor_date_code"),
        Index("ix_stk_factor_date", "trade_date"),
        Index("ix_stk_factor_code", "ts_code"),
    )


class DailyBasic(Base):
    """个股每日基本面指标缓存表（daily_basic）。"""
    __tablename__ = "daily_basic"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(8), nullable=False)
    ts_code = Column(String(16), nullable=False)
    close = Column(Float, default=0)
    turnover_rate = Column(Float, default=0)
    turnover_rate_f = Column(Float, default=0)
    volume_ratio = Column(Float, default=0)
    pe = Column(Float, default=0)
    pe_ttm = Column(Float, default=0)
    pb = Column(Float, default=0)
    ps = Column(Float, default=0)
    ps_ttm = Column(Float, default=0)
    dv_ratio = Column(Float, default=0)
    dv_ttm = Column(Float, default=0)
    total_share = Column(Float, default=0)
    float_share = Column(Float, default=0)
    free_share = Column(Float, default=0)
    total_mv = Column(Float, default=0)
    circ_mv = Column(Float, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("trade_date", "ts_code", name="uq_daily_basic_date_code"),
        Index("ix_daily_basic_code", "ts_code"),
        Index("ix_daily_basic_date", "trade_date"),
    )


class Watchlist(Base):
    """自选股表。"""
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts_code = Column(String(16), nullable=False, unique=True)
    name = Column(String(32), default="")
    group_name = Column(String(32), default="default")  # default/观察仓/重仓/长线
    added_date = Column(String(8), default="")
    notes = Column(String(256), default="")
    sort_order = Column(Integer, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_watchlist_code", "ts_code"),
        Index("ix_watchlist_group", "group_name"),
    )
# ------------------------------------------------------------------
# Strategy Intelligence Models
# ------------------------------------------------------------------

class StrategySnapshot(Base):
    """策略每日快照——记录每次策略执行的结果摘要。"""
    __tablename__ = "strategy_snapshot"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(8), nullable=False)
    strategy_name = Column(String(64), nullable=False)
    pick_count = Column(Integer, default=0)
    top_picks = Column(String(2048), default="")  # JSON: [{ts_code, name, score, reason}]
    avg_score = Column(Float, default=0)
    max_score = Column(Float, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("trade_date", "strategy_name", name="uq_snapshot_date_strategy"),
        Index("ix_snapshot_date", "trade_date"),
        Index("ix_snapshot_strategy", "strategy_name"),
    )


class StrategyPerformance(Base):
    """策略推荐股票的后续表现——追踪推荐后的实际收益。"""
    __tablename__ = "strategy_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(8), nullable=False)  # 推荐日期
    strategy_name = Column(String(64), nullable=False)
    ts_code = Column(String(16), nullable=False)
    name = Column(String(32), default="")
    entry_score = Column(Float, default=0)  # 推荐时的评分
    entry_price = Column(Float, default=0)  # 推荐日收盘价
    ret_1d = Column(Float, nullable=True)   # 1日收益率
    ret_3d = Column(Float, nullable=True)   # 3日收益率
    ret_5d = Column(Float, nullable=True)   # 5日收益率
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("trade_date", "strategy_name", "ts_code", name="uq_perf_date_strat_code"),
        Index("ix_perf_date", "trade_date"),
        Index("ix_perf_strategy", "strategy_name"),
        Index("ix_perf_code", "ts_code"),
    )


class FactorPerformance(Base):
    """因子表现追踪表。"""
    __tablename__ = "factor_performance"
    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(8), nullable=False, index=True)
    factor_name = Column(String(32), nullable=False)  # value/momentum/flow/event/combo
    avg_return_1d = Column(Float, default=0)    # 平均1日收益率
    avg_return_5d = Column(Float, default=0)    # 平均5日收益率
    avg_score = Column(Float, default=0)        # 平均策略评分
    stock_count = Column(Integer, default=0)    # 选股数量
    win_rate = Column(Float, default=0)         # 胜率
    momentum = Column(Float, default=0)         # 动量得分(近期vs历史)
    recorded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("trade_date", "factor_name", name="uq_factor_perf"),
        Index("ix_factor_perf_date_factor", "trade_date", "factor_name"),
    )


class StrategyWeightHistory(Base):
    """策略自适应权重历史记录。"""
    __tablename__ = "strategy_weight_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_date = Column(String(8), nullable=False)
    strategy_name = Column(String(64), nullable=False)
    weight = Column(Float, nullable=False)
    performance_score = Column(Float, default=0)
    consistency_score = Column(Float, default=0)
    regime_fit_score = Column(Float, default=0)
    correlation_penalty = Column(Float, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("trade_date", "strategy_name", name="uq_weight_history"),
        Index("ix_weight_history_date", "trade_date"),
    )


class ActivityLog(Base):
    """AI 工作日志 — 记录 cron 任务执行记录."""
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_type = Column(String(20), nullable=False, index=True)  # review/evolution/sync/manual
    task_name = Column(String(100))  # 任务名称
    started_at = Column(String(30))  # ISO 格式时间
    finished_at = Column(String(30))
    duration_seconds = Column(Integer)
    status = Column(String(20), nullable=False, default="success")  # success/failed/partial
    summary = Column(String(500))  # 一句话摘要
    files_changed = Column(String(2000))  # JSON 数组
    details = Column(String(10000))  # 完整 markdown 报告
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_activity_type", "task_type"),
        Index("ix_activity_time", "started_at"),
    )


# Engine & session factory — lazy initialization via init_db()
# No module-level side effects: os.makedirs and create_engine are deferred.


class _LazySession:
    """Callable wrapper that defers sessionmaker creation until init_db() runs."""

    _factory = None

    def __call__(self):
        if _LazySession._factory is None:
            raise RuntimeError("Database not initialized — call init_db() first")
        return _LazySession._factory()


# Assign as module-level callable so `from .models import SessionLocal` works
# at import time; actual sessions are only created after init_db().
SessionLocal = _LazySession()


def init_db():
    """Create data directory, engine, session factory, and all tables."""
    global engine
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    engine = create_engine(
        f"sqlite:///{DB_PATH}",
        echo=False,
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=StaticPool,
    )

    # 通过 connect 事件处理器设置 PRAGMA，这是 SQLAlchemy 设置 PRAGMA 的正确方式
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    _LazySession._factory = sessionmaker(bind=engine)
    Base.metadata.create_all(engine)
