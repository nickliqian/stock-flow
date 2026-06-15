"""内部人置信度策略——基于四维信号筛选高置信度标的。"""

from typing import List, Dict, Any
import pandas as pd

from ..base import BaseStrategy, StrategyResult
from ..registry import register


@register
class InsiderConvictionStrategy(BaseStrategy):
    name = "insider_conviction"
    description = "内部人与机构置信度信号——整合内部人买入、股东集中度、业绩预告、质押风险四维信号"
    category = "flow"
    icon = "🏛️"

    def required_data(self) -> List[str]:
        return ["stk_holdertrade", "stk_holdernumber", "top10_holders", "pledge_stat", "daily_basic"]

    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        insider_df = data.get("stk_holdertrade")
        holdernum_df = data.get("stk_holdernumber")
        top10_df = data.get("top10_holders")
        pledge_df = data.get("pledge_stat")
        basic_df = data.get("daily_basic")

        if (insider_df is None or insider_df.empty) and \
           (holdernum_df is None or holdernum_df.empty) and \
           (top10_df is None or top10_df.empty):
            return []

        # 构建 basic 映射
        basic_map = self._build_basic_map(basic_df)

        # 构建内部人交易映射
        insider_map = self._build_insider_map(insider_df)

        # 构建股东人数变动映射
        holder_num_map = self._build_holder_num_map(holdernum_df)

        # 构建前十大股东映射
        top10_map = self._build_top10_map(top10_df)

        # 构建质押映射
        pledge_map = self._build_pledge_map(pledge_df)

        # 合并所有有数据的股票
        all_codes = set()
        for m in [insider_map, holder_num_map, top10_map, pledge_map]:
            all_codes.update(m.keys())

        results = []
        for ts_code in all_codes:
            insider = insider_map.get(ts_code, {})
            hnum = holder_num_map.get(ts_code, {})
            top10 = top10_map.get(ts_code, {})
            pledge = pledge_map.get(ts_code, {})
            info = basic_map.get(ts_code, {})

            name = info.get("name", ts_code)
            insider_buy_count = insider.get("buy_count", 0)
            conviction_score = insider.get("conviction_score", 0)

            # 策略条件: conviction_score >= 60 且 insider_buying_count >= 2
            if conviction_score < 60 or insider_buy_count < 2:
                continue

            buy_consistency = insider.get("buy_consistency", 0)
            score = conviction_score * 0.8 + buy_consistency * 0.2

            signals = {
                "conviction_score": conviction_score,
                "insider_buy_count": insider_buy_count,
                "buy_consistency": buy_consistency,
                "net_buy_amount_wan": insider.get("net_buy_amount_wan", 0),
                "holder_count_change_pct": hnum.get("change_pct", 0),
                "top10_institutional_ratio": top10.get("institutional_ratio", 0),
                "pledge_ratio": pledge.get("pledge_ratio"),
            }

            reasons = []
            if insider_buy_count >= 2:
                reasons.append(f"内部人买入{insider_buy_count}次")
            if hnum.get("change_pct", 0) < -10:
                reasons.append("筹码集中")
            if top10.get("institutional_ratio", 0) > 15:
                reasons.append(f"机构占比{top10['institutional_ratio']:.1f}%")
            if pledge.get("pledge_ratio") is not None and pledge["pledge_ratio"] < 10:
                reasons.append(f"低质押{pledge['pledge_ratio']:.1f}%")

            results.append(StrategyResult(
                ts_code=ts_code,
                name=name,
                score=min(100, score),
                signals=signals,
                reason="；".join(reasons) if reasons else "综合置信度信号",
            ))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:50]

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _build_basic_map(self, basic_df) -> Dict[str, Dict]:
        result = {}
        if basic_df is None or basic_df.empty:
            return result
        code_col = self._find_col(basic_df, ["ts_code", "tc"])
        close_col = self._find_col(basic_df, ["close", "cl"])
        name_col = self._find_col(basic_df, ["name", "nm"])
        if not code_col:
            return result
        for _, r in basic_df.iterrows():
            tc = str(r.get(code_col, ""))
            result[tc] = {
                "close": self._safe(r, close_col) if close_col else None,
                "name": str(r.get(name_col, "")) if name_col else tc,
            }
        return result

    def _build_insider_map(self, df) -> Dict[str, Dict]:
        """构建内部人交易映射并计算初步置信度分数。"""
        result = {}
        if df is None or df.empty:
            return result
        code_col = self._find_col(df, ["ts_code", "tc"])
        if not code_col:
            return result

        for _, r in df.iterrows():
            tc = str(r.get(code_col, ""))
            if not tc:
                continue

            in_de = str(r.get("in_de", ""))
            change_vol = self._safe(r, self._find_col(df, ["change_vol", "cv"])) or 0
            avg_price = self._safe(r, self._find_col(df, ["avg_price", "ap"])) or 0
            amount = change_vol * avg_price

            is_buy = in_de == "IN"

            if tc not in result:
                result[tc] = {"buy_count": 0, "sell_count": 0, "net_buy_amount": 0, "buy_consistency": 0}

            entry = result[tc]
            if is_buy:
                entry["buy_count"] += 1
                entry["net_buy_amount"] += amount
            else:
                entry["sell_count"] += 1
                entry["net_buy_amount"] -= amount

        # 计算置信度分数
        for tc, entry in result.items():
            buy_count = entry["buy_count"]
            net = entry["net_buy_amount"]
            sc = 0
            if buy_count > 0 and net > 1_000_000:
                sc = min(100, 50 + (net / 1_000_000) * 10 + buy_count * 5)
            elif buy_count > 0:
                sc = min(60, 30 + buy_count * 5)
            if entry["sell_count"] > buy_count * 2:
                sc = max(0, sc - 30)
            entry["conviction_score"] = sc
            entry["net_buy_amount_wan"] = round(net / 10000, 2)
            if buy_count >= 3:
                entry["buy_consistency"] = min(100, buy_count * 20)
            elif buy_count >= 2:
                entry["buy_consistency"] = 60
            elif buy_count >= 1:
                entry["buy_consistency"] = 30
            else:
                entry["buy_consistency"] = 0

        return result

    def _build_holder_num_map(self, df) -> Dict[str, Dict]:
        result = {}
        if df is None or df.empty:
            return result
        code_col = self._find_col(df, ["ts_code", "tc"])
        if not code_col:
            return result
        for tc, group in df.groupby(code_col):
            group_sorted = group.sort_values("end_date")
            hn_col = self._find_col(group, ["holder_num", "hn"])
            ed_col = "end_date" if "end_date" in group.columns else None
            vals = []
            for _, r in group_sorted.iterrows():
                hn = self._safe(r, hn_col) if hn_col else None
                ed = str(r.get(ed_col, "")) if ed_col else ""
                if hn is not None and ed:
                    vals.append({"end_date": ed, "holder_num": int(hn)})
            if len(vals) < 2:
                result[tc] = {"change_pct": 0}
                continue
            earliest = vals[0]["holder_num"]
            latest = vals[-1]["holder_num"]
            change_pct = ((latest - earliest) / earliest * 100) if earliest > 0 else 0
            result[tc] = {"change_pct": round(change_pct, 2), "history": vals[-6:]}
        return result

    def _build_top10_map(self, df) -> Dict[str, Dict]:
        result = {}
        if df is None or df.empty:
            return result
        code_col = self._find_col(df, ["ts_code", "tc"])
        if not code_col:
            return result
        for tc, group in df.groupby(code_col):
            institutional_ratio = 0
            for _, r in group.iterrows():
                name = str(r.get("holder_name", ""))
                ratio = self._safe(r, self._find_col(group, ["hold_ratio", "hr"])) or 0
                is_inst = any(kw in name for kw in ("基金", "证券", "保险", "社保", "QFII", "券商", "资管", "信托"))
                if is_inst:
                    institutional_ratio += ratio
            result[tc] = {"institutional_ratio": round(institutional_ratio, 2)}
        return result

    def _build_pledge_map(self, df) -> Dict[str, Dict]:
        result = {}
        if df is None or df.empty:
            return result
        code_col = self._find_col(df, ["ts_code", "tc"])
        ratio_col = self._find_col(df, ["pledge_ratio", "pr"])
        if not code_col or not ratio_col:
            return result
        for _, r in df.iterrows():
            tc = str(r.get(code_col, ""))
            ratio = self._safe(r, ratio_col)
            if tc and ratio is not None:
                result[tc] = {"pledge_ratio": ratio}
        return result
