import logging
import threading
from sqlalchemy import text
from datetime import datetime, timedelta, timezone
import pandas as pd

logger = logging.getLogger(__name__)

from .models import SessionLocal
from .config import (
    FLOW_CACHE_MINUTES,
    SECTOR_MEMBER_CACHE_MINUTES,
    STOCK_BASIC_CACHE_MINUTES,
    THS_INDEX_CACHE_MINUTES,
    DAILY_PRICE_CACHE_MINUTES,
    DAILY_BASIC_CACHE_MINUTES,
    INDEX_DAILY_CACHE_MINUTES,
    STK_FACTOR_CACHE_MINUTES,
)


class CacheService:
    """SQLite-based cache with freshness checking."""

    def __init__(self):
        self.Session = SessionLocal
        # In-memory cache for get_all_sector_members()
        self._sector_members_cache = None
        self._sector_members_cache_time = None
        self._sector_members_lock = threading.Lock()

    from contextlib import contextmanager

    @contextmanager
    def _session(self):
        """Context manager for database sessions."""
        s = self.Session()
        try:
            yield s
        finally:
            s.close()

    def get_freshness_minutes(self, table_name: str) -> int:
        """Return max allowed age in minutes for a given table."""
        mapping = {
            "market_flow": FLOW_CACHE_MINUTES,
            "north_fund_flow": FLOW_CACHE_MINUTES,
            "stock_flow": FLOW_CACHE_MINUTES,
            "moneyflow_dc": FLOW_CACHE_MINUTES,
            "dragon_tiger": FLOW_CACHE_MINUTES,
            "sector_flow": FLOW_CACHE_MINUTES,
            "sector_daily": DAILY_PRICE_CACHE_MINUTES,
            "sector_member": SECTOR_MEMBER_CACHE_MINUTES,
            "stock_basic": STOCK_BASIC_CACHE_MINUTES,
            "ths_index": THS_INDEX_CACHE_MINUTES,
            "daily_price": DAILY_PRICE_CACHE_MINUTES,
            "daily_basic": DAILY_BASIC_CACHE_MINUTES,
            "limit_list": DAILY_PRICE_CACHE_MINUTES,
            "index_daily": INDEX_DAILY_CACHE_MINUTES,
            "stk_factor": STK_FACTOR_CACHE_MINUTES,
        }
        return mapping.get(table_name, FLOW_CACHE_MINUTES)

    def is_fresh(self, table_name: str, trade_date: str = None) -> bool:
        """Check if cached data for the table is still fresh."""
        # 白名单校验，防止 SQL 注入
        allowed_tables = {
            "market_flow", "north_fund_flow", "stock_flow", "moneyflow_dc",
            "sector_flow", "dragon_tiger", "sector_member", "stock_basic",
            "ths_index", "daily_price", "sector_daily", "daily_basic",
            "limit_list", "index_daily", "stk_factor",
        }
        if table_name not in allowed_tables:
            return False
        with self._session() as session:
            try:
                max_age_min = self.get_freshness_minutes(table_name)
                # Use naive UTC datetime so comparison works with SQLite's naive datetimes
                cutoff = (datetime.now(timezone.utc) - timedelta(minutes=max_age_min)).replace(tzinfo=None)

                query = "SELECT MAX(updated_at) as last_update FROM " + table_name
                if trade_date:
                    query += " WHERE trade_date = :trade_date"
                    result = session.execute(text(query), {"trade_date": trade_date}).fetchone()
                else:
                    result = session.execute(text(query)).fetchone()

                if result and result[0]:
                    last_update = result[0]
                    if isinstance(last_update, str):
                        last_update = datetime.fromisoformat(last_update)
                    # Strip timezone info if present to ensure naive comparison
                    if hasattr(last_update, 'tzinfo') and last_update.tzinfo is not None:
                        last_update = last_update.replace(tzinfo=None)
                    return last_update > cutoff
                return False
            except Exception:
                logger.debug("is_fresh check failed for %s: %s", table_name, exc_info=True)
                return False

    def upsert_market_flow(self, data: pd.DataFrame, trade_date: str):
        """Upsert market_flow records in batch."""
        with self._session() as session:
            try:
                now = datetime.now(timezone.utc)
                rows = []
                for _, row in data.iterrows():
                    rows.append({
                        "td": trade_date,
                        "bsv": _safe_float(row, "buy_sm_vol") or 0.0,
                        "bsa": _safe_float(row, "buy_sm_amount") or 0.0,
                        "ssv": _safe_float(row, "sell_sm_vol") or 0.0,
                        "ssa": _safe_float(row, "sell_sm_amount") or 0.0,
                        "bmv": _safe_float(row, "buy_md_vol") or 0.0,
                        "bma": _safe_float(row, "buy_md_amount") or 0.0,
                        "smv": _safe_float(row, "sell_md_vol") or 0.0,
                        "sma": _safe_float(row, "sell_md_amount") or 0.0,
                        "blv": _safe_float(row, "buy_lg_vol") or 0.0,
                        "bla": _safe_float(row, "buy_lg_amount") or 0.0,
                        "slv": _safe_float(row, "sell_lg_vol") or 0.0,
                        "sla": _safe_float(row, "sell_lg_amount") or 0.0,
                        "bev": _safe_float(row, "buy_elg_vol") or 0.0,
                        "bea": _safe_float(row, "buy_elg_amount") or 0.0,
                        "sev": _safe_float(row, "sell_elg_vol") or 0.0,
                        "sea": _safe_float(row, "sell_elg_amount") or 0.0,
                        "nmv": _safe_float(row, "net_mf_vol") or 0.0,
                        "nma": _safe_float(row, "net_mf_amount") or 0.0,
                        "ua": now,
                    })
                if rows:
                    session.execute(
                        text("""
                            INSERT OR REPLACE INTO market_flow
                            (trade_date, buy_sm_vol, buy_sm_amount, sell_sm_vol, sell_sm_amount,
                             buy_md_vol, buy_md_amount, sell_md_vol, sell_md_amount,
                             buy_lg_vol, buy_lg_amount, sell_lg_vol, sell_lg_amount,
                             buy_elg_vol, buy_elg_amount, sell_elg_vol, sell_elg_amount,
                             net_mf_vol, net_mf_amount, updated_at)
                            VALUES (:td, :bsv, :bsa, :ssv, :ssa,
                                    :bmv, :bma, :smv, :sma,
                                    :blv, :bla, :slv, :sla,
                                    :bev, :bea, :sev, :sea,
                                    :nmv, :nma, :ua)
                        """),
                        rows,
                    )
                session.commit()
            except Exception:
                session.rollback()
                raise

    def upsert_north_fund(self, data: pd.DataFrame, trade_date: str):
        """Upsert north_fund_flow records in batch."""
        with self._session() as session:
            try:
                now = datetime.now(timezone.utc)
                rows = []
                for _, row in data.iterrows():
                    rows.append({
                        "td": trade_date,
                        "gss": _safe_float(row, "ggt_ss") or 0.0,
                        "gsz": _safe_float(row, "ggt_sz") or 0.0,
                        "hgt": _safe_float(row, "hgt") or 0.0,
                        "sgt": _safe_float(row, "sgt") or 0.0,
                        "nm": _safe_float(row, "north_money") or 0.0,
                        "ua": now,
                    })
                if rows:
                    session.execute(
                        text("""
                            INSERT OR REPLACE INTO north_fund_flow
                            (trade_date, ggt_ss, ggt_sz, hgt, sgt, north_money, updated_at)
                            VALUES (:td, :gss, :gsz, :hgt, :sgt, :nm, :ua)
                        """),
                        rows,
                    )
                session.commit()
            except Exception:
                session.rollback()
                raise

    def upsert_stock_flows(self, data: pd.DataFrame, trade_date: str):
        """Upsert stock_flow records in batch using INSERT OR REPLACE."""
        # 过滤 ts_code 为 NaN/None 的行，防止写入字符串 "nan" 到数据库
        data = data[data["ts_code"].notna()]
        with self._session() as session:
            try:
                now = datetime.now(timezone.utc)
                rows = []
                for _, row in data.iterrows():
                    pc = _safe_float(row, "pct_change")
                    rows.append({
                        "td": trade_date,
                        "tc": str(row.get("ts_code", "")),
                        "nm": str(row.get("name", "")),
                        "cl": _safe_float(row, "close") or 0.0,
                        "pc": pc if pc is not None else (_safe_float(row, "pct_chg") or 0.0),
                        "tr": _safe_float(row, "turnover_rate") or 0.0,
                        "bsv": _safe_float(row, "buy_sm_vol") or 0.0,
                        "bsa": _safe_float(row, "buy_sm_amount") or 0.0,
                        "ssv": _safe_float(row, "sell_sm_vol") or 0.0,
                        "ssa": _safe_float(row, "sell_sm_amount") or 0.0,
                        "bmv": _safe_float(row, "buy_md_vol") or 0.0,
                        "bma": _safe_float(row, "buy_md_amount") or 0.0,
                        "smv": _safe_float(row, "sell_md_vol") or 0.0,
                        "sma": _safe_float(row, "sell_md_amount") or 0.0,
                        "blv": _safe_float(row, "buy_lg_vol") or 0.0,
                        "bla": _safe_float(row, "buy_lg_amount") or 0.0,
                        "slv": _safe_float(row, "sell_lg_vol") or 0.0,
                        "sla": _safe_float(row, "sell_lg_amount") or 0.0,
                        "bev": _safe_float(row, "buy_elg_vol") or 0.0,
                        "bea": _safe_float(row, "buy_elg_amount") or 0.0,
                        "sev": _safe_float(row, "sell_elg_vol") or 0.0,
                        "sea": _safe_float(row, "sell_elg_amount") or 0.0,
                        "nmv": _safe_float(row, "net_mf_vol") or 0.0,
                        "nma": _safe_float(row, "net_mf_amount") or 0.0,
                        "ua": now,
                    })
                if rows:
                    session.execute(
                        text("""
                            INSERT OR REPLACE INTO stock_flow
                            (trade_date, ts_code, name, close, pct_change, turnover_rate,
                             buy_sm_vol, buy_sm_amount, sell_sm_vol, sell_sm_amount,
                             buy_md_vol, buy_md_amount, sell_md_vol, sell_md_amount,
                             buy_lg_vol, buy_lg_amount, sell_lg_vol, sell_lg_amount,
                             buy_elg_vol, buy_elg_amount, sell_elg_vol, sell_elg_amount,
                             net_mf_vol, net_mf_amount, updated_at)
                            VALUES (:td, :tc, :nm, :cl, :pc, :tr,
                                    :bsv, :bsa, :ssv, :ssa,
                                    :bmv, :bma, :smv, :sma,
                                    :blv, :bla, :slv, :sla,
                                    :bev, :bea, :sev, :sea,
                                    :nmv, :nma, :ua)
                        """),
                        rows,
                    )
                session.commit()
            except Exception:
                session.rollback()
                raise

    def upsert_moneyflow_dc(self, data: pd.DataFrame, trade_date: str):
        """Upsert moneyflow_dc records in batch using INSERT OR REPLACE.

        列名与 TuShare moneyflow_dc API 一致：
        net_amount, net_amount_rate, buy_{elg,lg,md,sm}_amount, buy_{elg,lg,md,sm}_amount_rate
        """
        # 过滤 ts_code 为 NaN/None 的行，防止写入字符串 "nan" 到数据库
        data = data[data["ts_code"].notna()]
        with self._session() as session:
            try:
                now = datetime.now(timezone.utc)
                rows = []
                for _, row in data.iterrows():
                    rows.append({
                        "td": trade_date,
                        "tc": str(row.get("ts_code", "")),
                        "cl": _safe_float(row, "close") or 0.0,
                        "pc": _safe_float(row, "pct_change") or 0.0,
                        "na": _safe_float(row, "net_amount") or 0.0,
                        "nar": _safe_float(row, "net_amount_rate") or 0.0,
                        "bea": _safe_float(row, "buy_elg_amount") or 0.0,
                        "bear": _safe_float(row, "buy_elg_amount_rate") or 0.0,
                        "bla": _safe_float(row, "buy_lg_amount") or 0.0,
                        "blar": _safe_float(row, "buy_lg_amount_rate") or 0.0,
                        "bma": _safe_float(row, "buy_md_amount") or 0.0,
                        "bmar": _safe_float(row, "buy_md_amount_rate") or 0.0,
                        "bsa": _safe_float(row, "buy_sm_amount") or 0.0,
                        "bsar": _safe_float(row, "buy_sm_amount_rate") or 0.0,
                        "ua": now,
                    })
                if rows:
                    session.execute(
                        text("""
                            INSERT OR REPLACE INTO moneyflow_dc
                            (trade_date, ts_code, close, pct_change,
                             net_amount, net_amount_rate,
                             buy_elg_amount, buy_elg_amount_rate,
                             buy_lg_amount, buy_lg_amount_rate,
                             buy_md_amount, buy_md_amount_rate,
                             buy_sm_amount, buy_sm_amount_rate, updated_at)
                            VALUES (:td, :tc, :cl, :pc,
                                    :na, :nar,
                                    :bea, :bear,
                                    :bla, :blar,
                                    :bma, :bmar,
                                    :bsa, :bsar, :ua)
                        """),
                        rows,
                    )
                session.commit()
            except Exception:
                session.rollback()
                raise

    def get_moneyflow_dc_by_codes(self, trade_date: str, ts_codes: list) -> list:
        """Get moneyflow_dc records filtered by specific ts_codes (SQL-level filtering)."""
        if not ts_codes:
            return []
        with self._session() as session:
            placeholders = ", ".join([f":tc{i}" for i in range(len(ts_codes))])
            params = {"td": trade_date}
            for i, tc in enumerate(ts_codes):
                params[f"tc{i}"] = tc
            results = session.execute(
                text(f"""
                    SELECT id, trade_date, ts_code, close, pct_change,
                           net_amount, net_amount_rate,
                           buy_elg_amount, buy_elg_amount_rate,
                           buy_lg_amount, buy_lg_amount_rate,
                           buy_md_amount, buy_md_amount_rate,
                           buy_sm_amount, buy_sm_amount_rate,
                           net_amount AS net_mf_amount,
                           updated_at
                    FROM moneyflow_dc WHERE trade_date = :td
                    AND ts_code IN ({placeholders})
                """),
                params,
            ).fetchall()
            return [dict(r._mapping) for r in results]

    def has_moneyflow_dc(self, trade_date: str) -> bool:
        """Check if moneyflow_dc data exists for a trade date (lightweight, no full load)."""
        with self._session() as session:
            result = session.execute(
                text("SELECT 1 FROM moneyflow_dc WHERE trade_date = :td LIMIT 1"),
                {"td": trade_date},
            ).fetchone()
            return result is not None

    def get_moneyflow_dc(self, trade_date: str) -> list:
        """Get all moneyflow_dc records for a trade date.

        返回字典中 key 为 net_mf_amount（兼容 get_stock_ranking 等调用方）。
        """
        with self._session() as session:
            results = session.execute(
                text("""
                    SELECT id, trade_date, ts_code, close, pct_change,
                           net_amount, net_amount_rate,
                           buy_elg_amount, buy_elg_amount_rate,
                           buy_lg_amount, buy_lg_amount_rate,
                           buy_md_amount, buy_md_amount_rate,
                           buy_sm_amount, buy_sm_amount_rate,
                           net_amount AS net_mf_amount,
                           updated_at
                    FROM moneyflow_dc WHERE trade_date = :td
                """),
                {"td": trade_date},
            ).fetchall()
            return [dict(r._mapping) for r in results]

    def get_moneyflow_dc_ranking(self, trade_date: str, ranking_type: str = "net_inflow", limit: int = 20) -> list:
        """Get top N moneyflow_dc records by net amount using SQL ORDER BY + LIMIT."""
        # 白名单校验，防止 SQL 注入
        allowed_ranking_types = {"net_inflow", "net_outflow"}
        if ranking_type not in allowed_ranking_types:
            ranking_type = "net_inflow"
        with self._session() as session:
            order_dir = "DESC" if ranking_type != "net_outflow" else "ASC"
            results = session.execute(
                text(f"""
                    SELECT id, trade_date, ts_code, close, pct_change,
                           net_amount, net_amount_rate,
                           buy_elg_amount, buy_elg_amount_rate,
                           buy_lg_amount, buy_lg_amount_rate,
                           buy_md_amount, buy_md_amount_rate,
                           buy_sm_amount, buy_sm_amount_rate,
                           net_amount AS net_mf_amount,
                           updated_at
                    FROM moneyflow_dc WHERE trade_date = :td
                    ORDER BY net_amount {order_dir}
                    LIMIT :limit
                """),
                {"td": trade_date, "limit": limit},
            ).fetchall()
            return [dict(r._mapping) for r in results]

    def upsert_dragon_tiger(self, data: pd.DataFrame, trade_date: str):
        """Upsert dragon_tiger records in batch."""
        # 过滤 ts_code 为 NaN/None 的行，防止写入字符串 "nan" 到数据库
        data = data[data["ts_code"].notna()]
        with self._session() as session:
            try:
                # 只删除 DataFrame 中包含的 ts_code，避免覆盖其他股票的缓存数据
                ts_codes = data["ts_code"].unique().tolist() if not data.empty and "ts_code" in data.columns else []
                if ts_codes:
                    placeholders = ", ".join([f":tc{i}" for i in range(len(ts_codes))])
                    params = {"td": trade_date}
                    for i, tc in enumerate(ts_codes):
                        params[f"tc{i}"] = tc
                    session.execute(
                        text(f"DELETE FROM dragon_tiger WHERE trade_date = :td AND ts_code IN ({placeholders})"),
                        params,
                    )
                now = datetime.now(timezone.utc)
                rows = []
                for _, row in data.iterrows():
                    pc = _safe_float(row, "pct_change")
                    nb = _safe_float(row, "net_buy")
                    rows.append({
                        "td": trade_date,
                        "tc": str(row.get("ts_code", "")),
                        "nm": str(row.get("name", "")),
                        "cl": _safe_float(row, "close") or 0.0,
                        "pc": pc if pc is not None else (_safe_float(row, "pct_chg") or 0.0),
                        "tr": _safe_float(row, "turnover_rate") or 0.0,
                        "am": _safe_float(row, "amount") or 0.0,
                        "nb": ((nb if nb is not None else _safe_float(row, "net_amount")) or 0.0) / 10000,
                        "re": str(row.get("reason", "")),
                        "nr": _safe_float(row, "net_rate") or 0.0,
                        "ua": now,
                    })
                if rows:
                    session.execute(
                        text("""
                            INSERT OR REPLACE INTO dragon_tiger
                            (trade_date, ts_code, name, close, pct_change,
                             turnover_rate, amount, net_buy, reason, net_rate, updated_at)
                            VALUES (:td, :tc, :nm, :cl, :pc,
                                    :tr, :am, :nb, :re, :nr, :ua)
                        """),
                        rows,
                    )
                session.commit()
            except Exception:
                session.rollback()
                raise

    def upsert_sector_flows(self, records: list, trade_date: str):
        """Upsert aggregated sector_flow records in batch.

        采用「先 INSERT 新数据 → 再 DELETE 旧数据」策略，
        避免 DELETE-then-INSERT 之间多线程读到空表。
        """
        with self._session() as session:
            try:
                new_codes = set()
                if records:
                    now = datetime.now(timezone.utc)
                    rows = []
                    for rec in records:
                        sc = rec["sector_code"]
                        new_codes.add(sc)
                        rows.append({
                            "td": trade_date,
                            "sc": sc,
                            "sn": rec["sector_name"],
                            "ni": rec["net_inflow"],
                            "ln": rec["large_net"],
                            "lp": rec["large_pct"],
                            "ls": rec.get("lead_stock", ""),
                            "lsn": rec.get("lead_stock_name", ""),
                            "lc": rec.get("lead_chg", 0),
                            "ua": now,
                        })
                    session.execute(
                        text("""
                            INSERT OR REPLACE INTO sector_flow
                            (trade_date, sector_code, sector_name, net_inflow,
                             large_net, large_pct, lead_stock, lead_stock_name, lead_chg, updated_at)
                            VALUES (:td, :sc, :sn, :ni,
                                    :ln, :lp, :ls, :lsn, :lc, :ua)
                        """),
                        rows,
                    )
                # 删除该交易日中不在新数据集中的旧记录
                if new_codes:
                    codes_list = list(new_codes)
                    placeholders = ", ".join([f":sc{j}" for j in range(len(codes_list))])
                    params = {"td": trade_date}
                    for j, sc in enumerate(codes_list):
                        params[f"sc{j}"] = sc
                    session.execute(
                        text(f"DELETE FROM sector_flow WHERE trade_date = :td AND sector_code NOT IN ({placeholders})"),
                        params,
                    )
                else:
                    session.execute(
                        text("DELETE FROM sector_flow WHERE trade_date = :td"),
                        {"td": trade_date},
                    )
                session.commit()
            except Exception:
                session.rollback()
                raise

    def upsert_sector_members(self, data: pd.DataFrame):
        """Upsert all sector members in a single transaction.

        采用「先 INSERT 新数据 → 再 DELETE 旧数据」策略，
        避免 DELETE-then-INSERT 之间多线程读到空表。

        DELETE 时分批执行，避免超过 SQLITE_MAX_VARIABLE_NUMBER（默认 999）。
        """
        BATCH_SIZE = 400  # each pair uses 2 params, so 400 pairs = 800 params < 999
        with self._session() as session:
            try:
                new_keys = set()
                if not data.empty:
                    now = datetime.now(timezone.utc)
                    rows = []
                    for _, row in data.iterrows():
                        sc = str(row.get("sector_code", ""))
                        mc = str(row.get("member_code", ""))
                        new_keys.add((sc, mc))
                        rows.append({
                            "sc": sc,
                            "sn": str(row.get("sector_name", "")),
                            "mc": mc,
                            "mn": str(row.get("member_name", "")),
                            "isn": str(row.get("is_new", "0")),
                            "ua": now,
                        })
                    if rows:
                        session.execute(
                            text("""
                                INSERT OR REPLACE INTO sector_member
                                (sector_code, sector_name, member_code, member_name, is_new, updated_at)
                                VALUES (:sc, :sn, :mc, :mn, :isn, :ua)
                            """),
                            rows,
                        )
                # 删除不在新数据集中的旧记录
                # 使用临时表存放全部新 key，再通过子查询一次性删除，
                # 避免原来逐批 DELETE NOT IN (batch_i) 只保留最后一批的 bug。
                if new_keys:
                    keys_list = list(new_keys)
                    session.execute(text("CREATE TEMPORARY TABLE IF NOT EXISTS _new_sector_keys (sector_code TEXT, member_code TEXT)"))
                    try:
                        for i in range(0, len(keys_list), BATCH_SIZE):
                            batch = keys_list[i:i + BATCH_SIZE]
                            batch_rows = [{"sc": sc, "mc": mc} for sc, mc in batch]
                            session.execute(
                                text("INSERT INTO _new_sector_keys (sector_code, member_code) VALUES (:sc, :mc)"),
                                batch_rows,
                            )
                        session.execute(
                            text("""
                                DELETE FROM sector_member
                                WHERE (sector_code, member_code) NOT IN
                                      (SELECT sector_code, member_code FROM _new_sector_keys)
                            """),
                        )
                    finally:
                        session.execute(text("DROP TABLE IF EXISTS _new_sector_keys"))
                else:
                    # data 为空时不应删除全表，直接提交（无操作）并返回
                    session.commit()
                    return
                session.commit()
            except Exception:
                session.rollback()
                raise

    def upsert_stock_basic(self, data: pd.DataFrame):
        """Upsert stock_basic records in batch.

        采用「先 INSERT 新数据 → 再 DELETE 旧数据」策略，
        避免 DELETE-then-INSERT 之间多线程读到空表。

        DELETE 时分批执行，避免超过 SQLITE_MAX_VARIABLE_NUMBER（默认 999）。
        """
        # 过滤 ts_code 为 NaN/None 的行，防止写入字符串 "nan" 到数据库
        data = data[data["ts_code"].notna()]
        BATCH_SIZE = 500
        with self._session() as session:
            try:
                new_codes = set()
                if not data.empty:
                    now = datetime.now(timezone.utc)
                    rows = []
                    for _, row in data.iterrows():
                        tc = str(row.get("ts_code", ""))
                        new_codes.add(tc)
                        rows.append({
                            "tc": tc,
                            "sy": str(row.get("symbol", "")),
                            "nm": str(row.get("name", "")),
                            "ind": str(row.get("industry", "")),
                            "ld": str(row.get("list_date", "")),
                            "ua": now,
                        })
                    if rows:
                        session.execute(
                            text("""
                                INSERT OR REPLACE INTO stock_basic
                                (ts_code, symbol, name, industry, list_date, updated_at)
                                VALUES (:tc, :sy, :nm, :ind, :ld, :ua)
                            """),
                            rows,
                        )
                # 删除不在新数据集中的旧记录
                # 使用临时表存放全部新 key，再通过子查询一次性删除，
                # 避免原来逐批 DELETE NOT IN (batch_i) 只保留最后一批的 bug。
                if new_codes:
                    codes_list = list(new_codes)
                    session.execute(text("CREATE TEMPORARY TABLE IF NOT EXISTS _new_stock_codes (ts_code TEXT)"))
                    try:
                        for i in range(0, len(codes_list), BATCH_SIZE):
                            batch = codes_list[i:i + BATCH_SIZE]
                            batch_rows = [{"tc": tc} for tc in batch]
                            session.execute(
                                text("INSERT INTO _new_stock_codes (ts_code) VALUES (:tc)"),
                                batch_rows,
                            )
                        session.execute(
                            text("""
                                DELETE FROM stock_basic
                                WHERE ts_code NOT IN
                                      (SELECT ts_code FROM _new_stock_codes)
                            """),
                        )
                    finally:
                        session.execute(text("DROP TABLE IF EXISTS _new_stock_codes"))
                else:
                    # data 为空时不应删除全表，直接提交（无操作）并返回
                    session.commit()
                    return
                session.commit()
            except Exception:
                session.rollback()
                raise

    def upsert_ths_index(self, data: pd.DataFrame):
        """Upsert ths_index records in batch.

        采用「先 INSERT 新数据 → 再 DELETE 旧数据」策略，
        避免 DELETE-then-INSERT 之间多线程读到空表。

        DELETE 时分批执行，避免超过 SQLITE_MAX_VARIABLE_NUMBER（默认 999）。
        """
        # 过滤 ts_code 为 NaN/None 的行，防止写入字符串 "nan" 到数据库
        data = data[data["ts_code"].notna()]
        BATCH_SIZE = 500
        with self._session() as session:
            try:
                new_codes = set()
                if not data.empty:
                    now = datetime.now(timezone.utc)
                    rows = []
                    for _, row in data.iterrows():
                        tc = str(row.get("ts_code", ""))
                        new_codes.add(tc)
                        rows.append({
                            "tc": tc,
                            "nm": str(row.get("name", "")),
                            "ex": str(row.get("exchange", "")),
                            "it": str(row.get("index_type", "")),
                            "ua": now,
                        })
                    if rows:
                        session.execute(
                            text("""
                                INSERT OR REPLACE INTO ths_index
                                (ts_code, name, exchange, index_type, updated_at)
                                VALUES (:tc, :nm, :ex, :it, :ua)
                            """),
                            rows,
                        )
                # 删除不在新数据集中的旧记录
                # 使用临时表存放全部新 key，再通过子查询一次性删除，
                # 避免原来逐批 DELETE NOT IN (batch_i) 只保留最后一批的 bug。
                if new_codes:
                    codes_list = list(new_codes)
                    session.execute(text("CREATE TEMPORARY TABLE IF NOT EXISTS _new_ths_codes (ts_code TEXT)"))
                    try:
                        for i in range(0, len(codes_list), BATCH_SIZE):
                            batch = codes_list[i:i + BATCH_SIZE]
                            batch_rows = [{"tc": tc} for tc in batch]
                            session.execute(
                                text("INSERT INTO _new_ths_codes (ts_code) VALUES (:tc)"),
                                batch_rows,
                            )
                        session.execute(
                            text("""
                                DELETE FROM ths_index
                                WHERE ts_code NOT IN
                                      (SELECT ts_code FROM _new_ths_codes)
                            """),
                        )
                    finally:
                        session.execute(text("DROP TABLE IF EXISTS _new_ths_codes"))
                else:
                    # data 为空时不应删除全表，直接提交（无操作）并返回
                    session.commit()
                    return
                session.commit()
            except Exception:
                session.rollback()
                raise

    _ALLOWED_TABLES = frozenset({"daily_price", "sector_daily", "index_daily"})

    def _upsert_daily(self, table_name: str, data: pd.DataFrame, ts_code: str,
                       col_defs: list):
        """Generic upsert for daily OHLCV-like tables.

        Args:
            table_name: target database table name (must be in _ALLOWED_TABLES).
            data: pandas DataFrame to insert.
            ts_code: ts_code value for all rows.
            col_defs: list of (db_column, param_key, src_field) tuples describing
                      data columns.  trade_date / ts_code / updated_at are handled
                      automatically.
        """
        if table_name not in self._ALLOWED_TABLES:
            raise ValueError(f"Invalid table name: {table_name!r}")
        with self._session() as session:
            try:
                # Only delete records that will be replaced
                trade_dates = data["trade_date"].unique().tolist() if not data.empty and "trade_date" in data.columns else []
                if trade_dates:
                    placeholders = ", ".join([f":td{i}" for i in range(len(trade_dates))])
                    params = {"tc": ts_code}
                    for i, td in enumerate(trade_dates):
                        params[f"td{i}"] = td
                    session.execute(
                        text(f"DELETE FROM {table_name} WHERE ts_code = :tc AND trade_date IN ({placeholders})"),
                        params,
                    )
                # Batch insert new data
                now = datetime.now(timezone.utc)
                rows = []
                for _, row in data.iterrows():
                    row_data = {
                        "td": str(row.get("trade_date", "")),
                        "tc": ts_code,
                        "ua": now,
                    }
                    for _, param_key, src_field in col_defs:
                        row_data[param_key] = _safe_float(row, src_field) or 0.0
                    rows.append(row_data)
                if rows:
                    db_columns = ["trade_date", "ts_code"] + [c[0] for c in col_defs] + ["updated_at"]
                    param_keys = ["td", "tc"] + [c[1] for c in col_defs] + ["ua"]
                    cols_str = ", ".join(db_columns)
                    vals_str = ", ".join([f":{k}" for k in param_keys])
                    session.execute(
                        text(f"INSERT OR REPLACE INTO {table_name}\n                        ({cols_str})\n                        VALUES ({vals_str})"),
                        rows,
                    )
                session.commit()
            except Exception:
                session.rollback()
                raise

    def upsert_daily_prices(self, data: pd.DataFrame, ts_code: str):
        """Upsert daily_price records in batch."""
        col_defs = [
            ("open", "op", "open"),
            ("high", "hi", "high"),
            ("low", "lo", "low"),
            ("close", "cl", "close"),
            ("pre_close", "pc", "pre_close"),
            ("change", "ch", "change"),
            ("pct_chg", "pct", "pct_chg"),
            ("vol", "vol", "vol"),
            ("amount", "amt", "amount"),
        ]
        self._upsert_daily("daily_price", data, ts_code, col_defs)

    def get_daily_prices(self, ts_code: str, limit: int = 20) -> list:
        """Get daily prices for a stock, ordered by date descending."""
        with self._session() as session:
            results = session.execute(
                text("""
                    SELECT trade_date, ts_code, open, high, low, close,
                           pre_close, change, pct_chg, vol, amount
                    FROM daily_price
                    WHERE ts_code = :tc
                    ORDER BY trade_date DESC
                    LIMIT :limit
                """),
                {"tc": ts_code, "limit": limit},
            ).fetchall()
            return [dict(r._mapping) for r in results]

    def get_daily_closes_batch(self, ts_codes: list, days: int = 20) -> dict:
        """Batch-get recent close prices for multiple stocks.

        Returns {ts_code: [close_recent, close_prev, ...]} ordered by
        trade_date DESC (most recent first), limited to *days* rows per stock.

        修复：分批查询防止 SQLite 默认的 999 变量限制（SQLITE_MAX_VARIABLE_NUMBER），
        当 ts_codes 数量过多时会触发 sqlite3.OperationalError。
        """
        if not ts_codes:
            return {}

        # SQLite 默认变量上限为 999，每个批次预留一些余量给 :limit 参数
        # 使用 900 作为安全批次大小
        _BATCH_SIZE = 900

        mapping: dict = {}
        with self._session() as session:
            # 将 ts_codes 分批处理
            for batch_start in range(0, len(ts_codes), _BATCH_SIZE):
                batch_codes = ts_codes[batch_start:batch_start + _BATCH_SIZE]
                placeholders = ", ".join([f":tc{i}" for i in range(len(batch_codes))])
                params = {}
                for i, tc in enumerate(batch_codes):
                    params[f"tc{i}"] = tc
                params["limit"] = days
                results = session.execute(
                    text(f"""
                        SELECT ts_code, close
                        FROM (
                            SELECT ts_code, close, trade_date,
                                   ROW_NUMBER() OVER (
                                       PARTITION BY ts_code ORDER BY trade_date DESC
                                   ) AS rn
                            FROM daily_price
                            WHERE ts_code IN ({placeholders})
                        )
                        WHERE rn <= :limit
                        ORDER BY ts_code, rn
                    """),
                    params,
                ).fetchall()
                for r in results:
                    code = r.ts_code
                    if code not in mapping:
                        mapping[code] = []
                    mapping[code].append(float(r.close) if r.close else 0.0)
            return mapping

    # --- Query methods ---

    def get_market_flow(self, trade_date: str) -> dict:
        with self._session() as session:
            result = session.execute(
                text("SELECT * FROM market_flow WHERE trade_date = :td LIMIT 1"),
                {"td": trade_date},
            ).fetchone()
            if not result:
                return None
            return dict(result._mapping)

    def get_north_fund(self, trade_date: str) -> dict:
        with self._session() as session:
            result = session.execute(
                text("SELECT * FROM north_fund_flow WHERE trade_date = :td LIMIT 1"),
                {"td": trade_date},
            ).fetchone()
            if not result:
                return None
            return dict(result._mapping)

    def get_north_fund_range(self, start_date: str, end_date: str) -> list:
        with self._session() as session:
            results = session.execute(
                text("SELECT * FROM north_fund_flow WHERE trade_date BETWEEN :s AND :e ORDER BY trade_date"),
                {"s": start_date, "e": end_date},
            ).fetchall()
            return [dict(r._mapping) for r in results]

    def get_stock_flow(self, trade_date: str, ts_code: str) -> dict:
        """Get stock flow data with name from stock_basic.

        moneyflow API does not return name, so we JOIN stock_basic to get it.
        """
        with self._session() as session:
            result = session.execute(
                text("""
                    SELECT sf.*, sb.name
                    FROM stock_flow sf
                    LEFT JOIN stock_basic sb ON sf.ts_code = sb.ts_code
                    WHERE sf.trade_date = :td AND sf.ts_code = :tc
                    LIMIT 1
                """),
                {"td": trade_date, "tc": ts_code},
            ).fetchone()
            if not result:
                return None
            return dict(result._mapping)

    def get_dragon_tiger(self, trade_date: str, ts_code: str = None) -> list:
        with self._session() as session:
            if ts_code:
                results = session.execute(
                    text("SELECT * FROM dragon_tiger WHERE trade_date = :td AND ts_code = :tc"),
                    {"td": trade_date, "tc": ts_code},
                ).fetchall()
            else:
                results = session.execute(
                    text("SELECT * FROM dragon_tiger WHERE trade_date = :td ORDER BY amount DESC"),
                    {"td": trade_date},
                ).fetchall()
            return [dict(r._mapping) for r in results]

    # [修改] 问题8：添加 sort_order 参数支持 asc/desc 排序
    def get_sector_flows(self, trade_date: str, page: int = 1, size: int = 20, sort_order: str = "desc", sort_by: str = "net_inflow") -> dict:
        with self._session() as session:
            offset = (page - 1) * size
            total = session.execute(
                text("SELECT COUNT(*) FROM sector_flow WHERE trade_date = :td"),
                {"td": trade_date},
            ).scalar()
            order_dir = "DESC" if sort_order.lower() != "asc" else "ASC"
            # 白名单校验 sort_by，防止 SQL 注入
            allowed_sort_fields = {"net_inflow", "large_net", "sector_name", "large_pct", "lead_stock_name", "lead_chg"}
            if sort_by not in allowed_sort_fields:
                sort_by = "net_inflow"
            results = session.execute(
                text(f"""
                    SELECT * FROM sector_flow WHERE trade_date = :td
                    ORDER BY {sort_by} {order_dir}
                    LIMIT :limit OFFSET :offset
                """),
                {"td": trade_date, "limit": size, "offset": offset},
            ).fetchall()
            return {
                "total": total or 0,
                "page": page,
                "size": size,
                "data": [dict(r._mapping) for r in results],
            }

    def search_sectors(self, query: str, trade_date: str = None) -> list:
        with self._session() as session:
            q = f"%{query}%"
            if trade_date:
                results = session.execute(
                    text("""
                        SELECT * FROM sector_flow
                        WHERE trade_date = :td AND (sector_name LIKE :q OR sector_code LIKE :q)
                        ORDER BY net_inflow DESC LIMIT 20
                    """),
                    {"td": trade_date, "q": q},
                ).fetchall()
            else:
                results = session.execute(
                    text("""
                        SELECT * FROM sector_flow
                        WHERE sector_name LIKE :q OR sector_code LIKE :q
                        ORDER BY trade_date DESC, net_inflow DESC LIMIT 20
                    """),
                    {"q": q},
                ).fetchall()
            return [dict(r._mapping) for r in results]

    def search_stocks(self, query: str) -> list:
        with self._session() as session:
            q = f"%{query}%"
            results = session.execute(
                text("""
                    SELECT ts_code, symbol, name, industry
                    FROM stock_basic
                    WHERE name LIKE :q1 OR ts_code LIKE :q2 OR symbol LIKE :q3
                    LIMIT 20
                """),
                {"q1": q, "q2": q, "q3": q},
            ).fetchall()
            return [dict(r._mapping) for r in results]

    def get_sector_members(self, sector_code: str) -> list:
        with self._session() as session:
            results = session.execute(
                text("SELECT member_code, member_name FROM sector_member WHERE sector_code = :sc"),
                {"sc": sector_code},
            ).fetchall()
            return [dict(r._mapping) for r in results]

    def get_all_sector_members(self) -> dict:
        """Return {sector_code: [member_code, ...]} for all sectors.

        Uses in-memory cache with SECTOR_MEMBER_CACHE_MINUTES TTL to avoid
        loading the entire sector_member table on every call.
        Thread-safe via self._sector_members_lock.
        """
        # Check in-memory cache (fast path — read under lock)
        with self._sector_members_lock:
            now = datetime.now(timezone.utc)
            if (self._sector_members_cache is not None
                    and self._sector_members_cache_time is not None
                    and (now - self._sector_members_cache_time).total_seconds() < SECTOR_MEMBER_CACHE_MINUTES * 60):
                return self._sector_members_cache

        # Cache miss or expired — query DB (outside lock to avoid holding it during I/O)
        with self._session() as session:
            try:
                results = session.execute(
                    text("SELECT sector_code, sector_name, member_code, member_name FROM sector_member")
                ).fetchall()
                mapping = {}
                for r in results:
                    row = dict(r._mapping)
                    code = row["sector_code"]
                    if code not in mapping:
                        mapping[code] = {
                            "name": row["sector_name"],
                            "members": [],
                        }
                    mapping[code]["members"].append(row["member_code"])
                # Update in-memory cache under lock
                with self._sector_members_lock:
                    self._sector_members_cache = mapping
                    self._sector_members_cache_time = now
                return mapping
            except Exception:
                logger.debug("get_all_sector_members query failed: %s", exc_info=True)
                with self._sector_members_lock:
                    return self._sector_members_cache or {}

    def get_all_ths_index(self) -> list:
        """Get all ths_index records."""
        with self._session() as session:
            # Check if table exists
            try:
                results = session.execute(text("SELECT * FROM ths_index")).fetchall()
                return [dict(r._mapping) for r in results]
            except Exception:
                logger.debug("get_all_ths_index query failed: %s", exc_info=True)
                return []

    def get_stock_basic_from_db(self) -> list:
        """Get all stock_basic records from DB."""
        with self._session() as session:
            results = session.execute(
                text("SELECT ts_code, name FROM stock_basic")
            ).fetchall()
            return [dict(r._mapping) for r in results]

    def get_sector_trend(self, sector_code: str, days: int = 30) -> list:
        """Get historical flow trend for a sector across trade dates.

        Returns list of {trade_date, sector_code, sector_name, net_inflow,
                         large_net, large_pct} ordered by trade_date ASC.
        """
        with self._session() as session:
            results = session.execute(
                text(
                    """SELECT trade_date, sector_code, sector_name, net_inflow, large_net, large_pct
                    FROM sector_flow
                    WHERE sector_code = :sc
                    ORDER BY trade_date DESC
                    LIMIT :limit"""
                ),
                {"sc": sector_code, "limit": days},
            ).fetchall()
            rows = [dict(r._mapping) for r in results]
            rows.reverse()
            return rows

    def upsert_sector_daily(self, data: pd.DataFrame, ts_code: str):
        """Upsert sector_daily records in batch (from ths_daily API)."""
        col_defs = [
            ("close", "cl", "close"),
            ("open", "op", "open"),
            ("high", "hi", "high"),
            ("low", "lo", "low"),
            ("pre_close", "pc", "pre_close"),
            ("change", "ch", "change"),
            ("pct_change", "pct", "pct_change"),
            ("vol", "vol", "vol"),
            ("turnover_rate", "tr", "turnover_rate"),
        ]
        self._upsert_daily("sector_daily", data, ts_code, col_defs)

    def get_sector_daily(self, ts_code: str, days: int = 30) -> list:
        """Get sector daily price/volume data ordered by trade_date DESC."""
        with self._session() as session:
            results = session.execute(
                text("""
                    SELECT trade_date, ts_code, close, open, high, low,
                           pre_close, change, pct_change, vol, turnover_rate
                    FROM sector_daily
                    WHERE ts_code = :tc
                    ORDER BY trade_date DESC
                    LIMIT :limit
                """),
                {"tc": ts_code, "limit": days},
            ).fetchall()
            return [dict(r._mapping) for r in results]

    def get_sector_daily_batch(self, ts_codes: list, trade_date: str = None) -> dict:
        """Batch-get latest sector_daily for multiple ts_codes in one query.

        Returns {ts_code: {trade_date, ts_code, close, ...}} with the latest
        record per ts_code (optionally filtered by trade_date).
        """
        if not ts_codes:
            return {}
        with self._session() as session:
            placeholders = ", ".join([f":tc{i}" for i in range(len(ts_codes))])
            params = {}
            for i, tc in enumerate(ts_codes):
                params[f"tc{i}"] = tc

            # Build query: optionally filter by trade_date
            if trade_date:
                query = f"""
                    SELECT sd.trade_date, sd.ts_code, sd.close, sd.open, sd.high, sd.low,
                           sd.pre_close, sd.change, sd.pct_change, sd.vol, sd.turnover_rate
                    FROM sector_daily sd
                    INNER JOIN (
                        SELECT ts_code, MAX(trade_date) AS max_td
                        FROM sector_daily
                        WHERE ts_code IN ({placeholders}) AND trade_date = :td
                        GROUP BY ts_code
                    ) latest ON sd.ts_code = latest.ts_code AND sd.trade_date = latest.max_td
                """
                params["td"] = trade_date
            else:
                query = f"""
                    SELECT sd.trade_date, sd.ts_code, sd.close, sd.open, sd.high, sd.low,
                           sd.pre_close, sd.change, sd.pct_change, sd.vol, sd.turnover_rate
                    FROM sector_daily sd
                    INNER JOIN (
                        SELECT ts_code, MAX(trade_date) AS max_td
                        FROM sector_daily
                        WHERE ts_code IN ({placeholders})
                        GROUP BY ts_code
                    ) latest ON sd.ts_code = latest.ts_code AND sd.trade_date = latest.max_td
                """

            results = session.execute(text(query), params).fetchall()
            return {dict(r._mapping)["ts_code"]: dict(r._mapping) for r in results}

    def upsert_daily_basic(self, data: pd.DataFrame, ts_code: str):
        """Upsert daily_basic records in batch.

        Delegates to batch_upsert_daily_basic for each trade_date in data,
        eliminating duplicate INSERT logic.
        """
        if data.empty or "trade_date" not in data.columns:
            return
        for td in data["trade_date"].unique():
            self.batch_upsert_daily_basic(data[data["trade_date"] == td], td)

    def get_daily_basic(self, ts_code: str, trade_date: str = None) -> dict:
        """Get daily_basic record for a stock."""
        with self._session() as session:
            if trade_date:
                result = session.execute(
                    text("""
                        SELECT * FROM daily_basic
                        WHERE ts_code = :tc AND trade_date = :td
                        LIMIT 1
                    """),
                    {"tc": ts_code, "td": trade_date},
                ).fetchone()
            else:
                result = session.execute(
                    text("""
                        SELECT * FROM daily_basic
                        WHERE ts_code = :tc
                        ORDER BY trade_date DESC
                        LIMIT 1
                    """),
                    {"tc": ts_code},
                ).fetchone()
            if not result:
                return None
            return dict(result._mapping)

    def batch_upsert_daily_basic(self, data: pd.DataFrame, trade_date: str):
        """Batch upsert daily_basic for specific stocks on a trade date.

        DELETE 条件同时包含 trade_date 和 ts_code，避免误删同日其他股票数据。
        """
        # 过滤 ts_code 为 NaN/None 的行，防止写入字符串 "nan" 到数据库
        data = data[data["ts_code"].notna()]
        with self._session() as session:
            try:
                if not data.empty and "ts_code" in data.columns:
                    ts_codes = data["ts_code"].unique().tolist()
                    if ts_codes:
                        placeholders = ", ".join([f":tc{i}" for i in range(len(ts_codes))])
                        params = {"td": trade_date}
                        for i, tc in enumerate(ts_codes):
                            params[f"tc{i}"] = tc
                        session.execute(
                            text(f"DELETE FROM daily_basic WHERE trade_date = :td AND ts_code IN ({placeholders})"),
                            params,
                        )
                if data.empty:
                    session.commit()
                    return
                now = datetime.now(timezone.utc)
                rows = []
                for _, row in data.iterrows():
                    rows.append({
                        "td": trade_date,
                        "tc": str(row.get("ts_code", "")),
                        "cl": _safe_float(row, "close") or 0.0,
                        "tr": _safe_float(row, "turnover_rate") or 0.0,
                        "trf": _safe_float(row, "turnover_rate_f") or 0.0,
                        "vr": _safe_float(row, "volume_ratio") or 0.0,
                        "pe": _safe_float(row, "pe") or 0.0,
                        "pt": _safe_float(row, "pe_ttm") or 0.0,
                        "pb": _safe_float(row, "pb") or 0.0,
                        "ps": _safe_float(row, "ps") or 0.0,
                        "pst": _safe_float(row, "ps_ttm") or 0.0,
                        "dr": _safe_float(row, "dv_ratio") or 0.0,
                        "dt": _safe_float(row, "dv_ttm") or 0.0,
                        "ts": _safe_float(row, "total_share") or 0.0,
                        "fs": _safe_float(row, "float_share") or 0.0,
                        "fre": _safe_float(row, "free_share") or 0.0,
                        "tmv": _safe_float(row, "total_mv") or 0.0,
                        "cmv": _safe_float(row, "circ_mv") or 0.0,
                        "ua": now,
                    })
                if rows:
                    session.execute(
                        text("""
                            INSERT OR REPLACE INTO daily_basic
                            (trade_date, ts_code, close, turnover_rate, turnover_rate_f, volume_ratio,
                             pe, pe_ttm, pb, ps, ps_ttm, dv_ratio, dv_ttm,
                             total_share, float_share, free_share, total_mv, circ_mv, updated_at)
                            VALUES (:td, :tc, :cl, :tr, :trf, :vr,
                                    :pe, :pt, :pb, :ps, :pst, :dr, :dt,
                                    :ts, :fs, :fre, :tmv, :cmv, :ua)
                        """),
                        rows,
                    )
                session.commit()
            except Exception:
                session.rollback()
                raise

    def get_all_daily_basic(self, trade_date: str) -> list:
        """Get all daily_basic records for a trade date, joined with stock_basic for names."""
        with self._session() as session:
            results = session.execute(
                text("""
                    SELECT db.trade_date, db.ts_code, db.close, db.turnover_rate,
                           db.turnover_rate_f, db.volume_ratio, db.pe, db.pe_ttm,
                           db.pb, db.ps, db.ps_ttm, db.dv_ratio, db.dv_ttm,
                           db.total_share, db.float_share, db.free_share,
                           db.total_mv, db.circ_mv,
                           sb.name, sb.industry
                    FROM daily_basic db
                    LEFT JOIN stock_basic sb ON db.ts_code = sb.ts_code
                    WHERE db.trade_date = :td
                """),
                {"td": trade_date},
            ).fetchall()
            return [dict(r._mapping) for r in results]

    def get_all_daily_basic_count(self, trade_date: str) -> int:
        """Count daily_basic records for a trade date."""
        with self._session() as session:
            result = session.execute(
                text("SELECT COUNT(*) FROM daily_basic WHERE trade_date = :td"),
                {"td": trade_date},
            ).scalar()
            return result or 0

    def get_filtered_daily_basic(self, trade_date: str, filters: dict = None) -> list:
        """Get daily_basic records with SQL-level numeric filtering.

        Pushes common numeric filters into SQL WHERE to avoid loading all ~5000
        rows into Python memory for filtering.

        Supported filter keys: pe_min, pe_max, pb_min, pb_max,
        mv_min, mv_max (亿元→万元), circ_mv_min, circ_mv_max,
        turnover_min, turnover_max, volume_ratio_min, volume_ratio_max,
        dv_min, dv_max, name, industry.
        """
        where_clauses = ["db.trade_date = :td"]
        params: dict = {"td": trade_date}

        if filters:
            # PE(TTM) — use pe_ttm column
            if filters.get("pe_min") is not None:
                where_clauses.append("db.pe_ttm >= :pe_min")
                params["pe_min"] = float(filters["pe_min"])
            if filters.get("pe_max") is not None:
                where_clauses.append("db.pe_ttm > 0 AND db.pe_ttm <= :pe_max")
                params["pe_max"] = float(filters["pe_max"])

            # PB
            if filters.get("pb_min") is not None:
                where_clauses.append("db.pb >= :pb_min")
                params["pb_min"] = float(filters["pb_min"])
            if filters.get("pb_max") is not None:
                where_clauses.append("db.pb > 0 AND db.pb <= :pb_max")
                params["pb_max"] = float(filters["pb_max"])

            # Total market cap (亿元→万元)
            if filters.get("mv_min") is not None:
                where_clauses.append("db.total_mv >= :mv_min")
                params["mv_min"] = float(filters["mv_min"]) * 10000
            if filters.get("mv_max") is not None:
                where_clauses.append("db.total_mv <= :mv_max")
                params["mv_max"] = float(filters["mv_max"]) * 10000

            # Circulating market cap (亿元→万元)
            if filters.get("circ_mv_min") is not None:
                where_clauses.append("db.circ_mv >= :circ_mv_min")
                params["circ_mv_min"] = float(filters["circ_mv_min"]) * 10000
            if filters.get("circ_mv_max") is not None:
                where_clauses.append("db.circ_mv <= :circ_mv_max")
                params["circ_mv_max"] = float(filters["circ_mv_max"]) * 10000

            # Turnover rate
            if filters.get("turnover_min") is not None:
                where_clauses.append("db.turnover_rate >= :tr_min")
                params["tr_min"] = float(filters["turnover_min"])
            if filters.get("turnover_max") is not None:
                where_clauses.append("db.turnover_rate <= :tr_max")
                params["tr_max"] = float(filters["turnover_max"])

            # Volume ratio
            if filters.get("volume_ratio_min") is not None:
                where_clauses.append("db.volume_ratio >= :vr_min")
                params["vr_min"] = float(filters["volume_ratio_min"])
            if filters.get("volume_ratio_max") is not None:
                where_clauses.append("db.volume_ratio <= :vr_max")
                params["vr_max"] = float(filters["volume_ratio_max"])

            # Dividend yield
            if filters.get("dv_min") is not None:
                where_clauses.append("db.dv_ttm >= :dv_min")
                params["dv_min"] = float(filters["dv_min"])
            if filters.get("dv_max") is not None:
                where_clauses.append("db.dv_ttm <= :dv_max")
                params["dv_max"] = float(filters["dv_max"])

            # Name contains (case-insensitive LIKE on name or ts_code)
            name_q = filters.get("name")
            if name_q:
                where_clauses.append("(UPPER(sb.name) LIKE :name_q OR UPPER(db.ts_code) LIKE :name_q)")
                params["name_q"] = f"%{name_q.strip().upper()}%"

            # Industry equals
            industry = filters.get("industry")
            if industry:
                where_clauses.append("sb.industry = :industry")
                params["industry"] = industry.strip()

            # Net inflow (万元) — JOIN moneyflow_dc
            if filters.get("net_inflow_min") is not None:
                where_clauses.append("mf.net_amount >= :net_inflow_min")
                params["net_inflow_min"] = float(filters["net_inflow_min"])

        sql = f"""
            SELECT db.trade_date, db.ts_code, db.close, db.turnover_rate,
                   db.turnover_rate_f, db.volume_ratio, db.pe, db.pe_ttm,
                   db.pb, db.ps, db.ps_ttm, db.dv_ratio, db.dv_ttm,
                   db.total_share, db.float_share, db.free_share,
                   db.total_mv, db.circ_mv,
                   sb.name, sb.industry
            FROM daily_basic db
            LEFT JOIN stock_basic sb ON db.ts_code = sb.ts_code
            LEFT JOIN moneyflow_dc mf ON db.ts_code = mf.ts_code AND db.trade_date = mf.trade_date
            WHERE {" AND ".join(where_clauses)}
        """
        with self._session() as session:
            results = session.execute(text(sql), params).fetchall()
            return [dict(r._mapping) for r in results]

    def upsert_limit_list(self, data: pd.DataFrame, trade_date: str):
        """Upsert limit_list records in batch.

        采用「先 INSERT 新数据 → 再 DELETE 旧数据」策略，
        避免 DELETE-then-INSERT 之间多线程读到空表。
        """
        # 过滤 ts_code 为 NaN/None 的行，防止写入字符串 "nan" 到数据库
        data = data[data["ts_code"].notna()]
        with self._session() as session:
            try:
                new_codes = set()
                now = datetime.now(timezone.utc)
                rows = []
                for _, row in data.iterrows():
                    tc = str(row.get("ts_code", ""))
                    new_codes.add(tc)
                    rows.append({
                        "td": trade_date,
                        "tc": tc,
                        "ind": str(row.get("industry", "")),
                        "nm": str(row.get("name", "")),
                        "cl": _safe_float(row, "close") or 0.0,
                        "pc": _safe_float(row, "pct_chg") or 0.0,
                        "am": _safe_float(row, "amount") or 0.0,
                        "fmv": _safe_float(row, "float_mv") or 0.0,
                        "tmv": _safe_float(row, "total_mv") or 0.0,
                        "tr": _safe_float(row, "turnover_ratio") or 0.0,
                        "ft": str(row.get("first_time", "")),
                        "lt": str(row.get("last_time", "")),
                        "ot": int(_safe_float(row, "open_times", 0) or 0),
                        "us": str(row.get("up_stat", "")),
                        "ltimes": int(_safe_float(row, "limit_times", 0) or 0),
                        "lim": str(row.get("limit", "")),
                        "ua": now,
                    })
                if rows:
                    session.execute(
                        text("""
                            INSERT OR REPLACE INTO limit_list
                            (trade_date, ts_code, industry, name, close, pct_chg, amount,
                             float_mv, total_mv, turnover_ratio, first_time, last_time,
                             open_times, up_stat, limit_times, limit_type, updated_at)
                            VALUES (:td, :tc, :ind, :nm, :cl, :pc, :am,
                                    :fmv, :tmv, :tr, :ft, :lt,
                                    :ot, :us, :ltimes, :lim, :ua)
                        """),
                        rows,
                    )
                # 删除该交易日中不在新数据集中的旧记录
                if new_codes:
                    codes_list = list(new_codes)
                    placeholders = ", ".join([f":tc{j}" for j in range(len(codes_list))])
                    params = {"td": trade_date}
                    for j, tc in enumerate(codes_list):
                        params[f"tc{j}"] = tc
                    session.execute(
                        text(f"DELETE FROM limit_list WHERE trade_date = :td AND ts_code NOT IN ({placeholders})"),
                        params,
                    )
                else:
                    session.execute(
                        text("DELETE FROM limit_list WHERE trade_date = :td"),
                        {"td": trade_date},
                    )
                session.commit()
            except Exception:
                session.rollback()
                raise

    def get_limit_list(self, trade_date: str) -> list:
        """Get all limit_list records for a trade date."""
        with self._session() as session:
            results = session.execute(
                text("""
                    SELECT id, trade_date, ts_code, industry, name, close, pct_chg,
                           amount, float_mv, total_mv, turnover_ratio,
                           first_time, last_time, open_times, up_stat, limit_times, limit_type
                    FROM limit_list
                    WHERE trade_date = :td
                    ORDER BY limit_times DESC, amount DESC
                """),
                {"td": trade_date},
            ).fetchall()
            return [dict(r._mapping) for r in results]

    def upsert_index_daily(self, data: pd.DataFrame, ts_code: str):
        """Upsert index_daily records in batch."""
        col_defs = [
            ("close", "cl", "close"),
            ("open", "op", "open"),
            ("high", "hi", "high"),
            ("low", "lo", "low"),
            ("pre_close", "pc", "pre_close"),
            ("change", "ch", "change"),
            ("pct_chg", "pct", "pct_chg"),
            ("vol", "vol", "vol"),
            ("amount", "amt", "amount"),
        ]
        self._upsert_daily("index_daily", data, ts_code, col_defs)

    def get_index_daily(self, ts_code: str, trade_date: str = None) -> dict:
        """Get index_daily record for an index."""
        with self._session() as session:
            if trade_date:
                result = session.execute(
                    text("""
                        SELECT * FROM index_daily
                        WHERE ts_code = :tc AND trade_date = :td
                        LIMIT 1
                    """),
                    {"tc": ts_code, "td": trade_date},
                ).fetchone()
            else:
                result = session.execute(
                    text("""
                        SELECT * FROM index_daily
                        WHERE ts_code = :tc
                        ORDER BY trade_date DESC
                        LIMIT 1
                    """),
                    {"tc": ts_code},
                ).fetchone()
            if not result:
                return None
            return dict(result._mapping)

    def upsert_stk_factor(self, data: pd.DataFrame, trade_date: str):
        """Upsert stk_factor records in batch.

        采用「先 INSERT 新数据 → 再 DELETE 旧数据」策略，
        避免 DELETE-then-INSERT 之间多线程读到空表。
        """
        # 过滤 ts_code 为 NaN/None 的行，防止写入字符串 "nan" 到数据库
        data = data[data["ts_code"].notna()]
        if data.empty:
            return
        with self._session() as session:
            try:
                new_codes = set()
                now = datetime.now(timezone.utc)
                rows = []
                for _, row in data.iterrows():
                    tc = str(row.get("ts_code", ""))
                    new_codes.add(tc)
                    rows.append({
                        "td": trade_date,
                        "tc": tc,
                        "cl": _safe_float(row, "close") or 0.0,
                        "op": _safe_float(row, "open") or 0.0,
                        "hi": _safe_float(row, "high") or 0.0,
                        "lo": _safe_float(row, "low") or 0.0,
                        "pc": _safe_float(row, "pre_close") or 0.0,
                        "ch": _safe_float(row, "change") or 0.0,
                        "pct": _safe_float(row, "pct_change") or 0.0,
                        "vol": _safe_float(row, "vol") or 0.0,
                        "amt": _safe_float(row, "amount") or 0.0,
                        "af": _safe_float(row, "adj_factor") or 0.0,
                        "mdif": _safe_float(row, "macd_dif") or 0.0,
                        "mdea": _safe_float(row, "macd_dea") or 0.0,
                        "mcd": _safe_float(row, "macd") or 0.0,
                        "kk": _safe_float(row, "kdj_k") or 0.0,
                        "kd": _safe_float(row, "kdj_d") or 0.0,
                        "kj": _safe_float(row, "kdj_j") or 0.0,
                        "r6": _safe_float(row, "rsi_6") or 0.0,
                        "r12": _safe_float(row, "rsi_12") or 0.0,
                        "r24": _safe_float(row, "rsi_24") or 0.0,
                        "bu": _safe_float(row, "boll_upper") or 0.0,
                        "bm": _safe_float(row, "boll_mid") or 0.0,
                        "bl": _safe_float(row, "boll_lower") or 0.0,
                        "cci": _safe_float(row, "cci") or 0.0,
                        "ua": now,
                    })
                if rows:
                    session.execute(
                        text("""
                            INSERT OR REPLACE INTO stk_factor
                            (trade_date, ts_code, close, open, high, low, pre_close,
                             change, pct_change, vol, amount, adj_factor,
                             macd_dif, macd_dea, macd,
                             kdj_k, kdj_d, kdj_j,
                             rsi_6, rsi_12, rsi_24,
                             boll_upper, boll_mid, boll_lower, cci, updated_at)
                            VALUES (:td, :tc, :cl, :op, :hi, :lo, :pc,
                                    :ch, :pct, :vol, :amt, :af,
                                    :mdif, :mdea, :mcd,
                                    :kk, :kd, :kj,
                                    :r6, :r12, :r24,
                                    :bu, :bm, :bl, :cci, :ua)
                        """),
                        rows,
                    )
                # 删除该交易日中不在新数据集中的旧记录
                if new_codes:
                    codes_list = list(new_codes)
                    placeholders = ", ".join([f":tc{j}" for j in range(len(codes_list))])
                    params = {"td": trade_date}
                    for j, tc in enumerate(codes_list):
                        params[f"tc{j}"] = tc
                    session.execute(
                        text(f"DELETE FROM stk_factor WHERE trade_date = :td AND ts_code NOT IN ({placeholders})"),
                        params,
                    )
                else:
                    session.execute(
                        text("DELETE FROM stk_factor WHERE trade_date = :td"),
                        {"td": trade_date},
                    )
                session.commit()
            except Exception:
                session.rollback()
                raise

    def get_stk_factor_all(self, trade_date: str) -> list:
        """Get all stk_factor records for a trade date."""
        session = self.Session()
        try:
            results = session.execute(
                text("""
                    SELECT sf.trade_date, sf.ts_code, sf.close, sf.open, sf.high, sf.low,
                           sf.pre_close, sf.change, sf.pct_change, sf.vol, sf.amount,
                           sf.macd_dif, sf.macd_dea, sf.macd,
                           sf.kdj_k, sf.kdj_d, sf.kdj_j,
                           sf.rsi_6, sf.rsi_12, sf.rsi_24,
                           sf.boll_upper, sf.boll_mid, sf.boll_lower, sf.cci,
                           sb.name, sb.industry
                    FROM stk_factor sf
                    LEFT JOIN stock_basic sb ON sf.ts_code = sb.ts_code
                    WHERE sf.trade_date = :td
                """),
                {"td": trade_date},
            ).fetchall()
            return [dict(r._mapping) for r in results]
        finally:
            session.close()

    def get_stk_factor_count(self, trade_date: str) -> int:
        """Count stk_factor records for a trade date."""
        session = self.Session()
        try:
            result = session.execute(
                text("SELECT COUNT(*) FROM stk_factor WHERE trade_date = :td"),
                {"td": trade_date},
            ).scalar()
            return result or 0
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Strategy Weight History
    # ------------------------------------------------------------------

    def upsert_weight_history(self, records: list, trade_date: str):
        """Upsert strategy_weight_history records in batch.

        Each record dict should contain:
            strategy_name, weight, performance_score, consistency_score,
            regime_fit_score, correlation_penalty
        """
        with self._session() as session:
            try:
                if not records:
                    return
                # Delete existing records for this date first
                session.execute(
                    text("DELETE FROM strategy_weight_history WHERE trade_date = :td"),
                    {"td": trade_date},
                )
                now = datetime.now(timezone.utc)
                rows = []
                for rec in records:
                    rows.append({
                        "td": trade_date,
                        "sn": rec["strategy_name"],
                        "w": rec["weight"],
                        "ps": rec.get("performance_score", 0),
                        "cs": rec.get("consistency_score", 0),
                        "rf": rec.get("regime_fit_score", 0),
                        "cp": rec.get("correlation_penalty", 0),
                        "ca": now,
                    })
                if rows:
                    session.execute(
                        text("""
                            INSERT INTO strategy_weight_history
                            (trade_date, strategy_name, weight, performance_score,
                             consistency_score, regime_fit_score, correlation_penalty, created_at)
                            VALUES (:td, :sn, :w, :ps, :cs, :rf, :cp, :ca)
                        """),
                        rows,
                    )
                session.commit()
            except Exception:
                session.rollback()
                raise

    def get_weight_history(self, strategy_name: str = None, days: int = 30) -> list:
        """Get strategy weight history for visualization.

        Returns records ordered by trade_date DESC, limited by days.
        """
        session = self.Session()
        try:
            if strategy_name:
                results = session.execute(
                    text("""
                        SELECT trade_date, strategy_name, weight,
                               performance_score, consistency_score,
                               regime_fit_score, correlation_penalty
                        FROM strategy_weight_history
                        WHERE strategy_name = :sn
                        ORDER BY trade_date DESC
                        LIMIT :limit
                    """),
                    {"sn": strategy_name, "limit": days},
                ).fetchall()
            else:
                results = session.execute(
                    text("""
                        SELECT trade_date, strategy_name, weight,
                               performance_score, consistency_score,
                               regime_fit_score, correlation_penalty
                        FROM strategy_weight_history
                        ORDER BY trade_date DESC
                        LIMIT :limit
                    """),
                    {"limit": days * 20},
                ).fetchall()
            return [dict(r._mapping) for r in results]
        finally:
            session.close()

    def get_latest_weight_date(self) -> str:
        """Get the latest trade_date with weight records."""
        session = self.Session()
        try:
            result = session.execute(
                text("SELECT MAX(trade_date) FROM strategy_weight_history"),
            ).fetchone()
            return result[0] if result and result[0] else None
        finally:
            session.close()

    def get_stk_factor_prev_day(self, trade_date: str, ts_codes: list) -> list:
        """Get previous day's stk_factor for given ts_codes (for crossover detection).

        Uses ROW_NUMBER() window function to find each stock's own latest
        trade_date before the given date, ensuring per-stock accuracy.
        """
        session = self.Session()
        try:
            if not ts_codes:
                return []
            placeholders = ", ".join([f":tc{i}" for i in range(len(ts_codes))])
            params = {"td": trade_date}
            for i, tc in enumerate(ts_codes):
                params[f"tc{i}"] = tc
            results = session.execute(
                text(f"""
                    SELECT ts_code, macd, macd_dif, macd_dea, kdj_k, kdj_d, kdj_j
                    FROM (
                        SELECT ts_code, macd, macd_dif, macd_dea, kdj_k, kdj_d, kdj_j,
                               ROW_NUMBER() OVER (
                                   PARTITION BY ts_code ORDER BY trade_date DESC
                               ) AS rn
                        FROM stk_factor
                        WHERE trade_date < :td AND ts_code IN ({placeholders})
                    )
                    WHERE rn = 1
                """),
                params,
            ).fetchall()
            return [dict(r._mapping) for r in results]
        finally:
            session.close()


def _safe_float(row, key, default=None):
    """Safely extract a float value from a pandas Series."""
    try:
        val = row.get(key)
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        return float(val)
    except (ValueError, TypeError):
        return default
