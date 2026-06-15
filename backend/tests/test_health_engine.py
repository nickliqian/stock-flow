"""StockHealthEngine 单元测试。"""

import math
import pandas as pd
from unittest.mock import MagicMock, patch
from app.engine.health import StockHealthEngine, DIM_LIMITS, STRATEGY_CHECK_MAP


def _make_loader(data_map):
    """构造 mock StrategyDataLoader，返回指定数据。"""
    loader = MagicMock()
    loader.load.return_value = data_map
    loader.cache.get_stock_basic_from_db.return_value = []
    return loader


def _make_basic_df(rows):
    """构造 daily_basic DataFrame。"""
    return pd.DataFrame(rows)


def _make_stk_factor_df(rows):
    """构造 stk_factor DataFrame。"""
    return pd.DataFrame(rows)


def _make_moneyflow_df(rows):
    """构造 moneyflow DataFrame。"""
    return pd.DataFrame(rows)


def _make_cyq_df(rows):
    """构造 cyq_perf DataFrame。"""
    return pd.DataFrame(rows)


def _make_pledge_df(rows):
    """构造 pledge_stat DataFrame。"""
    return pd.DataFrame(rows)


def test_score_returns_correct_structure():
    """验证返回格式符合 spec。"""
    loader = _make_loader({
        "daily_basic": _make_basic_df([]),
        "stk_factor": _make_stk_factor_df([]),
        "moneyflow_multi": _make_moneyflow_df([]),
        "cyq_perf": _make_cyq_df([]),
        "pledge_stat": _make_pledge_df([]),
        "daily_multi": pd.DataFrame([]),
    })
    engine = StockHealthEngine(loader)
    result = engine.score("000001.SZ", "20260101")

    assert result["ts_code"] == "000001.SZ"
    assert result["trade_date"] == "20260101"
    assert "health_score" in result
    assert "dimensions" in result
    assert isinstance(result["health_score"], float)
    assert 0 <= result["health_score"] <= 100

    for dim, expected_limit in DIM_LIMITS.items():
        assert dim in result["dimensions"]
        d = result["dimensions"][dim]
        assert isinstance(d["score"], float)
        assert isinstance(d["max"], float)
        assert d["max"] == expected_limit
        assert 0 <= d["score"] <= d["max"]


def test_technical_macd_golden_cross():
    """验证 MACD 金叉 +8 分。"""
    loader = _make_loader({
        "daily_basic": _make_basic_df([]),
        "stk_factor": _make_stk_factor_df([{
            "ts_code": "000001.SZ", "macd_dif": 0.5, "macd_dea": 0.2,
            "macd": 0.3, "kdj_k": 50, "kdj_d": 45, "rsi_6": 50,
        }]),
        "moneyflow_multi": _make_moneyflow_df([]),
        "cyq_perf": _make_cyq_df([]),
        "pledge_stat": _make_pledge_df([]),
        "daily_multi": pd.DataFrame([]),
    })
    engine = StockHealthEngine(loader)
    result = engine.score("000001.SZ", "20260101")
    tech = result["dimensions"]["technical"]
    assert tech["score"] == 8.0
    assert tech["details"]["macd"] == "golden_cross"


def test_technical_macd_death_cross():
    """验证 MACD 死叉 -5 分。"""
    loader = _make_loader({
        "daily_basic": _make_basic_df([]),
        "stk_factor": _make_stk_factor_df([{
            "ts_code": "000001.SZ", "macd_dif": 0.2, "macd_dea": 0.5,
            "macd": -0.3, "kdj_k": 50, "kdj_d": 45, "rsi_6": 50,
        }]),
        "moneyflow_multi": _make_moneyflow_df([]),
        "cyq_perf": _make_cyq_df([]),
        "pledge_stat": _make_pledge_df([]),
        "daily_multi": pd.DataFrame([]),
    })
    engine = StockHealthEngine(loader)
    result = engine.score("000001.SZ", "20260101")
    tech = result["dimensions"]["technical"]
    assert tech["score"] == 0.0  # -5 clamped to 0
    assert tech["details"]["macd"] == "death_cross"


def test_technical_all_signals():
    """验证同时满足多个技术信号时正确叠加。"""
    loader = _make_loader({
        "daily_basic": _make_basic_df([]),
        "stk_factor": _make_stk_factor_df([{
            "ts_code": "000001.SZ",
            "macd_dif": 0.5, "macd_dea": 0.2, "macd": 0.3,  # 金叉 +8
            "kdj_k": 25, "kdj_d": 20,                       # 超卖金叉 +6
            "rsi_6": 25,                                     # 超卖 +6
        }]),
        "moneyflow_multi": _make_moneyflow_df([]),
        "cyq_perf": _make_cyq_df([]),
        "pledge_stat": _make_pledge_df([]),
        "daily_multi": pd.DataFrame([]),
    })
    engine = StockHealthEngine(loader)
    result = engine.score("000001.SZ", "20260101")
    tech = result["dimensions"]["technical"]
    assert tech["score"] == 20.0  # 8 + 6 + 6 = 20 (cap)
    assert tech["details"]["macd"] == "golden_cross"
    assert tech["details"]["kdj"] == "golden_cross_oversold"
    assert tech["details"]["rsi"] == "oversold_bounce"


def test_fundamental_valuation():
    """验证基本面低估值评分。"""
    loader = _make_loader({
        "daily_basic": _make_basic_df([{
            "ts_code": "000001.SZ", "pe_ttm": 10, "pb": 1.2,
            "dv_ttm": 4.0, "total_mv": 2000000,  # 200亿
        }]),
        "stk_factor": _make_stk_factor_df([]),
        "moneyflow_multi": _make_moneyflow_df([]),
        "cyq_perf": _make_cyq_df([]),
        "pledge_stat": _make_pledge_df([]),
        "daily_multi": pd.DataFrame([]),
    })
    engine = StockHealthEngine(loader)
    result = engine.score("000001.SZ", "20260101")
    fund = result["dimensions"]["fundamental"]
    # PE<15:+3, PB<1.5:+2, dv>3:+3, mv>100亿:+2 = 10 (cap)
    assert fund["score"] == 10.0
    assert fund["details"]["pe_ttm"] == 10.0
    assert fund["details"]["pb"] == 1.2


def test_fundamental_overvalued():
    """验证高估值扣分。"""
    loader = _make_loader({
        "daily_basic": _make_basic_df([{
            "ts_code": "000001.SZ", "pe_ttm": 60, "pb": 10,
            "dv_ttm": 0.5, "total_mv": 10000,  # 1亿
        }]),
        "stk_factor": _make_stk_factor_df([]),
        "moneyflow_multi": _make_moneyflow_df([]),
        "cyq_perf": _make_cyq_df([]),
        "pledge_stat": _make_pledge_df([]),
        "daily_multi": pd.DataFrame([]),
    })
    engine = StockHealthEngine(loader)
    result = engine.score("000001.SZ", "20260101")
    fund = result["dimensions"]["fundamental"]
    # PE>50:-2, PB>8:-2 = -4 → clamped to 0
    assert fund["score"] == 0.0


def test_chip_risk_pledge():
    """验证质押比例评分。"""
    loader = _make_loader({
        "daily_basic": _make_basic_df([]),
        "stk_factor": _make_stk_factor_df([]),
        "moneyflow_multi": _make_moneyflow_df([]),
        "cyq_perf": _make_cyq_df([]),
        "pledge_stat": _make_pledge_df([{
            "ts_code": "000001.SZ", "pledge_ratio": 5,
        }]),
        "daily_multi": pd.DataFrame([]),
    })
    engine = StockHealthEngine(loader)
    result = engine.score("000001.SZ", "20260101")
    chip = result["dimensions"]["chip_risk"]
    # pledge < 10 → +3
    assert chip["score"] == 3.0
    assert chip["details"]["pledge_ratio"] == 5.0


def test_chip_risk_high_pledge():
    """验证高质押比例扣分。"""
    loader = _make_loader({
        "daily_basic": _make_basic_df([]),
        "stk_factor": _make_stk_factor_df([]),
        "moneyflow_multi": _make_moneyflow_df([]),
        "cyq_perf": _make_cyq_df([]),
        "pledge_stat": _make_pledge_df([{
            "ts_code": "000001.SZ", "pledge_ratio": 60,
        }]),
        "daily_multi": pd.DataFrame([]),
    })
    engine = StockHealthEngine(loader)
    result = engine.score("000001.SZ", "20260101")
    chip = result["dimensions"]["chip_risk"]
    # pledge > 50 → -3
    assert chip["score"] == 0.0


def test_money_flow_consecutive_inflow():
    """验证连续净流入评分。"""
    loader = _make_loader({
        "daily_basic": _make_basic_df([]),
        "stk_factor": _make_stk_factor_df([]),
        "moneyflow_multi": _make_moneyflow_df([
            {"ts_code": "000001.SZ", "trade_date": "20260101", "net_mf_amount": 100,
             "buy_lg_amount": 200, "sell_lg_amount": 100, "buy_elg_amount": 150, "sell_elg_amount": 50,
             "buy_sm_amount": 50, "sell_sm_amount": 50, "buy_md_amount": 50, "sell_md_amount": 50},
            {"ts_code": "000001.SZ", "trade_date": "20260102", "net_mf_amount": 200,
             "buy_lg_amount": 300, "sell_lg_amount": 100, "buy_elg_amount": 200, "sell_elg_amount": 0,
             "buy_sm_amount": 50, "sell_sm_amount": 50, "buy_md_amount": 50, "sell_md_amount": 50},
            {"ts_code": "000001.SZ", "trade_date": "20260103", "net_mf_amount": 300,
             "buy_lg_amount": 400, "sell_lg_amount": 100, "buy_elg_amount": 300, "sell_elg_amount": 0,
             "buy_sm_amount": 50, "sell_sm_amount": 50, "buy_md_amount": 50, "sell_md_amount": 50},
            {"ts_code": "000001.SZ", "trade_date": "20260104", "net_mf_amount": 400,
             "buy_lg_amount": 500, "sell_lg_amount": 100, "buy_elg_amount": 400, "sell_elg_amount": 0,
             "buy_sm_amount": 50, "sell_sm_amount": 50, "buy_md_amount": 50, "sell_md_amount": 50},
            {"ts_code": "000001.SZ", "trade_date": "20260105", "net_mf_amount": 500,
             "buy_lg_amount": 600, "sell_lg_amount": 100, "buy_elg_amount": 500, "sell_elg_amount": 0,
             "buy_sm_amount": 50, "sell_sm_amount": 50, "buy_md_amount": 50, "sell_md_amount": 50},
        ]),
        "cyq_perf": _make_cyq_df([]),
        "pledge_stat": _make_pledge_df([]),
        "daily_multi": pd.DataFrame([]),
    })
    engine = StockHealthEngine(loader)
    result = engine.score("000001.SZ", "20260101")
    mf = result["dimensions"]["money_flow"]
    # 5日连续净流入 → +15
    assert mf["score"] >= 15.0
    assert mf["details"]["consecutive_inflow_days"] == 5


def test_strategy_signal_high_dividend():
    """验证高股息策略命中 +5 分。"""
    loader = _make_loader({
        "daily_basic": _make_basic_df([{
            "ts_code": "000001.SZ", "pe_ttm": 15, "pb": 1.5,
            "dv_ttm": 4.0, "total_mv": 500000,
        }]),
        "stk_factor": _make_stk_factor_df([]),
        "moneyflow_multi": _make_moneyflow_df([]),
        "cyq_perf": _make_cyq_df([]),
        "pledge_stat": _make_pledge_df([]),
        "daily_multi": pd.DataFrame([]),
    })
    engine = StockHealthEngine(loader)
    result = engine.score("000001.SZ", "20260101")
    strat = result["dimensions"]["strategy"]
    # high_dividend: dv>3 && pe<20 → hit, value=+5
    matched_names = [m["strategy"] for m in strat["details"]["matched_strategies"]]
    assert "high_dividend" in matched_names
    assert strat["score"] >= 5.0


def test_batch_score():
    """验证批量评分返回正确结构。"""
    loader = _make_loader({
        "daily_basic": _make_basic_df([
            {"ts_code": "000001.SZ", "pe_ttm": 10, "pb": 1, "dv_ttm": 5, "total_mv": 2000000},
            {"ts_code": "000002.SZ", "pe_ttm": 60, "pb": 10, "dv_ttm": 0.3, "total_mv": 5000},
        ]),
        "stk_factor": _make_stk_factor_df([]),
        "moneyflow_multi": _make_moneyflow_df([]),
        "cyq_perf": _make_cyq_df([]),
        "pledge_stat": _make_pledge_df([]),
        "daily_multi": pd.DataFrame([]),
    })
    loader.cache.get_stock_basic_from_db.return_value = [
        {"ts_code": "000001.SZ", "name": "平安银行"},
        {"ts_code": "000002.SZ", "name": "万科A"},
    ]
    engine = StockHealthEngine(loader)
    result = engine.batch_score("20260101")

    assert result["total"] == 2
    assert len(result["results"]) == 2
    # 按分数降序
    assert result["results"][0]["health_score"] >= result["results"][1]["health_score"]
    # 名称正确
    names = [r["stock_name"] for r in result["results"]]
    assert "平安银行" in names
    assert "万科A" in names


def test_dimension_failure_isolated():
    """验证单个维度失败不影响其他维度。"""
    loader = _make_loader({
        "daily_basic": _make_basic_df([{
            "ts_code": "000001.SZ", "pe_ttm": 10, "pb": 1,
            "dv_ttm": 5, "total_mv": 2000000,
        }]),
        "stk_factor": _make_stk_factor_df([]),
        "moneyflow_multi": _make_moneyflow_df([]),
        "cyq_perf": _make_cyq_df([]),
        "pledge_stat": _make_pledge_df([]),
        "daily_multi": pd.DataFrame([]),
    })
    engine = StockHealthEngine(loader)
    # Monkey-patch one dimension to raise
    engine._score_technical = MagicMock(side_effect=RuntimeError("boom"))
    result = engine.score("000001.SZ", "20260101")

    # technical should be 0 but others still work
    assert result["dimensions"]["technical"]["score"] == 0.0
    assert result["dimensions"]["fundamental"]["score"] > 0
    assert isinstance(result["health_score"], float)


def test_strategy_map_has_20_strategies():
    """验证 20 个策略全部映射（对应 base.py 中去重后的 20 个唯一策略）。"""
    assert len(STRATEGY_CHECK_MAP) == 20
    categories = set(v[0] for v in STRATEGY_CHECK_MAP.values())
    assert categories == {"value", "momentum", "flow", "event"}
