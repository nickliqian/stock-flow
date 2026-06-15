"""多因子 Alpha 评分引擎 — 行业内百分位排名的多因子评分系统。

核心逻辑：
1. 5 大因子：价值(Value)、动量(Momentum)、资金(Flow)、质量(Quality)、规模(Size)
2. 每个因子在行业内做百分位排名（行业相对排名）
3. Composite Alpha = Value(30%) + Momentum(25%) + Flow(25%) + Quality(10%) + Size(10%)
4. 行业百分位 = 行业内排名 / 行业股票数 * 100

数据源：
- daily_basic: PE/PB/换手率/总市值/流通市值/股息率/量比
- stk_factor: RSI/MACD/KDJ/布林带/收盘价
- moneyflow_dc / stock_flow: 资金流向
- stock_basic: 行业分类
"""

import logging
import math
from typing import Dict, Any, List, Optional
from collections import defaultdict

import numpy as np
import pandas as pd
from sqlalchemy import text

from ..models import SessionLocal, DailyBasic, StkFactor, StockBasic

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 因子权重
# ------------------------------------------------------------------
FACTOR_WEIGHTS = {
    "value": 0.30,
    "momentum": 0.25,
    "flow": 0.25,
    "quality": 0.10,
    "size": 0.10,
}

FACTOR_META = {
    "value": {"name": "价值因子", "icon": "💎", "description": "低估值、高股息"},
    "momentum": {"name": "动量因子", "icon": "🚀", "description": "趋势与技术动量"},
    "flow": {"name": "资金因子", "icon": "💰", "description": "主力资金净流入"},
    "quality": {"name": "质量因子", "icon": "⭐", "description": "换手率适中、市值稳健"},
    "size": {"name": "规模因子", "icon": "🏢", "description": "市值规模"},
}

# 行业内最少需要多少只股票才计算百分位
MIN_INDUSTRY_SIZE = 5


class AlphaScoringEngine:
    """多因子 Alpha 评分引擎。

    行业相对排名的多因子评分系统，在行业内计算百分位排名，
    使不同行业的股票具有可比性。
    """

    def __init__(self):
        pass

    # ==================================================================
    # 公开接口
    # ==================================================================

    def get_market_alpha_scores(
        self,
        trade_date: Optional[str] = None,
        industry: Optional[str] = None,
        min_mv: float = 20,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """获取全市场行业调整后的 Alpha 评分排名。

        Args:
            trade_date: 交易日期 YYYYMMDD，None 则取最新
            industry: 指定行业筛选，None 为全市场
            min_mv: 最小总市值（亿元），默认 20 亿
            limit: 返回股票数量上限，默认 50

        Returns:
            {"trade_date": "...", "summary": {...}, "stocks": [...]}
        """
        session = SessionLocal()
        try:
            # 获取目标交易日
            if trade_date is None:
                row = session.execute(
                    text("SELECT MAX(trade_date) FROM daily_basic")
                ).fetchone()
                if not row or not row[0]:
                    return {"error": "无可用数据"}
                trade_date = row[0]

            # 加载数据
            stock_df = self._load_stock_data(session, trade_date)
            if stock_df.empty:
                return {"trade_date": trade_date, "summary": {}, "stocks": []}

            # 按市值过滤（min_mv 单位为亿元，total_mv 单位为万元）
            min_mv_wan = min_mv * 10000
            stock_df = stock_df[stock_df["total_mv"] >= min_mv_wan].copy()
            if stock_df.empty:
                return {"trade_date": trade_date, "summary": {}, "stocks": []}

            # 行业筛选
            if industry:
                stock_df = stock_df[stock_df["industry"] == industry].copy()
                if stock_df.empty:
                    return {"trade_date": trade_date, "summary": {}, "stocks": []}

            # 计算各因子得分
            scored_df = self._compute_all_factor_scores(stock_df)
            if scored_df.empty:
                return {"trade_date": trade_date, "summary": {}, "stocks": []}

            # 计算 Composite Alpha
            scored_df["alpha_score"] = self._compute_composite_alpha(scored_df)

            # 排序取 top
            scored_df = scored_df.sort_values("alpha_score", ascending=False).head(limit)

            # 构建结果
            stocks = self._format_stock_list(scored_df)

            # 汇总统计
            summary = self._build_summary(scored_df)

            return {
                "trade_date": trade_date,
                "min_mv": min_mv,
                "industry_filter": industry,
                "summary": summary,
                "stocks": stocks,
            }
        except Exception as e:
            logger.error("get_market_alpha_scores failed: %s", e, exc_info=True)
            return {"error": str(e)}
        finally:
            session.close()

    def get_stock_alpha_profile(
        self, ts_code: str, trade_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取单只股票的详细 Alpha 画像，包含行业内各因子百分位。

        Args:
            ts_code: 股票代码（如 000001.SZ）
            trade_date: 交易日期 YYYYMMDD，None 则取最新

        Returns:
            {"ts_code": "...", "name": "...", "industry": "...",
             "alpha_score": ..., "factors": {...}, "peer_rank": ...}
        """
        session = SessionLocal()
        try:
            if trade_date is None:
                row = session.execute(
                    text("SELECT MAX(trade_date) FROM daily_basic")
                ).fetchone()
                if not row or not row[0]:
                    return {"error": "无可用数据"}
                trade_date = row[0]

            # 加载全量数据（用于行业百分位计算）
            stock_df = self._load_stock_data(session, trade_date)
            if stock_df.empty:
                return {"error": f"交易日 {trade_date} 无数据"}

            # 检查目标股票是否存在
            target = stock_df[stock_df["ts_code"] == ts_code]
            if target.empty:
                return {"error": f"未找到股票 {ts_code} 的数据"}

            # 计算各因子得分
            scored_df = self._compute_all_factor_scores(stock_df)
            if scored_df.empty:
                return {"error": "因子得分计算失败"}

            # 计算 Composite Alpha
            scored_df["alpha_score"] = self._compute_composite_alpha(scored_df)

            # 提取目标股票数据
            target_row = scored_df[scored_df["ts_code"] == ts_code].iloc[0]
            industry = target_row.get("industry", "")
            target_industry = scored_df[scored_df["industry"] == industry]
            total_in_industry = len(target_industry)
            rank_in_industry = target_industry["alpha_score"].rank(ascending=False).iloc[
                target_industry.index.get_loc(target_row.name)
            ]

            # 构建详细 profile
            profile = {
                "ts_code": ts_code,
                "name": target_row.get("name", ts_code),
                "industry": industry,
                "trade_date": trade_date,
                "alpha_score": round(float(target_row["alpha_score"]), 2),
                "factors": {},
                "peer_comparison": {
                    "industry": industry,
                    "peer_count": total_in_industry,
                    "rank_in_industry": int(rank_in_industry),
                    "percentile": round(
                        (1 - rank_in_industry / total_in_industry) * 100, 1
                    )
                    if total_in_industry > 0
                    else 0,
                },
            }

            # 各因子详情
            for factor_name in FACTOR_WEIGHTS:
                score_col = f"{factor_name}_score"
                pct_col = f"{factor_name}_pctile"
                weight = FACTOR_WEIGHTS[factor_name]
                raw_score = target_row.get(score_col, 50.0)
                pctile = target_row.get(pct_col, 50.0)

                profile["factors"][factor_name] = {
                    "name": FACTOR_META[factor_name]["name"],
                    "icon": FACTOR_META[factor_name]["icon"],
                    "weight": weight,
                    "score": round(float(raw_score), 2),
                    "percentile": round(float(pctile), 1),
                    "weighted_contribution": round(float(raw_score * weight), 2),
                }

            # 行业内原始指标
            raw_cols = [
                "pe_ttm", "pb", "dv_ttm", "turnover_rate", "total_mv",
                "circ_mv", "volume_ratio", "rsi_12", "macd",
            ]
            raw_values = {}
            for col in raw_cols:
                if col in target_row.index:
                    val = target_row[col]
                    if pd.notna(val):
                        raw_values[col] = round(float(val), 4)
                    else:
                        raw_values[col] = None
                else:
                    raw_values[col] = None
            profile["raw_metrics"] = raw_values

            return profile
        except Exception as e:
            logger.error(
                "get_stock_alpha_profile failed for %s: %s", ts_code, e, exc_info=True
            )
            return {"error": str(e)}
        finally:
            session.close()

    def get_industry_heatmap(
        self, trade_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取行业级别的聚合指标热力图。

        每个行业的平均 PE、平均动量、净资金流、平均 Alpha 等。

        Returns:
            {"trade_date": "...", "industries": [{industry, avg_pe, avg_alpha, ...}]}
        """
        session = SessionLocal()
        try:
            if trade_date is None:
                row = session.execute(
                    text("SELECT MAX(trade_date) FROM daily_basic")
                ).fetchone()
                if not row or not row[0]:
                    return {"error": "无可用数据"}
                trade_date = row[0]

            # 加载数据
            stock_df = self._load_stock_data(session, trade_date)
            if stock_df.empty:
                return {"trade_date": trade_date, "industries": []}

            # 过滤无行业的股票
            stock_df = stock_df[stock_df["industry"].notna() & (stock_df["industry"] != "")]
            if stock_df.empty:
                return {"trade_date": trade_date, "industries": []}

            # 计算因子得分
            scored_df = self._compute_all_factor_scores(stock_df)
            scored_df["alpha_score"] = self._compute_composite_alpha(scored_df)

            # 按行业聚合
            industries = []
            for industry_name, group in scored_df.groupby("industry"):
                if len(group) < MIN_INDUSTRY_SIZE:
                    continue

                avg_pe = self._safe_mean(group, "pe_ttm")
                avg_pb = self._safe_mean(group, "pb")
                avg_dv = self._safe_mean(group, "dv_ttm")
                avg_mv = self._safe_mean(group, "total_mv")
                avg_turnover = self._safe_mean(group, "turnover_rate")
                avg_alpha = self._safe_mean(group, "alpha_score")
                avg_value = self._safe_mean(group, "value_score")
                avg_momentum = self._safe_mean(group, "momentum_score")
                avg_flow = self._safe_mean(group, "flow_score")
                avg_quality = self._safe_mean(group, "quality_score")
                avg_size = self._safe_mean(group, "size_score")

                industries.append({
                    "industry": industry_name,
                    "stock_count": len(group),
                    "avg_pe_ttm": round(avg_pe, 2),
                    "avg_pb": round(avg_pb, 2),
                    "avg_dividend_yield": round(avg_dv, 2),
                    "avg_market_cap_yi": round(avg_mv / 10000, 2) if avg_mv else 0,
                    "avg_turnover_rate": round(avg_turnover, 2),
                    "avg_alpha_score": round(avg_alpha, 2),
                    "factor_averages": {
                        "value": round(avg_value, 2),
                        "momentum": round(avg_momentum, 2),
                        "flow": round(avg_flow, 2),
                        "quality": round(avg_quality, 2),
                        "size": round(avg_size, 2),
                    },
                })

            # 按平均 Alpha 降序排列
            industries.sort(key=lambda x: x["avg_alpha_score"], reverse=True)

            return {
                "trade_date": trade_date,
                "industry_count": len(industries),
                "industries": industries,
            }
        except Exception as e:
            logger.error("get_industry_heatmap failed: %s", e, exc_info=True)
            return {"error": str(e)}
        finally:
            session.close()

    def get_peer_comparison(
        self, ts_code: str, trade_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取目标股票与同行业 peers 的对比表。

        Args:
            ts_code: 股票代码
            trade_date: 交易日期

        Returns:
            {"target": {...}, "peers": [...], "peer_avg": {...}}
        """
        session = SessionLocal()
        try:
            if trade_date is None:
                row = session.execute(
                    text("SELECT MAX(trade_date) FROM daily_basic")
                ).fetchone()
                if not row or not row[0]:
                    return {"error": "无可用数据"}
                trade_date = row[0]

            # 加载数据
            stock_df = self._load_stock_data(session, trade_date)
            if stock_df.empty:
                return {"error": f"交易日 {trade_date} 无数据"}

            # 检查目标股票
            target = stock_df[stock_df["ts_code"] == ts_code]
            if target.empty:
                return {"error": f"未找到股票 {ts_code} 的数据"}

            industry = target.iloc[0].get("industry", "")
            if not industry:
                return {"error": f"股票 {ts_code} 无行业分类"}

            # 筛选同行业股票
            industry_df = stock_df[stock_df["industry"] == industry].copy()
            if len(industry_df) < 2:
                return {
                    "error": f"行业 '{industry}' 内不足 2 只股票，无法比较",
                    "ts_code": ts_code,
                    "industry": industry,
                }

            # 计算因子得分
            scored_df = self._compute_all_factor_scores(industry_df)
            scored_df["alpha_score"] = self._compute_composite_alpha(scored_df)

            # 按 Alpha 排序
            scored_df = scored_df.sort_values("alpha_score", ascending=False)
            scored_df["industry_rank"] = range(1, len(scored_df) + 1)

            # 提取目标股票
            target_row = scored_df[scored_df["ts_code"] == ts_code]
            if target_row.empty:
                return {"error": f"股票 {ts_code} 在因子计算后无数据"}

            target_info = self._format_single_stock(target_row.iloc[0])

            # 构建 peers 列表（排除目标股票）
            peers_df = scored_df[scored_df["ts_code"] != ts_code]
            peers = []
            for _, row in peers_df.iterrows():
                peers.append(self._format_single_stock(row))

            # 同行业平均
            peer_avg = {
                "avg_pe_ttm": round(self._safe_mean(scored_df, "pe_ttm"), 2),
                "avg_pb": round(self._safe_mean(scored_df, "pb"), 2),
                "avg_dividend_yield": round(self._safe_mean(scored_df, "dv_ttm"), 2),
                "avg_turnover_rate": round(self._safe_mean(scored_df, "turnover_rate"), 2),
                "avg_volume_ratio": round(self._safe_mean(scored_df, "volume_ratio"), 2),
                "avg_rsi": round(self._safe_mean(scored_df, "rsi_12"), 2),
                "avg_alpha_score": round(self._safe_mean(scored_df, "alpha_score"), 2),
                "peer_count": len(scored_df),
            }

            return {
                "trade_date": trade_date,
                "industry": industry,
                "target": target_info,
                "peers": peers,
                "peer_average": peer_avg,
            }
        except Exception as e:
            logger.error(
                "get_peer_comparison failed for %s: %s", ts_code, e, exc_info=True
            )
            return {"error": str(e)}
        finally:
            session.close()

    # ==================================================================
    # 数据加载
    # ==================================================================

    def _load_stock_data(
        self, session, trade_date: str
    ) -> pd.DataFrame:
        """从数据库加载合并后的全量股票数据。

        联合 daily_basic + stk_factor + stock_basic + moneyflow 数据，
        返回以 ts_code 为索引的 DataFrame。
        """
        try:
            # 1. daily_basic
            db_rows = session.execute(
                text("""
                    SELECT ts_code, close, pe_ttm, pb, turnover_rate, volume_ratio,
                           dv_ttm, total_mv, circ_mv
                    FROM daily_basic
                    WHERE trade_date = :td
                """),
                {"td": trade_date},
            ).fetchall()
            if not db_rows:
                return pd.DataFrame()

            db_df = pd.DataFrame(
                db_rows,
                columns=[
                    "ts_code", "close", "pe_ttm", "pb", "turnover_rate",
                    "volume_ratio", "dv_ttm", "total_mv", "circ_mv",
                ],
            )

            # 2. stk_factor
            sf_rows = session.execute(
                text("""
                    SELECT ts_code, rsi_6, rsi_12, rsi_24, macd, macd_dif, macd_dea,
                           kdj_k, kdj_d, kdj_j, close, pct_change, vol, amount
                    FROM stk_factor
                    WHERE trade_date = :td
                """),
                {"td": trade_date},
            ).fetchall()

            sf_df = pd.DataFrame(
                sf_rows,
                columns=[
                    "ts_code", "rsi_6", "rsi_12", "rsi_24", "macd", "macd_dif",
                    "macd_dea", "kdj_k", "kdj_d", "kdj_j", "sf_close", "pct_change",
                    "vol", "amount",
                ],
            ) if sf_rows else pd.DataFrame(columns=["ts_code"])

            # 3. stock_basic（不依赖 trade_date）
            sb_rows = session.execute(
                text("SELECT ts_code, name, industry FROM stock_basic")
            ).fetchall()
            sb_df = pd.DataFrame(
                sb_rows, columns=["ts_code", "name", "industry"]
            ) if sb_rows else pd.DataFrame(columns=["ts_code", "name", "industry"])

            # 4. 资金流向 — 优先 moneyflow_dc，回退 stock_flow
            flow_df = self._load_flow_data(session, trade_date)

            # 合并
            merged = db_df.merge(sb_df, on="ts_code", how="left")
            merged = merged.merge(sf_df, on="ts_code", how="left")
            if not flow_df.empty:
                merged = merged.merge(flow_df, on="ts_code", how="left")

            return merged

        except Exception as e:
            logger.error("_load_stock_data failed: %s", e, exc_info=True)
            return pd.DataFrame()

    def _load_flow_data(self, session, trade_date: str) -> pd.DataFrame:
        """加载资金流向数据。优先 moneyflow_dc，回退 stock_flow。"""
        try:
            # 尝试 moneyflow_dc
            rows = session.execute(
                text("""
                    SELECT ts_code, net_amount
                    FROM moneyflow_dc
                    WHERE trade_date = :td
                """),
                {"td": trade_date},
            ).fetchall()
            if rows:
                return pd.DataFrame(rows, columns=["ts_code", "net_fund_flow"])
        except Exception:
            pass

        try:
            # 回退 stock_flow
            rows = session.execute(
                text("""
                    SELECT ts_code, net_mf_amount
                    FROM stock_flow
                    WHERE trade_date = :td
                """),
                {"td": trade_date},
            ).fetchall()
            if rows:
                return pd.DataFrame(rows, columns=["ts_code", "net_fund_flow"])
        except Exception:
            pass

        return pd.DataFrame(columns=["ts_code", "net_fund_flow"])

    # ==================================================================
    # 因子计算
    # ==================================================================

    def _compute_all_factor_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """在行业分组内计算各因子的百分位得分。

        对每只股票，在其所属行业内计算各因子百分位（0-100），
        并汇总为 5 大因子得分。
        """
        result_frames = []

        for industry_name, group in df.groupby("industry"):
            if len(group) < MIN_INDUSTRY_SIZE:
                continue

            g = group.copy()
            g = self._compute_value_factor(g)
            g = self._compute_momentum_factor(g)
            g = self._compute_flow_factor(g)
            g = self._compute_quality_factor(g)
            g = self._compute_size_factor(g)
            result_frames.append(g)

        if not result_frames:
            return pd.DataFrame()
        return pd.concat(result_frames, ignore_index=True)

    def _compute_value_factor(self, df: pd.DataFrame) -> pd.DataFrame:
        """价值因子 = PE百分位(反转) + PB百分位(反转) + 股息率百分位。

        PE/PB 越低越好（取反），股息率越高越好。
        """
        df = df.copy()
        n = len(df)

        # PE 值越小越好：反转百分位
        pe_valid = df["pe_ttm"].notna() & (df["pe_ttm"] > 0)
        df["pe_score"] = np.nan
        if pe_valid.sum() > 1:
            pe_valid_idx = df.index[pe_valid]
            pe_vals = df.loc[pe_valid_idx, "pe_ttm"]
            # rank 从 1 开始，值越大排名越高 → 反转后值越大得分越高
            ranks = pe_vals.rank(ascending=True)  # 低 PE 排名低
            df.loc[pe_valid_idx, "pe_score"] = (
                (1 - (ranks - 1) / max(pe_valid.sum() - 1, 1)) * 100
            )

        # PB 值越小越好：反转百分位
        pb_valid = df["pb"].notna() & (df["pb"] > 0)
        df["pb_score"] = np.nan
        if pb_valid.sum() > 1:
            pb_valid_idx = df.index[pb_valid]
            pb_vals = df.loc[pb_valid_idx, "pb"]
            ranks = pb_vals.rank(ascending=True)
            df.loc[pb_valid_idx, "pb_score"] = (
                (1 - (ranks - 1) / max(pb_valid.sum() - 1, 1)) * 100
            )

        # 股息率越高越好：正向百分位
        dv_valid = df["dv_ttm"].notna() & (df["dv_ttm"] > 0)
        df["dv_score"] = np.nan
        if dv_valid.sum() > 1:
            dv_valid_idx = df.index[dv_valid]
            dv_vals = df.loc[dv_valid_idx, "dv_ttm"]
            ranks = dv_vals.rank(ascending=True)
            df.loc[dv_valid_idx, "dv_score"] = (
                (ranks - 1) / max(dv_valid.sum() - 1, 1) * 100
            )

        # 综合：三个子因子等权平均（缺失的跳过）
        def _value_row(row):
            scores = []
            if pd.notna(row.get("pe_score")):
                scores.append(row["pe_score"])
            if pd.notna(row.get("pb_score")):
                scores.append(row["pb_score"])
            if pd.notna(row.get("dv_score")):
                scores.append(row["dv_score"])
            return round(sum(scores) / len(scores), 2) if scores else None

        df["value_score"] = df.apply(_value_row, axis=1)
        df["value_pctile"] = df["value_score"]  # 在计算 composite 时再统一百分位

        return df

    def _compute_momentum_factor(self, df: pd.DataFrame) -> pd.DataFrame:
        """动量因子 = RSI百分位(适度偏离50更好) + 量比百分位。

        RSI 适度偏高（40-70 区间）为佳，量比适度偏高为佳。
        """
        df = df.copy()

        # RSI_12 适度偏离 50 越小越好（接近 50 越好，同时偏向多头更好）
        # 改为：RSI 越高越好（偏多头），但极端值扣分
        rsi_valid = df["rsi_12"].notna() & (df["rsi_12"] > 0)
        df["rsi_score"] = np.nan
        if rsi_valid.sum() > 1:
            rsi_idx = df.index[rsi_valid]
            rsi_vals = df.loc[rsi_idx, "rsi_12"]
            # 适度偏离50更好：距离50越近得分越高，但整体偏多头加分
            optimal_dist = np.abs(rsi_vals - 55).values  # 略偏多头为佳
            # 距离 55 越近 → 分越高
            max_dist = max(optimal_dist.max(), 1)
            scores = (1 - optimal_dist / max_dist) * 80 + (rsi_vals.values / 100) * 20
            df.loc[rsi_idx, "rsi_score"] = np.clip(scores, 0, 100)

        # MACD 柱：正值得分高
        macd_valid = df["macd"].notna()
        df["macd_score"] = np.nan
        if macd_valid.sum() > 1:
            macd_idx = df.index[macd_valid]
            macd_vals = df.loc[macd_idx, "macd"]
            ranks = macd_vals.rank(ascending=True)
            df.loc[macd_idx, "macd_score"] = (
                (ranks - 1) / max(macd_valid.sum() - 1, 1) * 100
            )

        # 量比越高越好（适中偏高）
        vr_valid = df["volume_ratio"].notna() & (df["volume_ratio"] > 0)
        df["vr_score"] = np.nan
        if vr_valid.sum() > 1:
            vr_idx = df.index[vr_valid]
            vr_vals = df.loc[vr_idx, "volume_ratio"]
            ranks = vr_vals.rank(ascending=True)
            df.loc[vr_idx, "vr_score"] = (
                (ranks - 1) / max(vr_valid.sum() - 1, 1) * 100
            )

        def _momentum_row(row):
            scores = []
            if pd.notna(row.get("rsi_score")):
                scores.append(row["rsi_score"])
            if pd.notna(row.get("macd_score")):
                scores.append(row["macd_score"])
            if pd.notna(row.get("vr_score")):
                scores.append(row["vr_score"])
            return round(sum(scores) / len(scores), 2) if scores else None

        df["momentum_score"] = df.apply(_momentum_row, axis=1)
        df["momentum_pctile"] = df["momentum_score"]

        return df

    def _compute_flow_factor(self, df: pd.DataFrame) -> pd.DataFrame:
        """资金因子 = 净资金流百分位。

        净资金流入越高越好。
        """
        df = df.copy()

        flow_valid = df["net_fund_flow"].notna()
        df["flow_score"] = np.nan
        if flow_valid.sum() > 1:
            flow_idx = df.index[flow_valid]
            flow_vals = df.loc[flow_idx, "net_fund_flow"]
            ranks = flow_vals.rank(ascending=True)
            df.loc[flow_idx, "flow_score"] = round(
                (ranks - 1) / max(flow_valid.sum() - 1, 1) * 100, 2
            )

        df["flow_pctile"] = df["flow_score"]
        return df

    def _compute_quality_factor(self, df: pd.DataFrame) -> pd.DataFrame:
        """质量因子 = 换手率百分位(适度) + 流通市值排名。

        换手率适度（3-8%）为佳，流通市值适中为佳。
        """
        df = df.copy()

        # 换手率适度越好
        to_valid = df["turnover_rate"].notna() & (df["turnover_rate"] > 0)
        df["to_score"] = np.nan
        if to_valid.sum() > 1:
            to_idx = df.index[to_valid]
            to_vals = df.loc[to_idx, "turnover_rate"]
            # 适度偏离 5% 越小越好
            optimal_dist = np.abs(to_vals - 5.0).values
            max_dist = max(optimal_dist.max(), 1)
            scores = (1 - optimal_dist / max_dist) * 100
            df.loc[to_idx, "to_score"] = np.clip(scores, 0, 100)

        # 流通市值排名（适中更好，极端大/小扣分）
        cmv_valid = df["circ_mv"].notna() & (df["circ_mv"] > 0)
        df["cmv_score"] = np.nan
        if cmv_valid.sum() > 1:
            cmv_idx = df.index[cmv_valid]
            cmv_vals = df.loc[cmv_idx, "circ_mv"]
            # 中位数附近得分最高
            median_cmv = cmv_vals.median()
            dist = np.abs(cmv_vals.values - median_cmv)
            max_dist = max(dist.max(), 1)
            scores = (1 - dist / max_dist) * 100
            df.loc[cmv_idx, "cmv_score"] = np.clip(scores, 0, 100)

        def _quality_row(row):
            scores = []
            if pd.notna(row.get("to_score")):
                scores.append(row["to_score"])
            if pd.notna(row.get("cmv_score")):
                scores.append(row["cmv_score"])
            return round(sum(scores) / len(scores), 2) if scores else None

        df["quality_score"] = df.apply(_quality_row, axis=1)
        df["quality_pctile"] = df["quality_score"]

        return df

    def _compute_size_factor(self, df: pd.DataFrame) -> pd.DataFrame:
        """规模因子 = ln(total_mv) 百分位。

        使用自然对数变换后的市值百分位。
        """
        df = df.copy()

        mv_valid = df["total_mv"].notna() & (df["total_mv"] > 0)
        df["ln_mv"] = np.nan
        df["size_score"] = np.nan
        if mv_valid.sum() > 1:
            mv_idx = df.index[mv_valid]
            ln_vals = np.log(df.loc[mv_idx, "total_mv"].values)
            df.loc[mv_idx, "ln_mv"] = ln_vals
            ranks = pd.Series(ln_vals, index=mv_idx).rank(ascending=True)
            df.loc[mv_idx, "size_score"] = round(
                (ranks - 1) / max(mv_valid.sum() - 1, 1) * 100, 2
            )

        df["size_pctile"] = df["size_score"]
        return df

    def _compute_composite_alpha(self, df: pd.DataFrame) -> pd.Series:
        """计算 Composite Alpha = 各因子加权求和。

        缺失因子的权重按比例分配给有数据的因子。
        """
        factor_cols = [
            "value_score", "momentum_score", "flow_score",
            "quality_score", "size_score",
        ]
        factor_names = ["value", "momentum", "flow", "quality", "size"]

        alpha = pd.Series(0.0, index=df.index)
        for _, row in df.iterrows():
            total_weight = 0.0
            weighted_sum = 0.0
            for fname, fcol in zip(factor_names, factor_cols):
                val = row.get(fcol)
                if pd.notna(val):
                    weighted_sum += val * FACTOR_WEIGHTS[fname]
                    total_weight += FACTOR_WEIGHTS[fname]
            if total_weight > 0:
                alpha.iloc[row.name if isinstance(row.name, int) else df.index.get_loc(row.name)] = round(
                    weighted_sum / total_weight, 2
                )

        return alpha

    # ==================================================================
    # 格式化输出
    # ==================================================================

    def _format_stock_list(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """将评分后的 DataFrame 转换为结果列表。"""
        stocks = []
        df_ranked = df.sort_values("alpha_score", ascending=False).reset_index(drop=True)
        for rank, (_, row) in enumerate(df_ranked.iterrows(), 1):
            stocks.append(self._format_single_stock(row, rank=rank))
        return stocks

    def _format_single_stock(
        self, row: pd.Series, rank: Optional[int] = None
    ) -> Dict[str, Any]:
        """格式化单只股票的输出。"""
        stock = {
            "ts_code": row.get("ts_code", ""),
            "name": row.get("name", ""),
            "industry": row.get("industry", ""),
            "alpha_score": round(float(row.get("alpha_score", 0)), 2),
        }
        if rank is not None:
            stock["rank"] = rank

        # 原始指标
        stock["pe_ttm"] = round(float(row.get("pe_ttm", 0) or 0), 2)
        stock["pb"] = round(float(row.get("pb", 0) or 0), 2)
        stock["dv_ttm"] = round(float(row.get("dv_ttm", 0) or 0), 4)
        stock["turnover_rate"] = round(float(row.get("turnover_rate", 0) or 0), 2)
        stock["total_mv_yi"] = round(float(row.get("total_mv", 0) or 0) / 10000, 2)
        stock["volume_ratio"] = round(float(row.get("volume_ratio", 0) or 0), 2)

        # 因子得分
        stock["factors"] = {}
        for fname in FACTOR_WEIGHTS:
            score = row.get(f"{fname}_score")
            stock["factors"][fname] = {
                "score": round(float(score), 2) if pd.notna(score) else None,
                "weight": FACTOR_WEIGHTS[fname],
                "icon": FACTOR_META[fname]["icon"],
            }

        # 行业排名（如果有）
        if "industry_rank" in row.index and pd.notna(row.get("industry_rank")):
            stock["industry_rank"] = int(row["industry_rank"])

        return stock

    def _build_summary(self, df: pd.DataFrame) -> Dict[str, Any]:
        """构建汇总统计。"""
        total = len(df)
        avg_alpha = df["alpha_score"].mean() if "alpha_score" in df.columns else 0
        avg_mv = df["total_mv"].mean() if "total_mv" in df.columns else 0

        # 行业分布
        industry_counts = {}
        if "industry" in df.columns:
            industry_counts = df["industry"].value_counts().head(10).to_dict()

        # 因子平均得分
        factor_avgs = {}
        for fname in FACTOR_WEIGHTS:
            col = f"{fname}_score"
            if col in df.columns:
                valid = df[col].dropna()
                factor_avgs[fname] = round(valid.mean(), 2) if len(valid) > 0 else None

        return {
            "total_stocks": total,
            "avg_alpha_score": round(float(avg_alpha), 2),
            "avg_market_cap_yi": round(float(avg_mv) / 10000, 2) if avg_mv else 0,
            "factor_averages": factor_avgs,
            "top_industries": industry_counts,
        }

    # ==================================================================
    # 工具方法
    # ==================================================================

    @staticmethod
    def _safe_mean(df: pd.DataFrame, col: str) -> float:
        """安全计算均值，忽略 NaN。"""
        if col not in df.columns:
            return 0.0
        valid = df[col].dropna()
        return float(valid.mean()) if len(valid) > 0 else 0.0

    @staticmethod
    def _safe_val(row, col):
        """安全获取行值。"""
        try:
            v = row.get(col) if hasattr(row, "get") else row[col]
            if v is None or (isinstance(v, float) and math.isnan(v)):
                return None
            return float(v)
        except (ValueError, TypeError, KeyError):
            return None
