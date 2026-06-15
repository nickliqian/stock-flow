"""协整配对交易引擎 (Cointegration Pair Trading Engine)

核心功能：
1. 配对发现：基于价格协整检验寻找统计套利机会
2. 信号生成：基于价差 z-score 的入场/出场信号
3. 回测引擎：验证配对交易策略的历史表现

创新点：市面上没有个人股票工具做「协整配对交易」，
这是将机构量化的统计套利方法论平民化。
"""

import logging
import json
import time
import math
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# 常量
DEFAULT_LOOKBACK_DAYS = 90
DEFAULT_MIN_CORRELATION = 0.7
DEFAULT_COTEGRATION_ALPHA = 0.05
DEFAULT_ZSCORE_ENTRY = 2.0
DEFAULT_ZSCORE_EXIT = 0.5
DEFAULT_MIN_MARKET_CAP = 50_0000  # 50亿（万元单位）
DEFAULT_UNIVERSE_SIZE = 80


class PairTradingEngine:
    """协整配对交易引擎"""

    def __init__(self, client, cache):
        self.client = client
        self.cache = cache

    # ================================================================
    # 公开方法
    # ================================================================

    def discover_pairs(
        self,
        trade_date: Optional[str] = None,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        min_correlation: float = DEFAULT_MIN_CORRELATION,
        significance: float = DEFAULT_COTEGRATION_ALPHA,
        min_market_cap: float = DEFAULT_MIN_MARKET_CAP,
        universe_size: int = DEFAULT_UNIVERSE_SIZE,
    ) -> Dict[str, Any]:
        """发现协整配对

        Returns:
            {
                "pairs": [...],  # 配对列表
                "summary": {...},  # 统计摘要
                "universe": [...],  # 股票池
            }
        """
        if not trade_date:
            trade_date = self._get_latest_trade_date()

        # Step 1: 构建股票池（按市值排序）
        universe = self._build_universe(trade_date, min_market_cap, universe_size)
        if len(universe) < 10:
            return {"pairs": [], "summary": {"error": "股票池太小"}, "universe": universe}

        # Step 2: 获取历史价格数据
        price_data = self._fetch_price_data(universe, lookback_days, trade_date)
        if price_data.empty:
            return {"pairs": [], "summary": {"error": "价格数据不足"}, "universe": universe}

        # Step 3: 计算收益率矩阵
        returns = price_data.pct_change().dropna()
        if len(returns) < 30:
            return {"pairs": [], "summary": {"error": "收益率数据不足30天"}, "universe": universe}

        # Step 4: 计算相关性矩阵
        corr_matrix = returns.corr()

        # Step 5: 寻找协整配对
        pairs = self._find_cointegrated_pairs(
            price_data, corr_matrix, min_correlation, significance
        )

        summary = {
            "trade_date": trade_date,
            "universe_size": len(universe),
            "lookback_days": lookback_days,
            "price_data_days": len(returns),
            "total_pairs_checked": len(universe) * (len(universe) - 1) // 2,
            "correlated_pairs": sum(
                1 for p in pairs if p.get("correlation", 0) >= min_correlation
            ),
            "cointegrated_pairs": len(pairs),
            "avg_correlation": (
                np.mean([p["correlation"] for p in pairs]) if pairs else 0
            ),
            "avg_cointegration_pvalue": (
                np.mean([p["cointegration_pvalue"] for p in pairs]) if pairs else 0
            ),
        }

        return {"pairs": pairs[:50], "summary": summary, "universe": universe}

    def get_pair_signals(
        self,
        trade_date: Optional[str] = None,
        lookback_days: int = DEFAULT_LOOKBACK_DAYS,
        zscore_entry: float = DEFAULT_ZSCORE_ENTRY,
        zscore_exit: float = DEFAULT_ZSCORE_EXIT,
        min_market_cap: float = DEFAULT_MIN_MARKET_CAP,
    ) -> Dict[str, Any]:
        """获取当前配对交易信号

        Returns:
            {
                "signals": [...],  # 信号列表
                "summary": {...},
            }
        """
        if not trade_date:
            trade_date = self._get_latest_trade_date()

        # 发现配对
        result = self.discover_pairs(
            trade_date=trade_date,
            lookback_days=lookback_days,
            min_market_cap=min_market_cap,
        )
        pairs = result.get("pairs", [])

        # 生成信号
        signals = []
        for pair in pairs:
            code1 = pair["code1"]
            code2 = pair["code2"]

            # 获取价差数据
            spread_info = self._compute_spread_signal(
                code1, code2, lookback_days, trade_date, zscore_entry, zscore_exit
            )
            if spread_info:
                spread_info["pair_info"] = pair
                signals.append(spread_info)

        # 按信号强度排序
        signals.sort(key=lambda x: abs(x.get("zscore", 0)), reverse=True)

        # 统计
        long_spread = [s for s in signals if s.get("signal") == "long_spread"]
        short_spread = [s for s in signals if s.get("signal") == "short_spread"]
        close_signal = [s for s in signals if s.get("signal") == "close"]

        summary = {
            "trade_date": trade_date,
            "total_pairs": len(pairs),
            "total_signals": len(signals),
            "long_spread_count": len(long_spread),
            "short_spread_count": len(short_spread),
            "close_count": len(close_signal),
            "strong_signals": len(
                [s for s in signals if abs(s.get("zscore", 0)) > 2.5]
            ),
        }

        return {"signals": signals[:30], "summary": summary}

    def backtest_pair(
        self,
        code1: str,
        code2: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        hold_days: int = 5,
        zscore_entry: float = DEFAULT_ZSCORE_ENTRY,
        zscore_exit: float = DEFAULT_ZSCORE_EXIT,
        initial_capital: float = 1_000_000,
    ) -> Dict[str, Any]:
        """回测单个配对交易

        Returns:
            {
                "pair": {...},
                "trades": [...],
                "metrics": {...},
                "equity_curve": [...],
            }
        """
        if not end_date:
            end_date = self._get_latest_trade_date()
        if not start_date:
            # 默认回测最近60个交易日
            start_date = self._shift_trade_date(end_date, -90)

        # 获取价格数据
        prices1 = self._fetch_single_stock_prices(code1, start_date, end_date)
        prices2 = self._fetch_single_stock_prices(code2, start_date, end_date)

        if prices1.empty or prices2.empty:
            return {
                "pair": {"code1": code1, "code2": code2},
                "trades": [],
                "metrics": {"error": "价格数据不足"},
                "equity_curve": [],
            }

        # 对齐日期
        aligned = pd.DataFrame(
            {code1: prices1.set_index("trade_date")["close"],
             code2: prices2.set_index("trade_date")["close"]}
        ).dropna()

        if len(aligned) < 30:
            return {
                "pair": {"code1": code1, "code2": code2},
                "trades": [],
                "metrics": {"error": "对齐后数据不足30天"},
                "equity_curve": [],
            }

        # 计算价差和 z-score
        spread = np.log(aligned[code1]) - np.log(aligned[code2])
        spread_mean = spread.rolling(window=20, min_periods=10).mean()
        spread_std = spread.rolling(window=20, min_periods=10).std()
        zscore = (spread - spread_mean) / spread_std.replace(0, np.nan)
        zscore = zscore.dropna()

        # 模拟交易
        trades = []
        equity = initial_capital
        equity_curve = []
        position = 0  # 0=空仓, 1=做多价差, -1=做空价差
        entry_date = None
        entry_zscore = 0

        for date, z in zscore.items():
            date_str = str(date)[:8] if hasattr(date, "strftime") else str(date)[:8]

            if position == 0:
                # 检查入场信号
                if z < -zscore_entry:
                    position = 1  # 做多价差（买code1卖code2）
                    entry_date = date
                    entry_zscore = z
                elif z > zscore_entry:
                    position = -1  # 做空价差（卖code1买code2）
                    entry_date = date
                    entry_zscore = z
            else:
                # 检查出场信号
                should_exit = False
                if position == 1 and z > -zscore_exit:
                    should_exit = True
                elif position == -1 and z < zscore_exit:
                    should_exit = True
                elif (date - entry_date).days >= hold_days:
                    should_exit = True

                if should_exit:
                    # 计算收益（简化：基于z-score变化）
                    pnl = position * (z - entry_zscore) * equity * 0.01
                    equity += pnl
                    trades.append({
                        "entry_date": str(entry_date)[:8],
                        "exit_date": date_str,
                        "direction": "long_spread" if position == 1 else "short_spread",
                        "entry_zscore": round(float(entry_zscore), 2),
                        "exit_zscore": round(float(z), 2),
                        "pnl": round(float(pnl), 2),
                        "return_pct": round(float(pnl / equity * 100), 2),
                    })
                    position = 0

            equity_curve.append({
                "date": date_str,
                "equity": round(float(equity), 2),
                "zscore": round(float(z), 3),
                "position": position,
            })

        # 计算性能指标
        metrics = self._compute_pair_metrics(trades, equity_curve, initial_capital)

        return {
            "pair": {"code1": code1, "code2": code2},
            "trades": trades,
            "metrics": metrics,
            "equity_curve": equity_curve[-60:],  # 最近60天
        }

    def get_pair_detail(
        self, code1: str, code2: str, lookback_days: int = 90
    ) -> Dict[str, Any]:
        """获取配对详情（价差、z-score、协整检验结果）"""
        trade_date = self._get_latest_trade_date()
        prices1 = self._fetch_single_stock_prices(
            code1,
            self._shift_trade_date(trade_date, -lookback_days),
            trade_date,
        )
        prices2 = self._fetch_single_stock_prices(
            code2,
            self._shift_trade_date(trade_date, -lookback_days),
            trade_date,
        )

        if prices1.empty or prices2.empty:
            return {"error": "价格数据不足"}

        # 对齐
        aligned = pd.DataFrame(
            {code1: prices1.set_index("trade_date")["close"],
             code2: prices2.set_index("trade_date")["close"]}
        ).dropna()

        if len(aligned) < 30:
            return {"error": "对齐后数据不足"}

        # 价差
        spread = np.log(aligned[code1]) - np.log(aligned[code2])
        spread_mean = spread.rolling(window=20, min_periods=10).mean()
        spread_std = spread.rolling(window=20, min_periods=10).std()
        zscore = (spread - spread_mean) / spread_std.replace(0, np.nan)

        # 协整检验
        from statsmodels.tsa.stattools import coint as coint_test
        try:
            score, pvalue, _ = coint_test(aligned[code1], aligned[code2])
        except Exception:
            score, pvalue = 0, 1

        # 相关性
        corr = aligned[code1].corr(aligned[code2])

        # 价差历史
        spread_history = []
        for date, val in spread.items():
            date_str = str(date)[:8] if hasattr(date, "strftime") else str(date)[:8]
            zs = float(zscore.get(date, 0)) if not pd.isna(zscore.get(date, np.nan)) else 0
            spread_history.append({
                "date": date_str,
                "spread": round(float(val), 4),
                "zscore": round(zs, 3),
                "price1": round(float(aligned.loc[date, code1]), 2),
                "price2": round(float(aligned.loc[date, code2]), 2),
            })

        return {
            "code1": code1,
            "code2": code2,
            "correlation": round(float(corr), 4),
            "cointegration_score": round(float(score), 4),
            "cointegration_pvalue": round(float(pvalue), 4),
            "is_cointegrated": pvalue < 0.05,
            "current_zscore": round(float(zscore.iloc[-1]), 3) if len(zscore) > 0 else 0,
            "spread_history": spread_history[-30:],
        }

    # ================================================================
    # 内部方法
    # ================================================================

    def _get_latest_trade_date(self) -> str:
        """获取最新交易日"""
        try:
            from ..utils import get_latest_trade_date
            return get_latest_trade_date(self.cache)
        except Exception:
            return datetime.now().strftime("%Y%m%d")

    def _shift_trade_date(self, date_str: str, days: int) -> str:
        """交易日期偏移"""
        from ..utils import get_last_n_trade_dates
        try:
            dates = get_last_n_trade_dates(self.cache, abs(days) + 10)
            if days < 0:
                dates = sorted(dates)
                target_idx = max(0, dates.index(date_str) + days) if date_str in dates else 0
                return dates[target_idx]
            else:
                dates = sorted(dates)
                target_idx = min(len(dates) - 1, dates.index(date_str) + days) if date_str in dates else len(dates) - 1
                return dates[target_idx]
        except Exception:
            dt = datetime.strptime(date_str, "%Y%m%d")
            dt += timedelta(days=days)
            return dt.strftime("%Y%m%d")

    def _build_universe(
        self, trade_date: str, min_market_cap: float, universe_size: int
    ) -> List[Dict]:
        """构建股票池（按市值排序的流动性好的股票）"""
        try:
            from ..models import SessionLocal, DailyBasic
            with SessionLocal() as session:
                rows = (
                    session.query(DailyBasic)
                    .filter(DailyBasic.trade_date == trade_date)
                    .filter(DailyBasic.total_mv >= min_market_cap)
                    .filter(DailyBasic.turnover_rate >= 0.5)  # 换手率>0.5%
                    .order_by(DailyBasic.total_mv.desc())
                    .limit(universe_size)
                    .all()
                )
                # 获取股票名称
                from ..models import StockBasic
                name_map = {}
                names = session.query(StockBasic).all()
                for n in names:
                    name_map[n.ts_code] = n.name

                universe = []
                for r in rows:
                    universe.append({
                        "ts_code": r.ts_code,
                        "name": name_map.get(r.ts_code, ""),
                        "total_mv": round(float(r.total_mv or 0), 2),
                        "close": round(float(r.close or 0), 2),
                        "pe_ttm": round(float(r.pe_ttm or 0), 2),
                        "pb": round(float(r.pb or 0), 2),
                        "turnover_rate": round(float(r.turnover_rate or 0), 2),
                    })
                return universe
        except Exception as exc:
            logger.error("Failed to build universe: %s", exc)
            return []

    def _fetch_price_data(
        self, universe: List[Dict], lookback_days: int, trade_date: str
    ) -> pd.DataFrame:
        """批量获取历史价格数据"""
        # 尝试从数据库获取
        try:
            from ..models import SessionLocal, DailyPrice
            start_date = self._shift_trade_date(trade_date, -lookback_days)

            ts_codes = [s["ts_code"] for s in universe]

            with SessionLocal() as session:
                rows = (
                    session.query(DailyPrice)
                    .filter(DailyPrice.trade_date >= start_date)
                    .filter(DailyPrice.trade_date <= trade_date)
                    .filter(DailyPrice.ts_code.in_(ts_codes))
                    .all()
                )
                if rows:
                    data = []
                    for r in rows:
                        data.append({
                            "trade_date": r.trade_date,
                            "ts_code": r.ts_code,
                            "close": float(r.close),
                        })
                    df = pd.DataFrame(data)
                    if len(df["ts_code"].unique()) >= 10:
                        pivot = df.pivot_table(
                            index="trade_date", columns="ts_code", values="close"
                        )
                        return pivot
        except Exception as exc:
            logger.warning("DB fetch failed, falling back to API: %s", exc)

        # 从 TuShare API 获取
        return self._fetch_price_data_from_api(universe, lookback_days, trade_date)

    def _fetch_price_data_from_api(
        self, universe: List[Dict], lookback_days: int, trade_date: str
    ) -> pd.DataFrame:
        """从 TuShare API 批量获取价格数据"""
        start_date = self._shift_trade_date(trade_date, -lookback_days)

        all_data = []
        for i, stock in enumerate(universe):
            ts_code = stock["ts_code"]
            try:
                df = self.client.get_daily(
                    ts_code=ts_code, start_date=start_date, end_date=trade_date
                )
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        all_data.append({
                            "trade_date": row["trade_date"],
                            "ts_code": ts_code,
                            "close": float(row["close"]),
                        })
                # 限流
                if i % 10 == 9:
                    time.sleep(0.5)
            except Exception as exc:
                logger.warning("Failed to fetch daily for %s: %s", ts_code, exc)
                continue

        if not all_data:
            return pd.DataFrame()

        df = pd.DataFrame(all_data)
        # 缓存到数据库
        self._cache_price_data(df)

        pivot = df.pivot_table(
            index="trade_date", columns="ts_code", values="close"
        )
        return pivot

    def _cache_price_data(self, df: pd.DataFrame):
        """缓存价格数据到数据库"""
        try:
            from ..models import SessionLocal, DailyPrice
            with SessionLocal() as session:
                for _, row in df.iterrows():
                    existing = (
                        session.query(DailyPrice)
                        .filter(
                            DailyPrice.trade_date == row["trade_date"],
                            DailyPrice.ts_code == row["ts_code"],
                        )
                        .first()
                    )
                    if not existing:
                        session.add(
                            DailyPrice(
                                trade_date=row["trade_date"],
                                ts_code=row["ts_code"],
                                open=row["close"],  # 简化
                                high=row["close"],
                                low=row["close"],
                                close=row["close"],
                                pre_close=row["close"],
                                change=0,
                                pct_chg=0,
                                vol=0,
                                amount=0,
                            )
                        )
                session.commit()
        except Exception as exc:
            logger.warning("Failed to cache price data: %s", exc)

    def _fetch_single_stock_prices(
        self, ts_code: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """获取单只股票的价格数据"""
        try:
            df = self.client.get_daily(
                ts_code=ts_code, start_date=start_date, end_date=end_date
            )
            if df is not None and not df.empty:
                return df[["trade_date", "close"]].copy()
        except Exception as exc:
            logger.warning("Failed to fetch prices for %s: %s", ts_code, exc)
        return pd.DataFrame()

    def _find_cointegrated_pairs(
        self,
        price_data: pd.DataFrame,
        corr_matrix: pd.DataFrame,
        min_correlation: float,
        significance: float,
    ) -> List[Dict]:
        """寻找协整配对"""
        from statsmodels.tsa.stattools import coint as coint_test

        stocks = list(price_data.columns)
        pairs = []

        for i in range(len(stocks)):
            for j in range(i + 1, len(stocks)):
                code1, code2 = stocks[i], stocks[j]

                # 检查相关性
                corr = corr_matrix.loc[code1, code2]
                if abs(corr) < min_correlation:
                    continue

                # 协整检验
                try:
                    s1 = price_data[code1].dropna()
                    s2 = price_data[code2].dropna()
                    common_dates = s1.index.intersection(s2.index)
                    if len(common_dates) < 30:
                        continue
                    score, pvalue, _ = coint_test(
                        s1.loc[common_dates], s2.loc[common_dates]
                    )
                except Exception:
                    continue

                if pvalue < significance:
                    # 计算价差统计
                    spread = np.log(s1.loc[common_dates]) - np.log(s2.loc[common_dates])
                    half_life = self._compute_half_life(spread)

                    pairs.append({
                        "code1": code1,
                        "code2": code2,
                        "correlation": round(float(corr), 4),
                        "cointegration_score": round(float(score), 4),
                        "cointegration_pvalue": round(float(pvalue), 6),
                        "half_life_days": round(float(half_life), 1) if half_life else None,
                        "spread_mean": round(float(spread.mean()), 4),
                        "spread_std": round(float(spread.std()), 4),
                    })

        # 按 p-value 排序（越小越好）
        pairs.sort(key=lambda x: x["cointegration_pvalue"])
        return pairs

    def _compute_half_life(self, spread: pd.Series) -> Optional[float]:
        """计算均值回复半衰期"""
        try:
            lagged = spread.shift(1).dropna()
            delta = spread.diff().dropna()
            common = lagged.index.intersection(delta.index)
            if len(common) < 10:
                return None
            X = lagged.loc[common].values.reshape(-1, 1)
            y = delta.loc[common].values
            from numpy.linalg import lstsq
            beta = lstsq(X, y, rcond=None)[0][0]
            if beta >= 0:
                return None  # 不均值回复
            half_life = -np.log(2) / beta
            return float(half_life)
        except Exception:
            return None

    def _compute_spread_signal(
        self,
        code1: str,
        code2: str,
        lookback_days: int,
        trade_date: str,
        zscore_entry: float,
        zscore_exit: float,
    ) -> Optional[Dict]:
        """计算配对价差信号"""
        try:
            start_date = self._shift_trade_date(trade_date, -lookback_days)

            prices1 = self._fetch_single_stock_prices(code1, start_date, trade_date)
            prices2 = self._fetch_single_stock_prices(code2, start_date, trade_date)

            if prices1.empty or prices2.empty:
                return None

            aligned = pd.DataFrame(
                {code1: prices1.set_index("trade_date")["close"],
                 code2: prices2.set_index("trade_date")["close"]}
            ).dropna()

            if len(aligned) < 30:
                return None

            spread = np.log(aligned[code1]) - np.log(aligned[code2])
            spread_mean = spread.rolling(window=20, min_periods=10).mean()
            spread_std = spread.rolling(window=20, min_periods=10).std()
            zscore = (spread - spread_mean) / spread_std.replace(0, np.nan)
            zscore = zscore.dropna()

            if len(zscore) == 0:
                return None

            current_zscore = float(zscore.iloc[-1])
            current_spread = float(spread.iloc[-1])

            # 判断信号
            if current_zscore < -zscore_entry:
                signal = "long_spread"
                signal_desc = f"做多价差：价差显著低于均值(z={current_zscore:.2f})"
            elif current_zscore > zscore_entry:
                signal = "short_spread"
                signal_desc = f"做空价差：价差显著高于均值(z={current_zscore:.2f})"
            elif abs(current_zscore) < zscore_exit:
                signal = "close"
                signal_desc = f"平仓信号：价差接近均值(z={current_zscore:.2f})"
            else:
                signal = "hold"
                signal_desc = f"持有：价差在正常范围内(z={current_zscore:.2f})"

            return {
                "code1": code1,
                "code2": code2,
                "zscore": round(current_zscore, 3),
                "spread": round(current_spread, 4),
                "signal": signal,
                "signal_desc": signal_desc,
                "price1": round(float(aligned[code1].iloc[-1]), 2),
                "price2": round(float(aligned[code2].iloc[-1]), 2),
                "ratio": round(float(aligned[code1].iloc[-1] / aligned[code2].iloc[-1]), 4),
            }
        except Exception as exc:
            logger.warning("Failed to compute spread signal: %s", exc)
            return None

    def _compute_pair_metrics(
        self, trades: List[Dict], equity_curve: List[Dict], initial_capital: float
    ) -> Dict:
        """计算配对交易性能指标"""
        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0,
                "total_return": 0,
                "max_drawdown": 0,
                "sharpe_ratio": 0,
                "profit_factor": 0,
            }

        wins = [t for t in trades if t["pnl"] > 0]
        losses = [t for t in trades if t["pnl"] <= 0]

        total_return = (equity_curve[-1]["equity"] / initial_capital - 1) * 100 if equity_curve else 0

        # 最大回撤
        peak = initial_capital
        max_dd = 0
        for pt in equity_curve:
            if pt["equity"] > peak:
                peak = pt["equity"]
            dd = (peak - pt["equity"]) / peak
            if dd > max_dd:
                max_dd = dd

        # 夏普比率
        returns = []
        for i in range(1, len(equity_curve)):
            prev = equity_curve[i - 1]["equity"]
            curr = equity_curve[i]["equity"]
            if prev > 0:
                returns.append(curr / prev - 1)
        avg_return = np.mean(returns) if returns else 0
        std_return = np.std(returns) if returns else 1
        sharpe = (avg_return / std_return * np.sqrt(252)) if std_return > 0 else 0

        # 盈亏比
        avg_win = np.mean([t["pnl"] for t in wins]) if wins else 0
        avg_loss = abs(np.mean([t["pnl"] for t in losses])) if losses else 1
        profit_factor = avg_win / avg_loss if avg_loss > 0 else 0

        return {
            "total_trades": len(trades),
            "win_count": len(wins),
            "loss_count": len(losses),
            "win_rate": round(len(wins) / len(trades) * 100, 1) if trades else 0,
            "total_return": round(total_return, 2),
            "max_drawdown": round(max_dd * 100, 2),
            "sharpe_ratio": round(float(sharpe), 3),
            "profit_factor": round(float(profit_factor), 2),
            "avg_win": round(float(avg_win), 2),
            "avg_loss": round(float(avg_loss), 2),
            "final_equity": round(float(equity_curve[-1]["equity"]), 2) if equity_curve else initial_capital,
        }
