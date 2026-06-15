"""板块轮动策略——筛选处于早期轮入板块中的优质个股。"""

from typing import List, Dict, Any
import pandas as pd
from sqlalchemy import text

from ..base import BaseStrategy, StrategyResult
from ..registry import register
from ...models import SessionLocal


@register
class SectorRotation(BaseStrategy):
    name = "sector_rotation"
    description = "板块轮动轮入：处于资金流入拐点板块中的资金共振个股"
    category = "flow"
    icon = "🔄"

    def required_data(self) -> List[str]:
        return ["daily_basic", "moneyflow_dc"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        daily_basic = data.get("daily_basic")
        moneyflow = data.get("moneyflow_dc")

        if daily_basic is None or daily_basic.empty:
            return []

        # 1. 获取轮入板块的成分股
        rotating_stocks = self._get_rotating_sector_stocks()
        if not rotating_stocks:
            return []

        # 2. 在轮入板块成分股中筛选
        results = []
        code_col = self._find_col(daily_basic, ["ts_code", "tc"])
        if not code_col:
            return []

        for _, row in daily_basic.iterrows():
            ts_code = row.get(code_col)
            if not ts_code or ts_code not in rotating_stocks:
                continue

            sector_info = rotating_stocks[ts_code]

            # 基础筛选：市值 > 20亿
            mv_col = self._find_col(daily_basic, ["total_mv", "tmv"])
            mv = self._safe(row, mv_col)
            if mv is None or mv < 200000:  # 万元单位，200000 = 20亿
                continue

            # 排除 ST
            name_col = self._find_col(daily_basic, ["name", "nm"])
            name = row.get(name_col, "") if name_col else ""
            if "ST" in str(name).upper():
                continue

            # 评分
            score = 50.0
            signals = {}

            # 板块轮动加分（板块评分越高，个股加分越多）
            sector_score = sector_info["sector_score"]
            score += min(25, sector_score / 4)
            signals["sector_score"] = sector_score
            signals["sector_name"] = sector_info["sector_name"]
            signals["sector_signal"] = sector_info["signal"]

            # 市值弹性加分（中小市值更受益于板块轮动）
            if mv and 200000 <= mv <= 5000000:  # 20亿-500亿
                score += 10
                signals["mv_bonus"] = True

            # 资金流向加分
            net_col = self._find_col(moneyflow, ["net_amount", "net_mf_amount"]) if moneyflow is not None and not moneyflow.empty else None
            if moneyflow is not None and not moneyflow.empty:
                mf_code_col = self._find_col(moneyflow, ["ts_code", "tc"])
                if mf_code_col and net_col:
                    mf_row = moneyflow[moneyflow[mf_code_col] == ts_code]
                    if not mf_row.empty:
                        net = mf_row.iloc[0].get(net_col)
                        if net is not None and net > 0:
                            score += min(15, net / 10000)
                            signals["net_inflow"] = round(float(net), 1)

            score = max(0, min(100, score))

            if score >= 55:  # 阈值
                results.append(StrategyResult(
                    ts_code=ts_code,
                    name=str(name),
                    score=score,
                    signals=signals,
                    reason=f"板块轮入({sector_info['sector_name']})+个股资金共振",
                ))

        return results

    def _get_rotating_sector_stocks(self) -> Dict[str, Dict]:
        """从数据库获取轮入板块的成分股。

        Returns:
            {ts_code: {"sector_name": str, "sector_score": float, "signal": str}}
        """
        session = SessionLocal()
        try:
            # 获取最近交易日
            td_row = session.execute(
                text("SELECT MAX(trade_date) FROM sector_flow")
            ).fetchone()
            if not td_row or not td_row[0]:
                return {}

            latest_date = td_row[0]

            # 获取所有可用日期
            dates = session.execute(
                text("SELECT DISTINCT trade_date FROM sector_flow ORDER BY trade_date DESC LIMIT 5")
            ).fetchall()
            dates = [r[0] for r in dates]

            if len(dates) < 2:
                return {}

            # 获取最近几天的 sector_flow 数据
            placeholders = ", ".join([f":d{i}" for i in range(len(dates))])
            params = {f"d{i}": d for i, d in enumerate(dates)}

            rows = session.execute(
                text(f"""
                    SELECT trade_date, sector_code, sector_name, net_inflow
                    FROM sector_flow
                    WHERE trade_date IN ({placeholders})
                    ORDER BY trade_date
                """),
                params,
            ).fetchall()

            # 按板块分组
            from collections import defaultdict
            sector_flows = defaultdict(list)
            sector_names = {}
            for r in rows:
                sector_flows[r[1]].append({"date": r[0], "net_inflow": r[2] or 0})
                sector_names[r[1]] = r[2]

            # 找出轮入板块（最近一日流入 + 前一日流出）
            rotating_sectors = []
            for sc, flow_list in sector_flows.items():
                if len(flow_list) < 2:
                    continue

                latest = flow_list[-1]["net_inflow"]
                prev = flow_list[-2]["net_inflow"]

                # 拐点信号：前一日流出 + 最近一日流入
                if prev < 0 and latest > 0:
                    rotating_sectors.append({
                        "sector_code": sc,
                        "sector_name": sector_names.get(sc, ""),
                        "sector_score": min(100, 50 + latest / 1000),
                        "signal": "ROTATE_IN",
                    })
                # 加速流入
                elif len(flow_list) >= 3:
                    f3 = flow_list[-3]["net_inflow"]
                    if f3 < flow_list[-2]["net_inflow"] < latest and latest > 0:
                        rotating_sectors.append({
                            "sector_code": sc,
                            "sector_name": sector_names.get(sc, ""),
                            "sector_score": min(100, 45 + latest / 1000),
                            "signal": "ACCELERATE_IN",
                        })

            if not rotating_sectors:
                return {}

            # 获取这些板块的成分股
            sector_codes = [s["sector_code"] for s in rotating_sectors]
            sector_map = {s["sector_code"]: s for s in rotating_sectors}

            placeholders2 = ", ".join([f":sc{i}" for i in range(len(sector_codes))])
            params2 = {f"sc{i}": sc for i, sc in enumerate(sector_codes)}

            members = session.execute(
                text(f"""
                    SELECT sector_code, member_code
                    FROM sector_member
                    WHERE sector_code IN ({placeholders2})
                """),
                params2,
            ).fetchall()

            result = {}
            for sc, mc in members:
                info = sector_map.get(sc, {})
                result[mc] = {
                    "sector_name": info.get("sector_name", ""),
                    "sector_score": info.get("sector_score", 50),
                    "signal": info.get("signal", "NEUTRAL"),
                }

            return result
        except Exception:
            return {}
        finally:
            session.close()
