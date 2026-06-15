#!/usr/bin/env python3
"""stock-flow API 数据准确性测试

检查所有关键 API 的返回数据是否正确解析（无 {success:true,data:{}} 嵌套问题）。
用法: python3 test-api-accuracy.py [--base-url http://localhost:8080]
"""
import json
import sys
import urllib.request
import urllib.error

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
TRADE_DATE = "20260615"

# (endpoint, description, expected_top_keys, data_path)
# data_path: 表示数据实际所在的 key 路径，如 "data" 表示 res["data"]
ENDPOINTS = [
    # 大盘总览
    (f"/api/market/overview?trade_date={TRADE_DATE}", "大盘资金总览", {"trade_date", "main_net_inflow", "total_turnover"}, "data"),
    (f"/api/market/north?trade_date={TRADE_DATE}", "北向资金", {"north_money", "hgt", "sgt"}, "data"),
    (f"/api/market/breadth?trade_date={TRADE_DATE}", "市场宽度", {"limit_up", "limit_down", "distribution"}, "data"),
    (f"/api/market/indices?trade_date={TRADE_DATE}", "三大指数", {"indices"}, "data"),
    (f"/api/market/limit-stats?trade_date={TRADE_DATE}", "涨跌停统计", {"up_count", "down_count", "up_list"}, "data"),
    (f"/api/market/flow-trend?days=7", "资金流向趋势", {"labels", "series"}, "data"),
    (f"/api/market/turnover/trend?days=7", "成交额趋势", {"labels", "values"}, "data"),
    # 板块
    (f"/api/sectors?page=1&size=5&trade_date={TRADE_DATE}", "板块列表", {"items", "total"}, "data"),
    # 选股
    (f"/api/screener/run?trade_date={TRADE_DATE}", "选股工具", {"stocks"}, "data"),
    # 策略
    (f"/api/strategies/health/market/top?trade_date={TRADE_DATE}", "策略健康度", {"items"}, "data"),
    # AI日志
    (f"/api/activity-log?page_size=3", "AI日志", {"items", "total"}, None),  # 无 data wrapper
    # 研究资料
    (f"/api/research-browser/tree", "研究资料目录树", {"name", "children"}, None),  # 无 data wrapper
]


def fetch(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "test"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"_error": str(e)}


def test_endpoint(url, desc, expected_keys, data_path):
    raw = fetch(url)
    if "_error" in raw:
        return f"  ❌ {desc}: 请求失败 - {raw['_error']}"

    # 如果有 data_path，尝试取数据
    data = raw
    if data_path and data_path in raw:
        data = raw[data_path]

    # 检查是否还是 {success, data} 嵌套
    if isinstance(data, dict) and "success" in data and "data" in data:
        return f"  ⚠️  {desc}: 数据仍嵌套在 {{success, data}} 中！需要解包。keys={list(data.keys())}"

    # 检查预期 key 是否存在
    if isinstance(data, dict):
        missing = expected_keys - set(data.keys())
        if missing:
            return f"  ⚠️  {desc}: 缺少字段 {missing}。实际 keys: {list(data.keys())[:8]}"
        return f"  ✅ {desc}: 正常 (keys: {list(data.keys())[:5]}...)"
    elif isinstance(data, list):
        return f"  ✅ {desc}: 正常 (列表, {len(data)} 条)"
    else:
        return f"  ⚠️  {desc}: 数据类型异常 {type(data).__name__}"


def main():
    print(f"🔍 stock-flow API 数据准确性测试")
    print(f"   Base URL: {BASE_URL}")
    print(f"   Trade Date: {TRADE_DATE}")
    print(f"{'='*60}")

    passed = 0
    warned = 0
    failed = 0

    for url, desc, expected_keys, data_path in ENDPOINTS:
        full_url = f"{BASE_URL}{url}"
        result = test_endpoint(full_url, desc, expected_keys, data_path)
        print(result)
        if result.startswith("  ✅"):
            passed += 1
        elif result.startswith("  ⚠️"):
            warned += 1
        else:
            failed += 1

    print(f"{'='*60}")
    print(f"结果: ✅ {passed} 通过  ⚠️ {warned} 警告  ❌ {failed} 失败")

    if warned > 0 or failed > 0:
        print("\n💡 警告/失败项需要检查前端是否正确解包了 API 响应。")
        print("   修复模式: setData(res) → setData(res?.data || res)")
        sys.exit(1)
    else:
        print("\n🎉 全部通过！")
        sys.exit(0)


if __name__ == "__main__":
    main()
