# [修改] 问题5：在 BaseStrategy 基类中添加 _find_col 和 _safe 静态方法，
# 消除 6 个策略子类中的重复定义。
"""策略引擎基类。"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import pandas as pd


class StrategyResult:
    """单只股票的策略评分结果。"""

    def __init__(self, ts_code: str, name: str, score: float, signals: Dict[str, Any], reason: str):
        self.ts_code = ts_code
        self.name = name
        self.score = score  # 0-100 置信度
        self.signals = signals
        self.reason = reason

    def to_dict(self):
        return {
            "ts_code": self.ts_code,
            "name": self.name,
            "score": round(self.score, 2),
            "signals": self.signals,
            "reason": self.reason,
        }


class BaseStrategy(ABC):
    """策略基类，所有策略必须继承此类。"""

    name: str = ""
    description: str = ""
    category: str = ""   # value, momentum, flow, event, combo
    icon: str = ""       # emoji 图标

    @abstractmethod
    def required_data(self) -> List[str]:
        """返回所需数据键列表，如 ['daily_basic', 'moneyflow']"""
        pass

    @abstractmethod
    def check(self, data: Dict[str, Any]) -> List[StrategyResult]:
        """执行策略筛选，返回匹配股票列表"""
        pass

    def score(self, result: StrategyResult) -> float:
        """可选的评分覆盖"""
        return result.score

    @staticmethod
    def _find_col(df, candidates):
        """在 DataFrame 的列中查找第一个匹配的候选列名。"""
        for c in candidates:
            if c in df.columns:
                return c
        return None

    @staticmethod
    def _safe(row, col):
        """安全提取数值，NaN/None 返回 None。"""
        try:
            v = row.get(col)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            return float(v)
        except (ValueError, TypeError):
            return None


# ---------------------------------------------------------------------------
# 策略分类定义
# ---------------------------------------------------------------------------
STRATEGY_CATEGORIES = {
    "value": ["high_dividend", "low_valuation_gold", "broken_net_gold", "value_fund_resonance", "chip_pledge_safe"],
    "momentum": ["volume_breakthrough", "ma_alignment", "trend_volume_resonance",
                 "volume_anomaly", "kdj_oversold_rebound", "macd_golden_cross",
                 "oversold_bounce"],
    "event": ["block_trade_premium", "consecutive_limit_up", "limit_up_reseal"],
    "flow": ["main_fund_inflow", "margin_growth", "margin_fund_convergence", "smart_money_tracker", "flow_divergence", "insider_conviction"],
    "combo": ["trend_volume_resonance", "value_fund_resonance"],
}
