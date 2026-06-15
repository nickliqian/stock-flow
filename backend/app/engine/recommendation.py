"""智能荐股引擎——综合多维度分析生成可操作的股票推荐。"""

import json
import math
import logging
from typing import Dict, Any, List, Optional

from sqlalchemy import text

from ..models import SessionLocal
from ..cache import CacheService
from ..utils import get_latest_trade_date

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 维度权重
# ---------------------------------------------------------------------------
DIMENSION_WEIGHTS = {
    "strategy_signal": 0.25,
    "flow_intelligence": 0.20,
    "technical_momentum": 0.15,
    "fundamental_value": 0.15,
    "insider_conviction": 0.10,
    "crowding_risk": 0.10,
    "market_regime_fit": 0.05,
}

# 推荐级别阈值
RECOMMENDATION_LEVELS = [
    (70, "STRONG_BUY", "强推", "#52c41a"),
    (55, "BUY", "推荐", "#1890ff"),
    (40, "HOLD", "观望", "#faad14"),
    (25, "REDUCE", "减仓", "#fa8c16"),
    (0, "AVOID", "回避", "#f5222d"),
]

DIMENSION_LABELS = {
    "strategy_signal": ("策略信号", "\U0001f680"),
    "flow_intelligence": ("资金智慧", "\U0001f4b0"),
    "technical_momentum": ("技术动量", "\U0001f4c8"),
    "fundamental_value": ("基本面价值", "\U0001f48e"),
    "insider_conviction": ("内部人信念", "\U0001f3e6"),
    "crowding_risk": ("拥挤风险", "\U0001f465"),
    "market_regime_fit": ("市场适配", "\U0001f30d"),
}


class RecommendationEngine:
    """智能荐股引擎——综合7维度评分生成股票推荐。"""

    def __init__(self, cache: CacheService = None):
        self.cache = cache or CacheService()

    # ==================================================================
    # Public API
    # ==================================================================

    def get_recommendations(
        self,
        trade_date: Optional[str] = None,
        min_score: float = 0,
        limit: int = 50,
        category: Optional[str] = None,
    ) -> Dict[str, Any]:
        """获取推荐列表。"""
        try:
            if not trade_date:
                trade_date = get_latest_trade_date(self.cache)

            # 加载所有维度数据（一次性 SQL 查询，避免 N+1）
            flow_map = self._load_flow_data(trade_date)
            tech_map = self._load_tech_data(trade_date)
            fund_map = self._load_fundamental_data(trade_date)
            strategy_map = self._load_strategy_hits(trade_date)
            crowding_map = self._load_crowding_data(trade_date)
            insider_map = self._load_insider_data(trade_date)
            name_map = self._load_stock_names()
            regime = self._detect_regime(trade_date)

            # 收集所有出现过的股票代码
            all_codes = set()
            for m in [flow_map, tech_map, fund_map, strategy_map, insider_map]:
                all_codes.update(m.keys())

            if not all_codes:
                return {"success": True, "data": {"stocks": [], "summary": self._empty_summary(trade_date)}}

            # 计算每个股票的7维度评分
            stocks = []
            for ts_code in all_codes:
                name = name_map.get(ts_code, ts_code)
                dims = self._compute_dimensions(
                    ts_code, flow_map, tech_map, fund_map,
                    strategy_map, crowding_map, insider_map, regime,
                )
                composite = sum(dims[d]["score"] * DIMENSION_WEIGHTS[d] for d in DIMENSION_WEIGHTS)
                composite = round(min(100, max(0, composite)), 1)
                level, level_cn, level_color = self._get_level(composite)
                reasoning, risks = self._generate_reasoning(ts_code, dims, strategy_map)

                stocks.append({
                    "ts_code": ts_code,
                    "name": name,
                    "composite_score": composite,
                    "recommendation": level,
                    "recommendation_cn": level_cn,
                    "recommendation_color": level_color,
                    "dimensions": dims,
                    "strategies_hit": strategy_map.get(ts_code, {}).get("count", 0),
                    "strategy_names": strategy_map.get(ts_code, {}).get("names", []),
                    "reasoning": reasoning,
                    "risk_factors": risks,
                })

            # 按综合评分降序排序
            stocks.sort(key=lambda s: s["composite_score"], reverse=True)

            # 过滤和截断
            if min_score > 0:
                stocks = [s for s in stocks if s["composite_score"] >= min_score]
            stocks = stocks[:limit]

            # 添加排名
            for i, s in enumerate(stocks):
                s["rank"] = i + 1

            summary = self._build_summary(stocks, trade_date, len(all_codes))

            return {"success": True, "data": {"stocks": stocks, "summary": summary}}
        except Exception as exc:
            logger.error("get_recommendations failed: %s", exc, exc_info=True)
            return {"success": False, "error": str(exc)}

    def get_stock_recommendation(
        self, ts_code: str, trade_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取单只股票的详细推荐分析。"""
        try:
            if not trade_date:
                trade_date = get_latest_trade_date(self.cache)

            flow_map = self._load_flow_data(trade_date)
            tech_map = self._load_tech_data(trade_date)
            fund_map = self._load_fundamental_data(trade_date)
            strategy_map = self._load_strategy_hits(trade_date)
            crowding_map = self._load_crowding_data(trade_date)
            insider_map = self._load_insider_data(trade_date)
            name_map = self._load_stock_names()
            regime = self._detect_regime(trade_date)

            name = name_map.get(ts_code, ts_code)
            dims = self._compute_dimensions(
                ts_code, flow_map, tech_map, fund_map,
                strategy_map, crowding_map, insider_map, regime,
            )
            composite = sum(dims[d]["score"] * DIMENSION_WEIGHTS[d] for d in DIMENSION_WEIGHTS)
            composite = round(min(100, max(0, composite)), 1)
            level, level_cn, level_color = self._get_level(composite)
            reasoning, risks = self._generate_reasoning(ts_code, dims, strategy_map)

            # 补充原始数据摘要
            flow_data = flow_map.get(ts_code, {})
            tech_data = tech_map.get(ts_code, {})
            fund_data = fund_map.get(ts_code, {})

            return {
                "success": True,
                "data": {
                    "ts_code": ts_code,
                    "name": name,
                    "trade_date": trade_date,
                    "composite_score": composite,
                    "recommendation": level,
                    "recommendation_cn": level_cn,
                    "recommendation_color": level_color,
                    "dimensions": dims,
                    "strategies_hit": strategy_map.get(ts_code, {}).get("count", 0),
                    "strategy_names": strategy_map.get(ts_code, {}).get("names", []),
                    "reasoning": reasoning,
                    "risk_factors": risks,
                    "raw_data": {
                        "flow": {
                            "net_amount": flow_data.get("net_amount"),
                            "net_amount_rate": flow_data.get("net_amount_rate"),
                        },
                        "technical": {
                            "macd": tech_data.get("macd"),
                            "macd_dif": tech_data.get("macd_dif"),
                            "macd_dea": tech_data.get("macd_dea"),
                            "kdj_k": tech_data.get("kdj_k"),
                            "kdj_d": tech_data.get("kdj_d"),
                            "kdj_j": tech_data.get("kdj_j"),
                            "rsi_6": tech_data.get("rsi_6"),
                            "rsi_12": tech_data.get("rsi_12"),
                            "pct_change": tech_data.get("pct_change"),
                        },
                        "fundamental": {
                            "pe_ttm": fund_data.get("pe_ttm"),
                            "pb": fund_data.get("pb"),
                            "dv_ttm": fund_data.get("dv_ttm"),
                            "total_mv": fund_data.get("total_mv"),
                            "circ_mv": fund_data.get("circ_mv"),
                            "turnover_rate": fund_data.get("turnover_rate"),
                        },
                    },
                    "regime": regime,
                },
            }
        except Exception as exc:
            logger.error("get_stock_recommendation failed: %s", exc, exc_info=True)
            return {"success": False, "error": str(exc)}

    def get_recommendation_summary(
        self, trade_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取市场级推荐概要统计。"""
        try:
            if not trade_date:
                trade_date = get_latest_trade_date(self.cache)

            result = self.get_recommendations(trade_date=trade_date, limit=200)
            if not result.get("success"):
                return result

            stocks = result["data"]["stocks"]
            summary = result["data"]["summary"]

            # 额外的市场维度分析
            level_counts = {}
            for s in stocks:
                level = s["recommendation"]
                level_counts[level] = level_counts.get(level, 0) + 1

            # 平均各维度得分
            dim_avgs = {}
            for d in DIMENSION_WEIGHTS:
                scores = [s["dimensions"][d]["score"] for s in stocks if d in s.get("dimensions", {})]
                dim_avgs[d] = round(sum(scores) / len(scores), 1) if scores else 0

            return {
                "success": True,
                "data": {
                    "trade_date": trade_date,
                    "total_analyzed": summary.get("total_analyzed", len(stocks)),
                    "total_recommendations": len(stocks),
                    "level_distribution": {
                        "STRONG_BUY": level_counts.get("STRONG_BUY", 0),
                        "BUY": level_counts.get("BUY", 0),
                        "HOLD": level_counts.get("HOLD", 0),
                        "REDUCE": level_counts.get("REDUCE", 0),
                        "AVOID": level_counts.get("AVOID", 0),
                    },
                    "avg_composite_score": summary.get("avg_composite_score", 0),
                    "avg_dimension_scores": dim_avgs,
                    "top_picks": stocks[:5],
                    "market_sentiment": self._get_market_sentiment(stocks),
                },
            }
        except Exception as exc:
            logger.error("get_recommendation_summary failed: %s", exc, exc_info=True)
            return {"success": False, "error": str(exc)}

    # ==================================================================
    # Data Loading (batch SQL queries)
    # ==================================================================

    def _load_flow_data(self, trade_date: str) -> Dict[str, Dict]:
        """从 moneyflow_dc 加载资金流向数据。"""
        result = {}
        try:
            with self.cache._session() as session:
                rows = session.execute(
                    text("""
                        SELECT ts_code, net_amount, net_amount_rate,
                               buy_elg_amount, buy_lg_amount, buy_md_amount, buy_sm_amount
                        FROM moneyflow_dc WHERE trade_date = :td
                    """),
                    {"td": trade_date},
                ).fetchall()
                for r in rows:
                    m = dict(r._mapping)
                    result[m["ts_code"]] = m
        except Exception as exc:
            logger.debug("load_flow_data: %s", exc)
        return result

    def _load_tech_data(self, trade_date: str) -> Dict[str, Dict]:
        """从 stk_factor 加载技术指标数据。"""
        result = {}
        try:
            with self.cache._session() as session:
                rows = session.execute(
                    text("""
                        SELECT ts_code, macd, macd_dif, macd_dea,
                               kdj_k, kdj_d, kdj_j,
                               rsi_6, rsi_12, rsi_24,
                               close, pre_close, pct_change
                        FROM stk_factor WHERE trade_date = :td
                    """),
                    {"td": trade_date},
                ).fetchall()
                for r in rows:
                    m = dict(r._mapping)
                    result[m["ts_code"]] = m
        except Exception as exc:
            logger.debug("load_tech_data: %s", exc)
        return result

    def _load_fundamental_data(self, trade_date: str) -> Dict[str, Dict]:
        """从 daily_basic 加载基本面数据。"""
        result = {}
        try:
            with self.cache._session() as session:
                rows = session.execute(
                    text("""
                        SELECT ts_code, pe, pe_ttm, pb, ps_ttm,
                               dv_ratio, dv_ttm, total_mv, circ_mv,
                               turnover_rate, volume_ratio
                        FROM daily_basic WHERE trade_date = :td
                    """),
                    {"td": trade_date},
                ).fetchall()
                for r in rows:
                    m = dict(r._mapping)
                    result[m["ts_code"]] = m
        except Exception as exc:
            logger.debug("load_fundamental_data: %s", exc)
        return result

    def _load_strategy_hits(self, trade_date: str) -> Dict[str, Dict]:
        """从 strategy_snapshot 加载策略命中数据。"""
        result = {}
        try:
            with self.cache._session() as session:
                rows = session.execute(
                    text("""
                        SELECT strategy_name, top_picks, pick_count
                        FROM strategy_snapshot WHERE trade_date = :td
                    """),
                    {"td": trade_date},
                ).fetchall()
                for r in rows:
                    m = dict(r._mapping)
                    strategy_name = m["strategy_name"]
                    picks_raw = m.get("top_picks", "[]")
                    if isinstance(picks_raw, str):
                        try:
                            picks = json.loads(picks_raw)
                        except (json.JSONDecodeError, TypeError):
                            picks = []
                    else:
                        picks = picks_raw or []
                    for pick in picks:
                        code = pick.get("ts_code", "")
                        if not code:
                            continue
                        if code not in result:
                            result[code] = {"count": 0, "names": [], "details": []}
                        result[code]["count"] += 1
                        if strategy_name not in result[code]["names"]:
                            result[code]["names"].append(strategy_name)
                        result[code]["details"].append({
                            "strategy": strategy_name,
                            "score": pick.get("score", 0),
                            "reason": pick.get("reason", ""),
                        })
        except Exception as exc:
            logger.debug("load_strategy_hits: %s", exc)
        return result

    def _load_crowding_data(self, trade_date: str) -> Dict[str, float]:
        """从 strategy_snapshot 计算拥挤度。"""
        result = {}
        try:
            code_counts = {}
            with self.cache._session() as session:
                rows = session.execute(
                    text("""
                        SELECT strategy_name, top_picks
                        FROM strategy_snapshot WHERE trade_date = :td
                    """),
                    {"td": trade_date},
                ).fetchall()
                total_strategies = len(rows)
                if total_strategies == 0:
                    return result
                for r in rows:
                    m = dict(r._mapping)
                    picks_raw = m.get("top_picks", "[]")
                    if isinstance(picks_raw, str):
                        try:
                            picks = json.loads(picks_raw)
                        except (json.JSONDecodeError, TypeError):
                            picks = []
                    else:
                        picks = picks_raw or []
                    for pick in picks:
                        code = pick.get("ts_code", "")
                        if code:
                            code_counts[code] = code_counts.get(code, 0) + 1
                # 拥挤度 = 出现在多少策略中 / 总策略数 * 100
                for code, cnt in code_counts.items():
                    result[code] = round(cnt / total_strategies * 100, 1)
        except Exception as exc:
            logger.debug("load_crowding_data: %s", exc)
        return result

    def _load_insider_data(self, trade_date: str) -> Dict[str, Dict]:
        """从 stk_holdertrade 加载内部人交易数据。"""
        result = {}
        try:
            with self.cache._session() as session:
                rows = session.execute(
                    text("""
                        SELECT ts_code,
                               SUM(CASE WHEN in_de = :inc THEN 1 ELSE 0 END) as add_count,
                               SUM(CASE WHEN in_de = :dec THEN 1 ELSE 0 END) as reduce_count
                        FROM stk_holdertrade
                        WHERE end_date >= date(:td, '-30 days') AND end_date <= :td
                        GROUP BY ts_code
                    """),
                    {"td": trade_date, "inc": "增持", "dec": "减持"},
                ).fetchall()
                for r in rows:
                    m = dict(r._mapping)
                    add_c = m.get("add_count", 0) or 0
                    reduce_c = m.get("reduce_count", 0) or 0
                    result[m["ts_code"]] = {
                        "add_count": add_c,
                        "reduce_count": reduce_c,
                        "net_direction": 1 if add_c > reduce_c else (-1 if reduce_c > add_c else 0),
                    }
        except Exception as exc:
            logger.debug("load_insider_data: %s", exc)
        return result

    def _load_stock_names(self) -> Dict[str, str]:
        """从 stock_basic 加载股票名称。"""
        result = {}
        try:
            with self.cache._session() as session:
                rows = session.execute(
                    text("SELECT ts_code, name FROM stock_basic")
                ).fetchall()
                for r in rows:
                    m = dict(r._mapping)
                    result[m["ts_code"]] = m.get("name", "")
        except Exception as exc:
            logger.debug("load_stock_names: %s", exc)
        return result

    def _detect_regime(self, trade_date: str) -> str:
        """检测市场状态（简化版：基于市场宽度）。"""
        try:
            with self.cache._session() as session:
                row = session.execute(
                    text("""
                        SELECT
                            SUM(CASE WHEN pct_change > 0 THEN 1 ELSE 0 END) as up_count,
                            SUM(CASE WHEN pct_change < 0 THEN 1 ELSE 0 END) as down_count,
                            AVG(pct_change) as avg_change
                        FROM stk_factor WHERE trade_date = :td
                    """),
                    {"td": trade_date},
                ).fetchone()
                if row:
                    m = dict(row._mapping)
                    up = m.get("up_count", 0) or 0
                    down = m.get("down_count", 0) or 0
                    avg_chg = m.get("avg_change", 0) or 0
                    total = up + down
                    if total == 0:
                        return "sideways"
                    up_ratio = up / total
                    if up_ratio > 0.65 and avg_chg > 1.0:
                        return "bull"
                    elif up_ratio < 0.35 and avg_chg < -1.0:
                        return "bear"
                    elif up_ratio < 0.2 or up_ratio > 0.8:
                        return "extreme"
                    return "sideways"
        except Exception:
            pass
        return "sideways"

    # ==================================================================
    # Dimension Scoring
    # ==================================================================

    def _compute_dimensions(
        self, ts_code, flow_map, tech_map, fund_map,
        strategy_map, crowding_map, insider_map, regime,
    ) -> Dict[str, Dict]:
        """计算单只股票的7维度评分。"""
        dims = {}
        dims["strategy_signal"] = self._score_strategy(ts_code, strategy_map)
        dims["flow_intelligence"] = self._score_flow(ts_code, flow_map)
        dims["technical_momentum"] = self._score_technical(ts_code, tech_map)
        dims["fundamental_value"] = self._score_fundamental(ts_code, fund_map)
        dims["insider_conviction"] = self._score_insider(ts_code, insider_map)
        dims["crowding_risk"] = self._score_crowding(ts_code, crowding_map)
        dims["market_regime_fit"] = self._score_regime_fit(ts_code, regime, fund_map, tech_map)
        return dims

    def _score_strategy(self, ts_code: str, strategy_map: Dict) -> Dict:
        """策略信号评分：命中的策略数量 / 总策略数 * 100。"""
        info = strategy_map.get(ts_code, {})
        hit_count = info.get("count", 0)
        total = 22
        raw_score = (hit_count / total) * 100
        score = min(100, raw_score * 3)
        label, icon = DIMENSION_LABELS["strategy_signal"]
        return {
            "score": round(score, 1),
            "label": label,
            "icon": icon,
            "detail": f"命中 {hit_count}/{total} 个策略",
            "weight": DIMENSION_WEIGHTS["strategy_signal"],
        }

    def _score_flow(self, ts_code: str, flow_map: Dict) -> Dict:
        """资金智慧评分：基于 net_amount 方向和 magnitude。"""
        info = flow_map.get(ts_code, {})
        net_amount = info.get("net_amount", 0) or 0
        net_rate = info.get("net_amount_rate", 0) or 0
        buy_elg = info.get("buy_elg_amount", 0) or 0
        buy_lg = info.get("buy_lg_amount", 0) or 0

        score = 50  # 中性起点

        # 净流入方向
        if net_amount > 0:
            mag = min(3, math.log1p(abs(net_amount) / 1e6))
            score += mag * 10
        else:
            mag = min(3, math.log1p(abs(net_amount) / 1e6))
            score -= mag * 10

        # 大单占比加分
        if buy_elg > 0 and net_amount > 0:
            score += 5
        if buy_lg > 0 and net_amount > 0:
            score += 3

        # net_amount_rate 影响
        if net_rate > 5:
            score += 5
        elif net_rate < -5:
            score -= 5

        score = max(0, min(100, score))
        label, icon = DIMENSION_LABELS["flow_intelligence"]
        direction = "净流入" if net_amount > 0 else "净流出"
        amount_yi = abs(net_amount) / 1e4
        amount_str = f"{amount_yi:.2f}亿" if amount_yi >= 1 else f"{abs(net_amount):.0f}万"

        return {
            "score": round(score, 1),
            "label": label,
            "icon": icon,
            "detail": f"主力{direction} {amount_str}",
            "weight": DIMENSION_WEIGHTS["flow_intelligence"],
        }

    def _score_technical(self, ts_code: str, tech_map: Dict) -> Dict:
        """技术动量评分：MACD/KDJ/RSI综合。"""
        info = tech_map.get(ts_code, {})
        if not info:
            return {"score": 50, "label": DIMENSION_LABELS["technical_momentum"][0],
                    "icon": DIMENSION_LABELS["technical_momentum"][1],
                    "detail": "无技术数据", "weight": DIMENSION_WEIGHTS["technical_momentum"]}

        score = 50
        signals = []

        # MACD 金叉/死叉
        macd_dif = info.get("macd_dif", 0) or 0
        macd_dea = info.get("macd_dea", 0) or 0
        macd_val = info.get("macd", 0) or 0
        if macd_dif > macd_dea and macd_val > 0:
            score += 12
            signals.append("MACD金叉")
        elif macd_dif < macd_dea and macd_val < 0:
            score -= 10
            signals.append("MACD死叉")

        # KDJ 超卖/超买
        kdj_k = info.get("kdj_k", 50) or 50
        kdj_j = info.get("kdj_j", 50) or 50
        if kdj_k < 20 and kdj_j < 0:
            score += 10
            signals.append("KDJ超卖反弹")
        elif kdj_k > 80 and kdj_j > 100:
            score -= 10
            signals.append("KDJ超买")
        elif 30 <= kdj_k <= 70:
            score += 3

        # RSI 中性区加分
        rsi_6 = info.get("rsi_6", 50) or 50
        if 40 <= rsi_6 <= 60:
            score += 5
            signals.append("RSI中性")
        elif rsi_6 > 80:
            score -= 8
            signals.append("RSI超买")
        elif rsi_6 < 20:
            score += 8
            signals.append("RSI超卖")

        # 涨跌幅动量
        pct = info.get("pct_change", 0) or 0
        if pct > 3:
            score += 5
        elif pct < -3:
            score -= 5

        score = max(0, min(100, score))
        label, icon = DIMENSION_LABELS["technical_momentum"]
        detail = "，".join(signals) if signals else "无明显信号"
        return {
            "score": round(score, 1),
            "label": label,
            "icon": icon,
            "detail": detail,
            "weight": DIMENSION_WEIGHTS["technical_momentum"],
        }

    def _score_fundamental(self, ts_code: str, fund_map: Dict) -> Dict:
        """基本面价值评分：PE/PB/股息率/市值。"""
        info = fund_map.get(ts_code, {})
        if not info:
            return {"score": 50, "label": DIMENSION_LABELS["fundamental_value"][0],
                    "icon": DIMENSION_LABELS["fundamental_value"][1],
                    "detail": "无基本面数据", "weight": DIMENSION_WEIGHTS["fundamental_value"]}

        score = 50
        signals = []

        pe_ttm = info.get("pe_ttm", 0) or 0
        pb = info.get("pb", 0) or 0
        dv_ttm = info.get("dv_ttm", 0) or 0
        total_mv = info.get("total_mv", 0) or 0
        turnover = info.get("turnover_rate", 0) or 0

        # PE 吸引力
        if 0 < pe_ttm <= 15:
            score += 12
            signals.append(f"低PE({pe_ttm:.1f})")
        elif 15 < pe_ttm <= 30:
            score += 5
        elif pe_ttm > 80 or pe_ttm < 0:
            score -= 10
            signals.append(f"高/负PE({pe_ttm:.1f})")

        # PB
        if 0 < pb <= 1.5:
            score += 8
            signals.append(f"低PB({pb:.2f})")
        elif 1.5 < pb <= 3:
            score += 3
        elif pb > 8:
            score -= 5

        # 股息率
        if dv_ttm >= 3:
            score += 10
            signals.append(f"高股息({dv_ttm:.1f}%)")
        elif dv_ttm >= 1.5:
            score += 5

        # 市值适中加分（50-500亿）
        mv_yi = total_mv / 10000 if total_mv > 0 else 0
        if 50 <= mv_yi <= 500:
            score += 3
        elif mv_yi > 2000:
            score += 2

        # 换手率异常扣分
        if turnover > 15:
            score -= 5
            signals.append("换手率过高")
        elif 1 <= turnover <= 5:
            score += 2

        score = max(0, min(100, score))
        label, icon = DIMENSION_LABELS["fundamental_value"]
        detail = "，".join(signals) if signals else "基本面中性"
        return {
            "score": round(score, 1),
            "label": label,
            "icon": icon,
            "detail": detail,
            "weight": DIMENSION_WEIGHTS["fundamental_value"],
        }

    def _score_insider(self, ts_code: str, insider_map: Dict) -> Dict:
        """内部人信念评分：增减持方向。"""
        info = insider_map.get(ts_code, {})
        if not info:
            return {"score": 50, "label": DIMENSION_LABELS["insider_conviction"][0],
                    "icon": DIMENSION_LABELS["insider_conviction"][1],
                    "detail": "无内部人数据", "weight": DIMENSION_WEIGHTS["insider_conviction"]}

        net_dir = info.get("net_direction", 0)
        add_c = info.get("add_count", 0)
        reduce_c = info.get("reduce_count", 0)

        score = 50
        if net_dir > 0:
            score += min(30, add_c * 10)
        elif net_dir < 0:
            score -= min(30, reduce_c * 10)

        score = max(0, min(100, score))
        label, icon = DIMENSION_LABELS["insider_conviction"]
        if net_dir > 0:
            detail = f"净增持({add_c}增/{reduce_c}减)"
        elif net_dir < 0:
            detail = f"净减持({add_c}增/{reduce_c}减)"
        else:
            detail = "无增减持"
        return {
            "score": round(score, 1),
            "label": label,
            "icon": icon,
            "detail": detail,
            "weight": DIMENSION_WEIGHTS["insider_conviction"],
        }

    def _score_crowding(self, ts_code: str, crowding_map: Dict) -> Dict:
        """拥挤风险评分（反转）：出现在过多策略中 -> 风险高 -> 分数低。"""
        crowding_pct = crowding_map.get(ts_code, 0)

        score = max(10, 90 - crowding_pct * 1.4)

        label, icon = DIMENSION_LABELS["crowding_risk"]
        return {
            "score": round(score, 1),
            "label": label,
            "icon": icon,
            "detail": f"拥挤度 {crowding_pct:.1f}%",
            "weight": DIMENSION_WEIGHTS["crowding_risk"],
        }

    def _score_regime_fit(self, ts_code: str, regime: str, fund_map: Dict, tech_map: Dict) -> Dict:
        """市场适配评分：牛市偏好动量，熊市偏好价值。"""
        info = fund_map.get(ts_code, {})
        tech_info = tech_map.get(ts_code, {})
        score = 50

        if regime in ("bull", "extreme"):
            pct = tech_info.get("pct_change", 0) or 0
            if pct > 0:
                score += min(25, pct * 5)
            else:
                score -= min(15, abs(pct) * 3)
        elif regime == "bear":
            pe = info.get("pe_ttm", 0) or 0
            dv = info.get("dv_ttm", 0) or 0
            if 0 < pe <= 20:
                score += 15
            if dv >= 3:
                score += 10
        else:
            score = 55

        score = max(0, min(100, score))
        label, icon = DIMENSION_LABELS["market_regime_fit"]
        regime_cn = {"bull": "牛市", "bear": "熊市", "sideways": "震荡", "extreme": "极端"}.get(regime, regime)
        return {
            "score": round(score, 1),
            "label": label,
            "icon": icon,
            "detail": f"当前{regime_cn}市",
            "weight": DIMENSION_WEIGHTS["market_regime_fit"],
        }

    # ==================================================================
    # Reasoning & Risk Generation
    # ==================================================================

    def _get_level(self, score: float):
        """根据综合评分返回推荐级别。"""
        for threshold, level, cn, color in RECOMMENDATION_LEVELS:
            if score >= threshold:
                return level, cn, color
        return "AVOID", "回避", "#f5222d"

    def _generate_reasoning(self, ts_code, dims, strategy_map) -> tuple:
        """生成可读推理文本和风险因素。"""
        reasons = []
        risks = []

        # 策略命中
        info = strategy_map.get(ts_code, {})
        hit_count = info.get("count", 0)
        names = info.get("names", [])
        if hit_count > 0:
            from .base import STRATEGY_CATEGORIES
            cat_map = {}
            for cat, strats in STRATEGY_CATEGORIES.items():
                for s in strats:
                    cat_map[s] = cat
            cat_groups = {}
            for n in names:
                cat = cat_map.get(n, "other")
                if cat not in cat_groups:
                    cat_groups[cat] = []
                cat_groups[cat].append(n)

            cat_cn = {"value": "价值", "momentum": "动量", "flow": "资金", "event": "事件", "combo": "组合"}
            parts = []
            for cat, strats in cat_groups.items():
                if strats:
                    parts.append(f"{cat_cn.get(cat, cat)}×{len(strats)}")
            reasons.append(f"触发{hit_count}个策略({'+' .join(parts)})")

        # 资金流向
        flow_dim = dims.get("flow_intelligence", {})
        flow_score = flow_dim.get("score", 50)
        if flow_score > 65:
            reasons.append("主力资金净流入")
        elif flow_score < 35:
            risks.append("主力资金净流出")

        # 技术面
        tech_dim = dims.get("technical_momentum", {})
        tech_detail = tech_dim.get("detail", "")
        if "金叉" in tech_detail:
            reasons.append(tech_detail.split("，")[0])
        if "死叉" in tech_detail:
            risks.append(tech_detail.split("，")[0])
        if "超买" in tech_detail:
            risks.append(tech_detail.split("，")[0])
        if "超卖" in tech_detail:
            reasons.append(tech_detail.split("，")[0])

        # 基本面
        fund_dim = dims.get("fundamental_value", {})
        fund_detail = fund_dim.get("detail", "")
        if "低PE" in fund_detail or "高股息" in fund_detail:
            reasons.append(fund_detail.split("，")[0])

        # 内部人
        insider_dim = dims.get("insider_conviction", {})
        insider_detail = insider_dim.get("detail", "")
        if "净增持" in insider_detail:
            reasons.append("内部人增持")
        elif "净减持" in insider_detail:
            risks.append("内部人减持")

        # 拥挤风险
        crowding_dim = dims.get("crowding_risk", {})
        crowding_detail = crowding_dim.get("detail", "")
        if "拥挤度" in crowding_detail:
            try:
                pct_val = float(crowding_detail.split(" ")[1].replace("%", ""))
                if pct_val > 30:
                    risks.append(f"拥挤度较高({pct_val:.0f}%)")
            except (IndexError, ValueError):
                pass

        reasoning = "，".join(reasons) if reasons else "综合评分一般"
        return reasoning, risks

    # ==================================================================
    # Summary
    # ==================================================================

    def _build_summary(self, stocks: List[Dict], trade_date: str, total_analyzed: int) -> Dict:
        """构建推荐概要。"""
        if not stocks:
            return self._empty_summary(trade_date)

        level_dist = {"STRONG_BUY": 0, "BUY": 0, "HOLD": 0, "REDUCE": 0, "AVOID": 0}
        for s in stocks:
            level = s["recommendation"]
            if level in level_dist:
                level_dist[level] += 1

        avg_score = sum(s["composite_score"] for s in stocks) / len(stocks)

        return {
            "trade_date": trade_date,
            "total_analyzed": total_analyzed,
            "total_recommendations": len(stocks),
            "avg_composite_score": round(avg_score, 1),
            "level_distribution": level_dist,
        }

    def _empty_summary(self, trade_date: str) -> Dict:
        return {
            "trade_date": trade_date,
            "total_analyzed": 0,
            "total_recommendations": 0,
            "avg_composite_score": 0,
            "level_distribution": {"STRONG_BUY": 0, "BUY": 0, "HOLD": 0, "REDUCE": 0, "AVOID": 0},
        }

    def _get_market_sentiment(self, stocks: List[Dict]) -> str:
        """判断市场情绪。"""
        if not stocks:
            return "neutral"
        bullish = sum(1 for s in stocks if s["recommendation"] in ("STRONG_BUY", "BUY"))
        bearish = sum(1 for s in stocks if s["recommendation"] in ("REDUCE", "AVOID"))
        if bullish > bearish * 2:
            return "bullish"
        elif bearish > bullish * 2:
            return "bearish"
        return "neutral"
