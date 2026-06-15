"""E2E 测试配置 — API 基准地址 + Tushare 直连验证器."""

import os
import sys
import pytest
import requests

# 后端路径加入 sys.path 以便直接调用 TuShare
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL


@pytest.fixture(scope="session")
def api_get(base_url):
    """封装 requests.get，自动拼接 base_url."""

    def _get(path, params=None, timeout=30):
        url = f"{base_url}{path}"
        resp = requests.get(url, params=params, timeout=timeout)
        return resp

    return _get


@pytest.fixture(scope="session")
def latest_trade_date(api_get):
    """从 /api/market/overview 获取最新交易日期."""
    resp = api_get("/api/market/overview")
    data = resp.json()
    return data.get("trade_date", "20260613")


@pytest.fixture(scope="session")
def tushare_client():
    """直连 TuShare 的客户端，用于第三方数据交叉验证."""
    import tushare as ts

    # 读取 token
    token = ""
    env_path = os.path.expanduser("~/.secrets/tushare.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if "TUSHARE_TOKEN" in line:
                    token = line.strip().split("=", 1)[1]
                    break

    pro = ts.pro_api(token)

    # 设置自定义端点 — 从 config.py 读取
    api_url = "http://124.222.60.121:8020/"  # 默认值
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "app", "config.py"
    )
    try:
        if os.path.exists(config_path):
            with open(config_path) as f:
                content = f.read()
                import re
                m = re.search(r'TUSHARE_API_URL\s*=\s*["\']([^"\']+)["\']', content)
                if m:
                    api_url = m.group(1)
    except Exception:
        pass
    pro._DataApi__http_url = api_url

    return pro
