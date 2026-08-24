"""提示词生成器注册表：标记并收集所有"提示词生成器"函数，供随时枚举查询。"""

from typing import Callable, Dict, TypeVar

_PromptBuilder = TypeVar("_PromptBuilder", bound=Callable[..., str])

_registry: Dict[str, Callable[..., str]] = {}


#######################################################################################################################################
def prompt_builder(func: _PromptBuilder) -> _PromptBuilder:
    """标记一个函数为提示词生成器，并注册到全局表中（原样返回函数，不做任何包装）。"""
    key = f"{func.__module__}.{func.__qualname__}"
    assert key not in _registry, f"提示词生成器重复注册: {key}"
    _registry[key] = func
    return func


#######################################################################################################################################
def get_prompt_builders() -> Dict[str, Callable[..., str]]:
    """返回当前已注册的全部提示词生成器（模块限定名 -> 函数）。"""
    return dict(_registry)
