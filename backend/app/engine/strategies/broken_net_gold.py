"""破净股淘金——筛选股价低于净资产且有资金关注的股票。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class BrokenNetGold(BaseStrategy):
    name = "broken_net_gold"
    description = "PB<1破净但有资金流入，估值修复潜力大"
    category = "value"
    icon = "💎"

    def required_data(self) -> List[str]:
        return ["daily_basic", "moneyflow"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        db_df = data.get("daily_basic")
        mf_df = data.get("moneyflow")

        if db_df is None or db_df.empty:
            return []

        # 构建资金流向查找表: ts_code -> net_mf_amount
        flow_map = {}
        if mf_df is not None and not mf_df.empty:
            code_col_mf = self._find_col(mf_df, ["ts_code"])
            net_col_mf = self._find_col(mf_df, ["net_mf_amount"])
            if code_col_mf and net_col_mf:
                for _, row in mf_df.iterrows():
                    tc = str(row.get(code_col_mf, ""))
                    net = self._safe(row, net_col_mf)
                    if tc and net is not None:
                        flow_map[tc] = net

        # 找列名
        code_col = self._find_col(db_df, ["ts_code"])
        name_col = self._find_col(db_df, ["name"])
        pb_col = self._find_col(db_df, ["pb"])
        pe_col = self._find_col(db_df, ["pe_ttm", "pt"])
        dv_col = self._find_col(db_df, ["dv_ratio", "dr"])
        mv_col = self._find_col(db_df, ["total_mv", "tmv"])

        if not all([code_col, pb_col]):
            return []

        results = []
        for _, row in db_df.iterrows():
            pb = self._safe(row, pb_col)
            if pb is None or pb >= 1:
                continue  # 只看破净 (PB < 1)
            if pb <= 0:
                continue  # 排除异常值

            ts_code = str(row.get(code_col, ""))
            stock_name = str(row.get(name_col, "")) if name_col else ts_code

            # 排除 ST
            if "ST" in stock_name.upper():
                continue

            pe = self._safe(row, pe_col)
            if pe is None or pe <= 0 or pe >= 20:
                continue  # 不盈利或估值过高

            # 检查资金流入
            net_flow = flow_map.get(ts_code)
            if net_flow is None or net_flow <= 0:
                continue  # 没有资金流入

            dv = self._safe(row, dv_col)
            mv = self._safe(row, mv_col)

            # 评分
            # PB: 0.5以下满分30, 0.5-0.8递减
            pb_score = min(30, max(0, (1 - pb) * 40))
            # 资金净流入: 1000万=10, 5000万=20, 1亿+=30
            flow_score = min(30, net_flow / 10000 * 10)
            # 股息率: >3%=20, >1%=10
            dv_score = 0
            if dv is not None:
                if dv >= 3:
                    dv_score = 20
                elif dv >= 1:
                    dv_score = 10
            # PE: 越低越好
            pe_score = min(20, max(0, (20 - pe) / 20 * 20))

            total_score = pb_score + flow_score + dv_score + pe_score

            signals = {
                "pb": round(pb, 2),
                "pe_ttm": round(pe, 2),
                "net_mf_amount_wan": round(net_flow, 2),
            }
            if dv is not None:
                signals["dv_ratio"] = round(dv, 2)
            if mv is not None:
                signals["total_mv_yi"] = round(mv / 10000, 2)

            reason_parts = [f"PB={pb:.2f}(破净)", f"PE={pe:.2f}"]
            if dv is not None:
                reason_parts.append(f"股息率{dv:.1f}%")
            reason_parts.append(f"净流入{net_flow/10000:.2f}亿")

            results.append(StrategyResult(
                ts_code=ts_code,
                name=stock_name,
                score=min(100, total_score),
                signals=signals,
                reason="；".join(reason_parts),
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results
