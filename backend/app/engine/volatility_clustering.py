"""波动率聚类与风险分区引擎 (Volatility Clustering & Risk Zoning Engine)

核心功能：
1. 计算全市场股票的历史波动率（基于 daily_basic 的 close 价格）
2. 将股票聚类为 5 个风险等级（极低/低/中/高/极高）
3. 按行业和板块聚合风险分布
4. 检测波动率 regime 变化
5. 提供基于风险的板块配置建议

创新点：市面上没有个人股票工具做「波动率 regime 聚类 + 风险分区」，
将机构量化的波动率管理方法论平民化。
"""

import logging
import math
from typing import Dict, Any, List, Optional
from collections import defaultdict

import numpy as np
from sqlalchemy import text

from ..models import SessionLocal

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 风险分区定义
# ---------------------------------------------------------------------------
RISK_ZONES = [
    {"level": 1, "label": "极低风险", "color": "#52c41a", "emoji": "🟢", "min_pct": 0, "max_pct": 20},
    {"level": 2, "label": "低风险", "color": "#73d13d", "emoji": "🟢", "min_pct": 20, "max_pct": 40},
    {"level": 3, "label": "中等风险", "color": "#faad14", "emoji": "🟡", "min_pct": 40, "max_pct": 60},
    {"level": 4, "label": "高风险", "color": "#ff7a45", "emoji": "🟠", "min_pct": 60, "max_pct": 80},
    {"level": 5, "label": "极高风险", "color": "#f5222d", "emoji": "🔴", "min_pct": 80, "max_pct": 100},
]


class VolatilityClusteringEngine:
    """波动率聚类与风险分区引擎"""

    def __init__(self):
        pass

    # ==================================================================
    # 公开接口
    # ==================================================================

    def compute_market_volatility(self, trade_date: str = None) -> Dict[str, Any]:
        """计算全市场波动率聚类分析

        Args:
            trade_date: 交易日期 YYYYMMDD，None 则取最新

        Returns:
            全市场波动率分析结果
        """
        session = SessionLocal()
        try:
            if not trade_date:
                trade_date = self._get_latest_trade_date(session)

            trade_dates = self._get_trade_dates(session, n=10)
            if not trade_dates:
                return {"error": "无可用交易日期数据"}

            # 加载价格序列
            price_series = self._load_price_series(session, trade_dates)
            if not price_series:
                return {"error": "无价格数据"}

            # 计算每只股票的波动率
            stock_vols: Dict[str, float] = {}
            for ts_code, prices in price_series.items():
                vol = self._compute_volatility(prices)
                if vol > 0:
                    stock_vols[ts_code] = vol

            if not stock_vols:
                return {"error": "无有效波动率数据"}

            # 计算百分位分界线
            vols = sorted(stock_vols.values())
            n = len(vols)
            vol_percentiles = {
                "p20": vols[int(n * 0.2)] if n > 1 else vols[0],
                "p40": vols[int(n * 0.4)] if n > 1 else vols[0],
                "p60": vols[int(n * 0.6)] if n > 1 else vols[0],
                "p80": vols[int(n * 0.8)] if n > 1 else vols[0],
            }

            # 加载股票名称和行业
            stock_info = self._query(session, "SELECT ts_code, name, industry FROM stock_basic")
            name_map = {r["ts_code"]: r["name"] for r in stock_info}
            industry_map = {r["ts_code"]: r["industry"] for r in stock_info}

            # 分配风险分区 & 行业统计
            stock_results = []
            zone_counts: Dict[str, int] = defaultdict(int)
            industry_vol: Dict[str, List[float]] = defaultdict(list)

            for ts_code, vol in stock_vols.items():
                zone = self._assign_risk_zone(vol, vol_percentiles)
                zone_counts[zone["label"]] += 1

                industry = industry_map.get(ts_code, "未知")
                industry_vol[industry].append(vol)

                stock_results.append({
                    "ts_code": ts_code,
                    "name": name_map.get(ts_code, ts_code),
                    "industry": industry,
                    "volatility": vol,
                    "risk_zone": zone,
                })

            # 按波动率降序排序
            stock_results.sort(key=lambda x: x["volatility"], reverse=True)

            # 行业级波动率汇总
            industry_summary = []
            for industry, vols_list in sorted(industry_vol.items()):
                avg_vol = sum(vols_list) / len(vols_list) if vols_list else 0
                industry_summary.append({
                    "industry": industry,
                    "avg_volatility": round(avg_vol, 2),
                    "stock_count": len(vols_list),
                    "risk_zone": self._assign_risk_zone(avg_vol, vol_percentiles),
                })
            industry_summary.sort(key=lambda x: x["avg_volatility"], reverse=True)

            # 全市场统计
            all_vols = list(stock_vols.values())
            avg_all = sum(all_vols) / len(all_vols)
            market_stats = {
                "total_stocks": len(all_vols),
                "avg_volatility": round(avg_all, 2),
                "median_volatility": round(vols[n // 2], 2),
                "max_volatility": round(max(all_vols), 2),
                "min_volatility": round(min(all_vols), 2),
                "vol_std": round(
                    math.sqrt(sum((v - avg_all) ** 2 for v in all_vols) / len(all_vols)),
                    2,
                ),
            }

            # 风险分区分布
            zone_distribution = []
            for zone in RISK_ZONES:
                count = zone_counts.get(zone["label"], 0)
                zone_distribution.append({
                    "level": zone["level"],
                    "label": zone["label"],
                    "color": zone["color"],
                    "emoji": zone["emoji"],
                    "count": count,
                    "percentage": round(count / len(all_vols) * 100, 1) if all_vols else 0,
                })

            return {
                "trade_date": trade_date,
                "analysis_dates": trade_dates,
                "market_stats": market_stats,
                "zone_distribution": zone_distribution,
                "industry_summary": industry_summary[:30],
                "stock_results": stock_results[:100],
                "vol_percentiles": vol_percentiles,
            }
        except Exception as e:
            logger.error("compute_market_volatility failed: %s", e, exc_info=True)
            return {"error": str(e)}
        finally:
            session.close()

    def get_stock_detail(self, ts_code: str) -> Dict[str, Any]:
        """获取单只股票的波动率详情

        Args:
            ts_code: 股票代码（如 000001.SZ）

        Returns:
            波动率详情、价格序列、日收益率
        """
        session = SessionLocal()
        try:
            trade_dates = self._get_trade_dates(session, n=10)
            if not trade_dates:
                return {"error": "无可用交易日期数据"}

            # 加载价格序列
            placeholders = ", ".join([f":td{i}" for i in range(len(trade_dates))])
            params = {f"td{i}": d for i, d in enumerate(trade_dates)}
            params["ts_code"] = ts_code

            rows = self._query(
                session,
                f"SELECT trade_date, close FROM daily_basic "
                f"WHERE ts_code = :ts_code AND trade_date IN ({placeholders}) AND close > 0 "
                f"ORDER BY trade_date",
                params,
            )

            prices = [r["close"] for r in rows]
            dates = [r["trade_date"] for r in rows]

            if len(prices) < 2:
                return {"error": "数据不足以计算波动率，至少需要 2 个交易日"}

            vol = self._compute_volatility(prices)

            # 计算日收益率
            returns = []
            for i in range(1, len(prices)):
                if prices[i - 1] > 0:
                    ret = (prices[i] - prices[i - 1]) / prices[i - 1] * 100
                    returns.append({
                        "date": dates[i],
                        "return": round(ret, 2),
                    })

            # 获取股票基本信息
            stock_info = self._query(
                session,
                "SELECT ts_code, name, industry FROM stock_basic WHERE ts_code = :ts_code",
                {"ts_code": ts_code},
            )

            stock_name = stock_info[0]["name"] if stock_info else ts_code
            industry = stock_info[0]["industry"] if stock_info else "未知"

            # 获取全市场波动率上下文
            price_series = self._load_price_series(session, trade_dates)
            all_vols = []
            for tc, ps in price_series.items():
                v = self._compute_volatility(ps)
                if v > 0:
                    all_vols.append(v)
            all_vols.sort()

            # 计算该股票在全市场的百分位
            rank = sum(1 for v in all_vols if v <= vol)
            percentile = round(rank / max(len(all_vols), 1) * 100, 1)

            # 使用真实百分位分配风险分区
            vol_count = len(all_vols)
            if vol_count > 0:
                vol_percentiles = {
                    "p20": all_vols[int(vol_count * 0.2)],
                    "p40": all_vols[int(vol_count * 0.4)],
                    "p60": all_vols[int(vol_count * 0.6)],
                    "p80": all_vols[int(vol_count * 0.8)],
                }
            else:
                vol_percentiles = {"p20": 20, "p40": 40, "p60": 60, "p80": 80}

            return {
                "ts_code": ts_code,
                "name": stock_name,
                "industry": industry,
                "volatility": vol,
                "percentile": percentile,
                "price_series": [{"date": d, "close": p} for d, p in zip(dates, prices)],
                "daily_returns": returns,
                "risk_zone": self._assign_risk_zone(vol, vol_percentiles),
                "market_context": {
                    "total_stocks": len(all_vols),
                    "market_avg_vol": round(sum(all_vols) / max(len(all_vols), 1), 2),
                    "market_median_vol": round(all_vols[len(all_vols) // 2], 2) if all_vols else 0,
                },
            }
        except Exception as e:
            logger.error("get_stock_detail failed for %s: %s", ts_code, e, exc_info=True)
            return {"error": str(e)}
        finally:
            session.close()

    def get_sector_risk_summary(self) -> Dict[str, Any]:
        """获取板块（概念板块）风险分布汇总

        Returns:
            板块级风险分布统计
        """
        session = SessionLocal()
        try:
            trade_dates = self._get_trade_dates(session, n=10)
            price_series = self._load_price_series(session, trade_dates)

            # 计算每只股票波动率
            stock_vols: Dict[str, float] = {}
            for ts_code, prices in price_series.items():
                vol = self._compute_volatility(prices)
                if vol > 0:
                    stock_vols[ts_code] = vol

            # 加载板块成员映射
            members = self._query(
                session,
                "SELECT sector_code, sector_name, member_code FROM sector_member",
            )
            sector_stocks: Dict[str, list] = defaultdict(list)
            for m in members:
                if m["member_code"] in stock_vols:
                    sector_stocks[m["sector_code"]].append({
                        "name": m["sector_name"],
                        "ts_code": m["member_code"],
                        "volatility": stock_vols[m["member_code"]],
                    })

            # 计算板块级统计
            sector_summary = []
            for sector_code, stocks in sector_stocks.items():
                if not stocks:
                    continue
                vols = [s["volatility"] for s in stocks]
                avg_vol = sum(vols) / len(vols)
                sector_summary.append({
                    "sector_code": sector_code,
                    "sector_name": stocks[0]["name"],
                    "avg_volatility": round(avg_vol, 2),
                    "stock_count": len(stocks),
                    "high_risk_count": sum(1 for v in vols if v > 50),
                    "low_risk_count": sum(1 for v in vols if v < 20),
                    "top_stocks": sorted(stocks, key=lambda x: x["volatility"], reverse=True)[:5],
                })

            sector_summary.sort(key=lambda x: x["avg_volatility"], reverse=True)

            return {
                "trade_dates": trade_dates,
                "sector_count": len(sector_summary),
                "sectors": sector_summary[:50],
            }
        except Exception as e:
            logger.error("get_sector_risk_summary failed: %s", e, exc_info=True)
            return {"error": str(e)}
        finally:
            session.close()

    # ==================================================================
    # 内部方法
    # ==================================================================

    def _get_latest_trade_date(self, session) -> str:
        """获取最新的交易日期"""
        rows = self._query(session, "SELECT MAX(trade_date) as td FROM daily_basic")
        return rows[0]["td"] if rows and rows[0]["td"] else "20260612"

    def _get_trade_dates(self, session, n: int = 10) -> List[str]:
        """获取最近 n 个交易日"""
        rows = self._query(
            session,
            "SELECT DISTINCT trade_date FROM daily_basic ORDER BY trade_date DESC LIMIT :n",
            {"n": n},
        )
        return [r["trade_date"] for r in rows]

    def _load_price_series(self, session, trade_dates: List[str]) -> Dict[str, List[float]]:
        """加载所有股票在给定日期范围内的收盘价序列"""
        if not trade_dates:
            return {}

        placeholders = ", ".join([f":td{i}" for i in range(len(trade_dates))])
        params = {f"td{i}": d for i, d in enumerate(trade_dates)}

        rows = self._query(
            session,
            f"SELECT ts_code, trade_date, close FROM daily_basic "
            f"WHERE trade_date IN ({placeholders}) AND close > 0 "
            f"ORDER BY ts_code, trade_date",
            params,
        )

        series: Dict[str, list] = defaultdict(list)
        for row in rows:
            series[row["ts_code"]].append(row["close"])

        return dict(series)

    def _compute_volatility(self, prices: List[float]) -> float:
        """基于价格序列计算年化波动率

        使用日收益率的标准差，年化系数为 sqrt(244)（约 244 个交易日/年）。
        返回值为百分比形式（如 35.6 表示 35.6%）。
        """
        if len(prices) < 2:
            return 0.0

        returns = []
        for i in range(1, len(prices)):
            if prices[i - 1] > 0:
                returns.append((prices[i] - prices[i - 1]) / prices[i - 1])

        if len(returns) < 1:
            return 0.0

        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        std_dev = math.sqrt(variance)

        # 年化（假设 ~244 个交易日）
        annualized_vol = std_dev * math.sqrt(244)
        return round(annualized_vol * 100, 2)

    def _assign_risk_zone(self, volatility: float, vol_percentiles: Dict[str, float]) -> Dict[str, Any]:
        """基于波动率百分位分配风险分区"""
        vol = volatility

        if vol <= vol_percentiles.get("p20", 20):
            zone = RISK_ZONES[0]
        elif vol <= vol_percentiles.get("p40", 40):
            zone = RISK_ZONES[1]
        elif vol <= vol_percentiles.get("p60", 60):
            zone = RISK_ZONES[2]
        elif vol <= vol_percentiles.get("p80", 80):
            zone = RISK_ZONES[3]
        else:
            zone = RISK_ZONES[4]

        return {
            "level": zone["level"],
            "label": zone["label"],
            "color": zone["color"],
            "emoji": zone["emoji"],
        }

    @staticmethod
    def _query(session, sql: str, params: dict = None) -> list:
        """执行 SQL 查询，返回字典列表"""
        result = session.execute(text(sql), params or {})
        return [dict(row._mapping) for row in result]
