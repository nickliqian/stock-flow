"""策略回测引擎——评估策略历史表现。"""

import logging
import math
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

import pandas as pd

from .registry import get_strategy, get_all_strategies, load_all_strategies
from .data_loader import StrategyDataLoader

logger = logging.getLogger(__name__)


class BacktestEngine:
    """回测引擎：在历史日期上执行策略，评估后续收益。"""

    def __init__(self, loader: StrategyDataLoader):
        self.loader = loader

    def run(
        self,
        strategy_name: str,
        start_date: str,
        end_date: str,
        hold_days: int = 5,
        top_n: int = 30,
    ) -> Dict[str, Any]:
        """
        回测指定策略在 [start_date, end_date] 区间的表现。

        逻辑：
        1. 遍历区间内每个交易日
        2. 在每个交易日执行策略，取 top_n 只股票
        3. 查找这些股票在 hold_days 个交易日后的价格
        4. 计算持有期收益率
        5. 汇总统计指标
        """
        load_all_strategies()

        strategy = get_strategy(strategy_name)
        if not strategy:
            return {"success": False, "error": f"未找到策略：{strategy_name}"}

        # 获取区间内的交易日
        trade_dates = self._get_trade_dates_in_range(start_date, end_date)
        if not trade_dates:
            return {"success": False, "error": "区间内无交易日"}

        # 按日期分批加载数据（避免重复加载）
        data_cache: Dict[str, Dict[str, pd.DataFrame]] = {}

        daily_results = []

        for td in trade_dates:
            try:
                # 加载策略所需数据
                data_keys = strategy.required_data()
                data = self._load_data_for_date(td, data_keys, data_cache)
                if not data:
                    continue

                # 执行策略
                results = strategy.check(data)
                results.sort(key=lambda r: r.score, reverse=True)
                picks = results[:top_n]
                if not picks:
                    daily_results.append({
                        "date": td,
                        "picks_count": 0,
                        "avg_return": None,
                        "best_return": None,
                        "worst_return": None,
                        "picks": [],
                    })
                    continue

                # 查找持有期后的价格
                exit_date = self._get_exit_date(td, hold_days)
                exit_prices = self._get_prices(exit_date, data_cache)
                entry_prices = self._get_entry_prices(td, picks, data_cache)

                # 计算每只股票的收益率
                pick_returns = []
                for pick in picks:
                    entry = entry_prices.get(pick.ts_code)
                    exit_p = exit_prices.get(pick.ts_code)
                    if entry and exit_p and entry > 0:
                        ret = ((exit_p - entry) / entry) * 100
                        pick_returns.append({
                            "ts_code": pick.ts_code,
                            "name": pick.name,
                            "entry_price": round(entry, 2),
                            "exit_price": round(exit_p, 2),
                            "return_pct": round(ret, 2),
                            "score": pick.score,
                            "reason": pick.reason,
                        })

                avg_ret = sum(r["return_pct"] for r in pick_returns) / len(pick_returns) if pick_returns else None
                best_ret = max((r["return_pct"] for r in pick_returns), default=None)
                worst_ret = min((r["return_pct"] for r in pick_returns), default=None)

                daily_results.append({
                    "date": td,
                    "picks_count": len(picks),
                    "avg_return": round(avg_ret, 2) if avg_ret is not None else None,
                    "best_return": round(best_ret, 2) if best_ret is not None else None,
                    "worst_return": round(worst_ret, 2) if worst_ret is not None else None,
                    "picks": sorted(pick_returns, key=lambda x: x["return_pct"], reverse=True)[:10],
                })
            except Exception as exc:
                logger.error("Backtest on %s failed: %s", td, exc)
                daily_results.append({
                    "date": td,
                    "picks_count": 0,
                    "avg_return": None,
                    "best_return": None,
                    "worst_return": None,
                    "picks": [],
                })

        # 汇总统计
        valid_days = [d for d in daily_results if d["avg_return"] is not None]
        returns = [d["avg_return"] for d in valid_days]

        stats = self._compute_stats(returns)
        stats["total_days"] = len(trade_dates)
        stats["valid_days"] = len(valid_days)
        stats["hold_days"] = hold_days
        stats["top_n"] = top_n

        # 计算累计收益曲线（等权组合）
        cumulative = 100
        equity_curve = [{"date": trade_dates[0], "value": 100}]
        for d in daily_results:
            if d["avg_return"] is not None:
                cumulative *= (1 + d["avg_return"] / 100)
            equity_curve.append({"date": d["date"], "value": round(cumulative, 2)})

        return {
            "success": True,
            "data": {
                "strategy": {
                    "name": strategy.name,
                    "description": strategy.description,
                    "category": strategy.category,
                    "icon": strategy.icon,
                },
                "params": {
                    "start_date": start_date,
                    "end_date": end_date,
                    "hold_days": hold_days,
                    "top_n": top_n,
                },
                "stats": stats,
                "equity_curve": equity_curve,
                "daily_results": daily_results,
            },
        }

    def _compute_stats(self, returns: List[float]) -> Dict[str, Any]:
        """计算回测统计指标。"""
        if not returns:
            return {
                "win_rate": 0, "avg_return": 0, "total_return": 0,
                "max_drawdown": 0, "sharpe_ratio": 0, "profit_loss_ratio": 0,
                "best_day": 0, "worst_day": 0, "positive_days": 0,
                "negative_days": 0,
            }

        n = len(returns)
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]

        avg_return = sum(returns) / n
        win_rate = len(wins) / n * 100 if n > 0 else 0

        # 累计收益
        cumulative = 1.0
        for r in returns:
            cumulative *= (1 + r / 100)
        total_return = (cumulative - 1) * 100

        # 最大回撤
        peak = 1.0
        max_dd = 0
        equity = 1.0
        for r in returns:
            equity *= (1 + r / 100)
            peak = max(peak, equity)
            dd = (peak - equity) / peak * 100
            max_dd = max(max_dd, dd)

        # 夏普比率（假设无风险利率3%年化，252交易日）
        if n > 1:
            mean_r = avg_return
            std_r = math.sqrt(sum((r - mean_r) ** 2 for r in returns) / (n - 1))
            daily_rf = 3.0 / 252
            sharpe = ((mean_r - daily_rf) / std_r * math.sqrt(252)) if std_r > 0 else 0
        else:
            sharpe = 0

        # 盈亏比
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 0.01
        profit_loss = avg_win / avg_loss if avg_loss > 0 else 0

        return {
            "win_rate": round(win_rate, 1),
            "avg_return": round(avg_return, 2),
            "total_return": round(total_return, 2),
            "max_drawdown": round(max_dd, 2),
            "sharpe_ratio": round(sharpe, 2),
            "profit_loss_ratio": round(profit_loss, 2),
            "best_day": round(max(returns), 2),
            "worst_day": round(min(returns), 2),
            "positive_days": len(wins),
            "negative_days": len(losses),
        }

    def _estimate_lookback(self, strategy) -> int:
        """估算策略需要回看多少交易日。"""
        keys = strategy.required_data()
        if "daily_multi" in keys:
            return 20
        if "moneyflow_multi" in keys:
            return 5
        return 3

    def _get_trade_dates_in_range(self, start: str, end: str) -> List[str]:
        """获取区间内的交易日列表（简化版：跳过周末和节假日）。"""
        from ..utils import is_holiday
        dates = []
        dt = datetime.strptime(start, "%Y%m%d")
        end_dt = datetime.strptime(end, "%Y%m%d")
        while dt <= end_dt:
            if dt.weekday() < 5 and not is_holiday(dt):
                dates.append(dt.strftime("%Y%m%d"))
            dt += timedelta(days=1)
        return dates

    def _get_trade_dates_before(self, date_str: str, n: int) -> List[str]:
        """获取指定日期前的N个交易日。"""
        from ..utils import get_last_n_trade_dates
        return get_last_n_trade_dates(date_str, n)

    def _get_trade_dates_after(self, date_str: str, n: int) -> List[str]:
        """获取指定日期后的N个交易日。"""
        from ..utils import is_holiday
        dates = []
        dt = datetime.strptime(date_str, "%Y%m%d")
        while len(dates) < n:
            dt += timedelta(days=1)
            if dt.weekday() < 5 and not is_holiday(dt):
                dates.append(dt.strftime("%Y%m%d"))
        return dates

    def _get_exit_date(self, entry_date: str, hold_days: int) -> str:
        """获取持有N天后的卖出日期。"""
        future = self._get_trade_dates_after(entry_date, hold_days)
        return future[-1] if future else entry_date

    def _load_data_for_date(
        self, trade_date: str, data_keys: List[str], cache: Dict
    ) -> Dict[str, pd.DataFrame]:
        """加载指定日期的数据（带缓存）。"""
        if trade_date not in cache:
            cache[trade_date] = self.loader.load(trade_date, data_keys)
        return cache[trade_date]

    def _get_prices(self, date_str: str, cache: Dict) -> Dict[str, float]:
        """从缓存的 daily 数据中获取收盘价。"""
        prices = {}
        if date_str not in cache:
            # 尝试加载 daily 数据
            try:
                df = self.loader._load_daily(date_str)
                if df is not None and not df.empty:
                    cache[f"_prices_{date_str}"] = df
            except Exception:
                return prices

        df = cache.get(f"_prices_{date_str}")
        if df is None:
            # 也检查主缓存中的 daily 数据
            day_cache = cache.get(date_str, {})
            for key, val in day_cache.items():
                if isinstance(val, pd.DataFrame) and "close" in val.columns and "ts_code" in val.columns:
                    df = val
                    break

        if df is not None and not df.empty:
            ts_col = "ts_code" if "ts_code" in df.columns else None
            close_col = "close" if "close" in df.columns else None
            if ts_col and close_col:
                for _, row in df.iterrows():
                    ts = row[ts_col]
                    cl = row[close_col]
                    if ts and cl:
                        try:
                            prices[str(ts)] = float(cl)
                        except (ValueError, TypeError):
                            pass
        return prices

    def _get_entry_prices(
        self, date_str: str, picks: list, cache: Dict
    ) -> Dict[str, float]:
        """获取选股日的收盘价（作为买入价）。"""
        prices = self._get_prices(date_str, cache)
        if not prices:
            # 尝试从 daily 数据中获取
            day_data = cache.get(date_str, {})
            for key, val in day_data.items():
                if isinstance(val, pd.DataFrame) and "close" in val.columns:
                    ts_col = "ts_code" if "ts_code" in val.columns else None
                    if ts_col:
                        for _, row in val.iterrows():
                            ts = str(row[ts_col])
                            try:
                                prices[ts] = float(row["close"])
                            except (ValueError, TypeError):
                                pass
                    break
        return prices
