from typing import Any, Dict, TypeVar, cast, Final


# TypeVar 是一个泛型，用于表示任意类型
T = TypeVar("T")

COMPONENTS_REGISTRY: Final[Dict[str, Any]] = {}


# component 装饰器
def register_component_class(cls: T) -> T:
    COMPONENTS_REGISTRY[cast(Any, cls).__name__] = cls
    return cls
