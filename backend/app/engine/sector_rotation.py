"""板块轮动雷达——分析板块资金流向趋势，检测轮动信号，发现早期轮入板块。"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from collections import defaultdict

from sqlalchemy import text

from ..models import SessionLocal
from ..cache import CacheService

logger = logging.getLogger(__name__)


class SectorRotationEngine:
    """板块轮动分析引擎。

    核心逻辑：
    1. 加载最近 N 个交易日的 sector_flow 数据
    2. 为每个板块计算轮动指标：
       - flow_trend: 资金流向趋势（正值=流入加速，负值=流出加速）
       - flow_momentum: 资金动量（最近一日 vs 前一日的变化）
       - rotation_score: 轮动综合评分（0-100）
    3. 检测轮动信号：
       - ROTATE_IN: 资金从流出转为流入（拐点信号）
       - ACCELERATE_IN: 持续流入且加速
       - ROTATE_OUT: 资金从流入转为流出
       - DECELERATE: 流入减速
       - NEUTRAL: 无明显信号
    4. 按轮动评分排序，找出最有价值的轮入板块
    """

    def __init__(self, cache: CacheService):
        self.cache = cache

    def analyze(
        self,
        trade_date: Optional[str] = None,
        lookback_days: int = 10,
        min_sectors: int = 5,
    ) -> Dict[str, Any]:
        """执行板块轮动分析。

        Args:
            trade_date: 截止日期，None 则取最新
            lookback_days: 回看天数
            min_sectors: 最少板块数（数据不足时降低阈值）

        Returns:
            包含 sectors、summary、signals 的完整分析结果
        """
        session = SessionLocal()
        try:
            # 1. 获取所有可用交易日
            dates_row = session.execute(
                text("SELECT DISTINCT trade_date FROM sector_flow ORDER BY trade_date DESC")
            ).fetchall()
            all_dates = [r[0] for r in dates_row]

            if not all_dates:
                return {"success": True, "data": {"sectors": [], "summary": {}, "signals": {}}}

            if trade_date and trade_date in all_dates:
                idx = all_dates.index(trade_date)
                target_dates = all_dates[idx: idx + lookback_days]
            else:
                target_dates = all_dates[:lookback_days]

            if len(target_dates) < 2:
                return {"success": True, "data": {"sectors": [], "summary": {"insufficient_data": True}, "signals": {}}}

            target_dates.sort()  # 升序

            # 2. 加载所有日期的 sector_flow 数据
            placeholders = ", ".join([f":d{i}" for i in range(len(target_dates))])
            params = {f"d{i}": d for i, d in enumerate(target_dates)}

            rows = session.execute(
                text(f"""
                    SELECT trade_date, sector_code, sector_name, net_inflow, large_net, large_pct
                    FROM sector_flow
                    WHERE trade_date IN ({placeholders})
                """),
                params,
            ).fetchall()

            # 3. 构建 {sector_code: {date: {net_inflow, large_net, large_pct}}}
            sector_data: Dict[str, Dict[str, Dict]] = defaultdict(dict)
            for r in rows:
                td, sc, sn, ni, ln, lp = r
                sector_data[sc][td] = {
                    "net_inflow": ni or 0,
                    "large_net": ln or 0,
                    "large_pct": lp or 0,
                    "sector_name": sn,
                }

            # 4. 计算每个板块的轮动指标
            results = []
            for sc, date_map in sector_data.items():
                if len(date_map) < 2:
                    continue

                # 按日期排序
                sorted_dates = sorted(date_map.keys())
                flows = [date_map[d]["net_inflow"] for d in sorted_dates]
                name = date_map[sorted_dates[-1]]["sector_name"]

                # 计算轮动指标
                metrics = self._compute_rotation_metrics(flows, sorted_dates)
                metrics["sector_code"] = sc
                metrics["sector_name"] = name
                metrics["latest_flow"] = flows[-1]
                metrics["latest_large_net"] = date_map[sorted_dates[-1]]["large_net"]
                metrics["latest_large_pct"] = date_map[sorted_dates[-1]]["large_pct"]
                metrics["history"] = [
                    {"date": d, "net_inflow": date_map[d]["net_inflow"]}
                    for d in sorted_dates
                ]

                results.append(metrics)

            # 5. 按轮动评分排序
            results.sort(key=lambda x: x["rotation_score"], reverse=True)

            # 6. 统计摘要
            total = len(results)
            rotate_in = sum(1 for r in results if r["signal"] == "ROTATE_IN")
            accelerate_in = sum(1 for r in results if r["signal"] == "ACCELERATE_IN")
            rotate_out = sum(1 for r in results if r["signal"] == "ROTATE_OUT")
            decelerate = sum(1 for r in results if r["signal"] == "DECELERATE")

            summary = {
                "total_sectors": total,
                "lookback_days": len(target_dates),
                "date_range": f"{target_dates[0]} ~ {target_dates[-1]}",
                "signals": {
                    "rotate_in": rotate_in,
                    "accelerate_in": accelerate_in,
                    "rotate_out": rotate_out,
                    "decelerate": decelerate,
                },
                "top_rotate_in": [
                    {"code": r["sector_code"], "name": r["sector_name"], "score": r["rotation_score"]}
                    for r in results if r["signal"] == "ROTATE_IN"
                ][:10],
            }

            return {
                "success": True,
                "data": {
                    "sectors": results[:100],  # 返回前100个
                    "summary": summary,
                    "trade_date": target_dates[-1],
                },
            }
        except Exception as exc:
            logger.error("SectorRotationEngine error: %s", exc, exc_info=True)
            return {"success": False, "error": str(exc)}
        finally:
            session.close()

    def get_sector_stocks(
        self,
        sector_code: str,
        trade_date: Optional[str] = None,
        limit: int = 30,
    ) -> Dict[str, Any]:
        """获取板块成分股及其资金流向。"""
        session = SessionLocal()
        try:
            # 获取成分股
            members = session.execute(
                text("""
                    SELECT member_code, member_name
                    FROM sector_member
                    WHERE sector_code = :sc
                """),
                {"sc": sector_code},
            ).fetchall()

            if not members:
                return {"success": True, "data": {"stocks": [], "sector_name": ""}}

            # 获取板块名称
            sector_name = ""
            sn_row = session.execute(
                text("SELECT sector_name FROM sector_flow WHERE sector_code = :sc LIMIT 1"),
                {"sc": sector_code},
            ).fetchone()
            if sn_row:
                sector_name = sn_row[0]

            # 获取最新交易日的资金流向
            if not trade_date:
                td_row = session.execute(
                    text("SELECT MAX(trade_date) FROM sector_flow")
                ).fetchone()
                trade_date = td_row[0] if td_row else None

            stocks = []
            for m in members:
                mc, mn = m[0], m[1]
                # 查找该股票在最新交易日的资金流向
                flow_row = session.execute(
                    text("""
                        SELECT net_amount, buy_lg_amount, buy_elg_amount, pct_change
                        FROM moneyflow_dc
                        WHERE ts_code = :tc AND trade_date = :td
                    """),
                    {"tc": mc, "td": trade_date},
                ).fetchone()

                stocks.append({
                    "ts_code": mc,
                    "name": mn,
                    "net_inflow": flow_row[0] if flow_row else None,
                    "large_buy": flow_row[1] if flow_row else None,
                    "huge_buy": flow_row[2] if flow_row else None,
                    "pct_change": flow_row[3] if flow_row else None,
                })

            # 按净流入排序
            stocks.sort(key=lambda x: x["net_inflow"] or 0, reverse=True)

            return {
                "success": True,
                "data": {
                    "sector_code": sector_code,
                    "sector_name": sector_name,
                    "trade_date": trade_date,
                    "stocks": stocks[:limit],
                    "total_members": len(members),
                },
            }
        except Exception as exc:
            logger.error("SectorRotation get_sector_stocks error: %s", exc, exc_info=True)
            return {"success": False, "error": str(exc)}
        finally:
            session.close()

    def _compute_rotation_metrics(self, flows: List[float], dates: List[str]) -> Dict[str, Any]:
        """计算板块的轮动指标。

        Args:
            flows: 按日期升序排列的资金流向序列
            dates: 对应的日期序列

        Returns:
            包含 rotation_score, signal, flow_trend, flow_momentum, details 的字典
        """
        n = len(flows)

        # --- 基础指标 ---
        latest = flows[-1]
        prev = flows[-2] if n >= 2 else 0
        avg_all = sum(flows) / n if n > 0 else 0
        avg_recent_3 = sum(flows[-3:]) / min(3, n) if n > 0 else 0

        # 资金动量 = 最近一日 vs 前一日的变化
        flow_momentum = latest - prev

        # 资金趋势 = 近3日均值 vs 全部均值
        flow_trend = avg_recent_3 - avg_all

        # --- 轮动信号检测 ---
        signal = "NEUTRAL"
        signal_detail = ""

        if n >= 3:
            # 检测拐点：前一日流出 + 最近一日流入
            if flows[-2] < 0 and flows[-1] > 0:
                signal = "ROTATE_IN"
                signal_detail = f"资金从流出({flows[-2]:.0f}万)转为流入({flows[-1]:.0f}万)"
            # 检测加速流入：连续流入且加速
            elif flows[-3] < flows[-2] < flows[-1] and flows[-1] > 0:
                signal = "ACCELERATE_IN"
                signal_detail = f"连续3日流入加速: {flows[-3]:.0f} → {flows[-2]:.0f} → {flows[-1]:.0f}"
            # 检测拐点：前一日流入 + 最近一日流出
            elif flows[-2] > 0 and flows[-1] < 0:
                signal = "ROTATE_OUT"
                signal_detail = f"资金从流入({flows[-2]:.0f}万)转为流出({flows[-1]:.0f}万)"
            # 检测减速流入
            elif flows[-2] > flows[-1] > 0:
                signal = "DECELERATE"
                signal_detail = f"流入减速: {flows[-2]:.0f} → {flows[-1]:.0f}"
        elif n >= 2:
            if flows[-2] < 0 and flows[-1] > 0:
                signal = "ROTATE_IN"
                signal_detail = f"资金从流出转为流入"
            elif flows[-2] > 0 and flows[-1] < 0:
                signal = "ROTATE_OUT"
                signal_detail = f"资金从流入转为流出"

        # --- 轮动评分 (0-100) ---
        score = 50.0  # 基准分

        # 信号加分
        signal_bonus = {
            "ROTATE_IN": 30,
            "ACCELERATE_IN": 25,
            "ROTATE_OUT": -20,
            "DECELERATE": -10,
            "NEUTRAL": 0,
        }
        score += signal_bonus.get(signal, 0)

        # 资金流入量加分（绝对值越大越好，但流入比流出好）
        if latest > 0:
            score += min(15, latest / 10000)  # 最多加15分
        else:
            score -= min(15, abs(latest) / 10000)

        # 趋势加分
        if flow_trend > 0:
            score += min(10, flow_trend / 5000)
        else:
            score -= min(10, abs(flow_trend) / 5000)

        # 动量加分
        if flow_momentum > 0:
            score += min(10, flow_momentum / 5000)
        else:
            score -= min(10, abs(flow_momentum) / 5000)

        # 限制在 0-100
        score = max(0, min(100, score))

        return {
            "rotation_score": round(score, 1),
            "signal": signal,
            "signal_detail": signal_detail,
            "flow_trend": round(flow_trend, 1),
            "flow_momentum": round(flow_momentum, 1),
            "avg_flow": round(avg_all, 1),
            "avg_recent_3": round(avg_recent_3, 1),
        }
