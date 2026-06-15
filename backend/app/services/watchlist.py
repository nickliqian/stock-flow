"""自选股服务层——管理自选股列表和每日信号雷达。"""

import logging
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from .base import BaseService, get_global_client, get_global_cache
from ..engine.registry import get_all_strategies, load_all_strategies
from ..engine.data_loader import StrategyDataLoader

logger = logging.getLogger(__name__)

# LRU cache for data_loader.load() results keyed by trade_date.
# Ensures the same trade_date's data is loaded at most once per process.
_DATA_CACHE_MAX = 5
_data_load_cache: "OrderedDict[str, dict]" = OrderedDict()


class WatchlistService(BaseService):
    """自选股管理与信号雷达。"""

    def __init__(self, cache=None, client=None):
        super().__init__(cache=cache, client=client)
        self.loader = StrategyDataLoader(self.client, self.cache)
        load_all_strategies()

    # ------------------------------------------------------------------
    # public
    # ------------------------------------------------------------------
    def list_watchlist(self, group_name: Optional[str] = None) -> Dict[str, Any]:
        """返回自选股列表，包含每只股票当日的策略信号。"""
        from ..models import Watchlist, StockBasic
        with self.cache._session() as session:
            query = session.query(Watchlist).order_by(Watchlist.sort_order, Watchlist.id)
            if group_name:
                query = query.filter(Watchlist.group_name == group_name)
            items = query.all()

            if not items:
                return {"success": True, "data": []}

            # 获取所有自选股的 ts_code 列表
            ts_codes = [item.ts_code for item in items]

            # 获取 stock_basic 名称映射
            name_map = {}
            try:
                basics = session.query(StockBasic.ts_code, StockBasic.name).filter(
                    StockBasic.ts_code.in_(ts_codes)
                ).all()
                name_map = {b.ts_code: b.name for b in basics}
            except Exception as exc:
                logger.warning("Failed to load stock_basic names: %s", exc)

            # 运行所有策略，收集信号
            signals_map = self._get_signals_for_stocks(ts_codes)

            # 批量获取所有自选股的最新价（一次查询替代 N 次）
            price_map = self._get_latest_price_batch(ts_codes)

            # 组装返回数据
            result = []
            for item in items:
                ts_code = item.ts_code
                stock_name = name_map.get(ts_code) or item.name or ""
                stock_signals = signals_map.get(ts_code, [])

                close, pct_change = price_map.get(ts_code, (0, 0))

                # 计算置信度
                signal_count = len(stock_signals)
                if signal_count == 0:
                    conviction = "none"
                elif signal_count == 1:
                    conviction = "low"
                elif signal_count == 2:
                    conviction = "medium"
                else:
                    conviction = "high"

                result.append({
                    "ts_code": ts_code,
                    "name": stock_name,
                    "group_name": item.group_name,
                    "added_date": item.added_date,
                    "notes": item.notes,
                    "close": close,
                    "pct_change": pct_change,
                    "signals": stock_signals,
                    "signal_count": signal_count,
                    "conviction": conviction,
                })

            return {"success": True, "data": result}

    def add_to_watchlist(
        self, ts_code: str, group_name: str = "default", notes: str = ""
    ) -> Dict[str, Any]:
        """添加自选股（先查 stock_basic 获取名称）。"""
        from ..models import Watchlist, StockBasic
        with self.cache._session() as session:
            try:
                # 检查是否已存在
                existing = session.query(Watchlist).filter(Watchlist.ts_code == ts_code).first()
                if existing:
                    return {"success": False, "error": f"{ts_code} 已在自选股列表中"}

                # 从 stock_basic 获取名称
                stock_name = ""
                try:
                    basic = session.query(StockBasic).filter(StockBasic.ts_code == ts_code).first()
                    if basic:
                        stock_name = basic.name or ""
                except Exception as exc:
                    logger.warning("Failed to query stock_basic: %s", exc)

                today = datetime.now().strftime("%Y%m%d")
                item = Watchlist(
                    ts_code=ts_code,
                    name=stock_name,
                    group_name=group_name,
                    added_date=today,
                    notes=notes,
                )
                session.add(item)
                session.commit()

                return {
                    "success": True,
                    "data": {
                        "ts_code": ts_code,
                        "name": stock_name,
                        "group_name": group_name,
                    },
                }
            except Exception as exc:
                session.rollback()
                logger.error("Failed to add to watchlist: %s", exc, exc_info=True)
                return {"success": False, "error": "添加自选股失败，请稍后重试"}

    def remove_from_watchlist(self, ts_code: str) -> Dict[str, Any]:
        """删除自选股。"""
        from ..models import Watchlist
        with self.cache._session() as session:
            try:
                item = session.query(Watchlist).filter(Watchlist.ts_code == ts_code).first()
                if not item:
                    return {"success": False, "error": f"{ts_code} 不在自选股列表中"}
                session.delete(item)
                session.commit()
                return {"success": True, "data": {"ts_code": ts_code}}
            except Exception as exc:
                session.rollback()
                logger.error("Failed to remove from watchlist: %s", exc, exc_info=True)
                return {"success": False, "error": "删除自选股失败，请稍后重试"}

    def update_watchlist(
        self, ts_code: str, group_name: Optional[str] = None, notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """更新自选股信息。"""
        from ..models import Watchlist
        with self.cache._session() as session:
            try:
                item = session.query(Watchlist).filter(Watchlist.ts_code == ts_code).first()
                if not item:
                    return {"success": False, "error": f"{ts_code} 不在自选股列表中"}
                if group_name is not None:
                    item.group_name = group_name
                if notes is not None:
                    item.notes = notes
                session.commit()
                return {
                    "success": True,
                    "data": {
                        "ts_code": ts_code,
                        "group_name": item.group_name,
                        "notes": item.notes,
                    },
                }
            except Exception as exc:
                session.rollback()
                logger.error("Failed to update watchlist: %s", exc, exc_info=True)
                return {"success": False, "error": "更新自选股失败，请稍后重试"}

    def get_stock_signals(self, ts_code: str) -> Dict[str, Any]:
        """获取单只股票的当日所有策略信号。"""
        from ..models import StockBasic
        with self.cache._session() as session:
            stock_name = ""
            try:
                basic = session.query(StockBasic).filter(StockBasic.ts_code == ts_code).first()
                if basic:
                    stock_name = basic.name or ""
            except Exception:
                pass

            signals = self._get_signals_for_stocks([ts_code]).get(ts_code, [])
            close, pct_change = self._get_latest_price(ts_code)

            return {
                "success": True,
                "data": {
                    "ts_code": ts_code,
                    "name": stock_name,
                    "close": close,
                    "pct_change": pct_change,
                    "signals": signals,
                    "signal_count": len(signals),
                },
            }

    def get_all_signals(self, trade_date: Optional[str] = None) -> Dict[str, Any]:
        """获取所有自选股的信号汇总。"""
        from ..models import Watchlist, StockBasic
        with self.cache._session() as session:
            items = session.query(Watchlist).all()
            ts_codes = [item.ts_code for item in items]

            if not ts_codes:
                return {"success": True, "data": {"trade_date": trade_date, "stocks": []}}

            # 名称映射
            name_map = {}
            try:
                basics = session.query(StockBasic.ts_code, StockBasic.name).filter(
                    StockBasic.ts_code.in_(ts_codes)
                ).all()
                name_map = {b.ts_code: b.name for b in basics}
            except Exception:
                pass

            signals_map = self._get_signals_for_stocks(ts_codes)

            # 批量获取最新价（一次查询替代 N 次）
            price_map = self._get_latest_price_batch(ts_codes)

            stocks = []
            for item in items:
                ts_code = item.ts_code
                stock_signals = signals_map.get(ts_code, [])
                close, pct_change = price_map.get(ts_code, (0, 0))
                stocks.append({
                    "ts_code": ts_code,
                    "name": name_map.get(ts_code) or item.name or "",
                    "group_name": item.group_name,
                    "close": close,
                    "pct_change": pct_change,
                    "signals": stock_signals,
                    "signal_count": len(stock_signals),
                })

            return {"success": True, "data": {"trade_date": trade_date, "stocks": stocks}}

    def get_stats(self) -> Dict[str, Any]:
        """统计：总数、各分组数量、各 conviction 数量。"""
        from ..models import Watchlist
        with self.cache._session() as session:
            items = session.query(Watchlist).all()
            total = len(items)

            # 分组统计
            group_counts: Dict[str, int] = {}
            for item in items:
                g = item.group_name or "default"
                group_counts[g] = group_counts.get(g, 0) + 1

            # 信号统计
            ts_codes = [item.ts_code for item in items]
            signals_map = self._get_signals_for_stocks(ts_codes) if ts_codes else {}

            conviction_counts: Dict[str, int] = {"none": 0, "low": 0, "medium": 0, "high": 0}
            with_signals = 0
            for ts_code in ts_codes:
                count = len(signals_map.get(ts_code, []))
                if count == 0:
                    conviction_counts["none"] += 1
                elif count == 1:
                    conviction_counts["low"] += 1
                elif count == 2:
                    conviction_counts["medium"] += 1
                else:
                    conviction_counts["high"] += 1
                if count > 0:
                    with_signals += 1

            return {
                "success": True,
                "data": {
                    "total": total,
                    "groups": group_counts,
                    "convictions": conviction_counts,
                    "with_signals": with_signals,
                },
            }

    # ------------------------------------------------------------------
    # private
    # ------------------------------------------------------------------
    def _get_signals_for_stocks(self, ts_codes: List[str]) -> Dict[str, List[Dict]]:
        """对给定股票列表运行所有策略，返回 {ts_code: [signal_dict, ...]}。

        使用 LRU 缓存 data_loader.load() 的结果，同一个 trade_date 下
        只加载一次全量数据，避免 list_watchlist / get_stats 等多次调用
        导致重复加载。
        """
        global _data_load_cache
        from ..utils import get_latest_trade_date
        trade_date = get_latest_trade_date(self.cache)

        strategies = get_all_strategies()
        if not strategies:
            return {code: [] for code in ts_codes}

        # 汇总所有策略所需数据键
        all_keys: set = set()
        for s in strategies.values():
            all_keys.update(s.required_data())

        # Cache lookup: reuse data for the same trade_date
        cache_key = trade_date
        if cache_key in _data_load_cache:
            data = _data_load_cache[cache_key]
        else:
            data = self.loader.load(trade_date, list(all_keys))
            # Insert into LRU cache, evict oldest if full
            _data_load_cache[cache_key] = data
            _data_load_cache.move_to_end(cache_key)
            if len(_data_load_cache) > _DATA_CACHE_MAX:
                _data_load_cache.popitem(last=False)

        ts_set = set(ts_codes)
        signals_map: Dict[str, List[Dict]] = {code: [] for code in ts_codes}

        for name, strategy in strategies.items():
            try:
                results = strategy.check(data)
                for r in results:
                    if r.ts_code in ts_set:
                        signals_map[r.ts_code].append({
                            "strategy": name,
                            "icon": strategy.icon,
                            "name": strategy.description,
                            "category": strategy.category,
                            "score": round(r.score, 2),
                            "reason": r.reason,
                        })
            except Exception as exc:
                logger.error("Strategy '%s' failed in watchlist scan: %s", name, exc)

        return signals_map

    def _get_latest_price(self, ts_code: str):
        """获取单只股票最新价和涨跌幅。"""
        try:
            from ..models import StkFactor
            with self.cache._session() as session:
                row = session.query(StkFactor).filter(
                    StkFactor.ts_code == ts_code
                ).order_by(StkFactor.trade_date.desc()).first()
                if row:
                    return row.close, row.pct_change
        except Exception as exc:
            logger.warning("Failed to get latest price for %s: %s", ts_code, exc)
        return 0, 0

    def _get_latest_price_batch(self, ts_codes: list) -> Dict[str, tuple]:
        """批量获取多只股票的最新价和涨跌幅（一次查询替代 N 次）。"""
        from ..models import StkFactor
        if not ts_codes:
            return {}
        with self.cache._session() as session:
            try:
                from sqlalchemy import text as sa_text
                placeholders = ", ".join([f":tc{i}" for i in range(len(ts_codes))])
                params = {}
                for i, tc in enumerate(ts_codes):
                    params[f"tc{i}"] = tc
                results = session.execute(
                    sa_text(f"""
                        SELECT s.ts_code, s.close, s.pct_change FROM stk_factor s
                        INNER JOIN (
                            SELECT ts_code, MAX(trade_date) AS max_td
                            FROM stk_factor
                            WHERE ts_code IN ({placeholders})
                            GROUP BY ts_code
                        ) latest ON s.ts_code = latest.ts_code AND s.trade_date = latest.max_td
                    """),
                    params,
                ).fetchall()
                return {r[0]: (r[1] or 0, r[2] or 0) for r in results}
            except Exception as exc:
                logger.warning("Failed to batch get latest prices: %s", exc)
                return {}
