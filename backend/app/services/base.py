# [修改说明] 问题1+6：创建 BaseService 基类，提供全局单例 TuShareClient 和 CacheService，
# 替代原来每个 Service 各自创建实例的方式，减少不必要的重复实例化。

import threading

from ..cache import CacheService
from ..clients.tushare import TuShareClient
from ..config import TUSHARE_TOKEN, TUSHARE_API_URL

# 全局单例：所有 Service 共享同一个 TuShareClient 和 CacheService
_global_client = None
_global_cache = None
_client_lock = threading.Lock()
_cache_lock = threading.Lock()


def get_global_client():
    """获取全局单例 TuShareClient（线程安全）。"""
    global _global_client
    if _global_client is None:
        with _client_lock:
            if _global_client is None:
                _global_client = TuShareClient(TUSHARE_TOKEN, TUSHARE_API_URL)
    return _global_client


def get_global_cache():
    """获取全局单例 CacheService（线程安全）。"""
    global _global_cache
    if _global_cache is None:
        with _cache_lock:
            if _global_cache is None:
                _global_cache = CacheService()
    return _global_cache


class BaseService:
    """所有 Service 的基类，提供共享的 __init__ 逻辑。

    子类可通过 cache 和 client 参数覆盖默认全局实例。
    """

    def __init__(self, cache=None, client=None):
        self.cache = cache or get_global_cache()
        self.client = client or get_global_client()
