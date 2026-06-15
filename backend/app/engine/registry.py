"""策略注册表——自动发现并注册所有策略。"""

import importlib
import os
import pkgutil
from typing import Dict, Type

from .base import BaseStrategy

_strategies: Dict[str, BaseStrategy] = {}


def register(strategy_class: Type[BaseStrategy]):
    """注册策略类（可作装饰器使用）。"""
    instance = strategy_class()
    _strategies[instance.name] = instance
    return strategy_class


def get_strategy(name: str) -> BaseStrategy:
    return _strategies.get(name)


def get_all_strategies() -> Dict[str, BaseStrategy]:
    return dict(_strategies)


def load_all_strategies():
    """自动发现并注册 engine.strategies 子包中的所有策略模块。"""
    from . import strategies  # noqa: ensure subpackage importable
    package_dir = os.path.dirname(strategies.__file__)
    for _, module_name, _ in pkgutil.iter_modules([package_dir]):
        if module_name.startswith("_"):
            continue
        importlib.import_module(f'.strategies.{module_name}', package=__package__)
