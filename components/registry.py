from typing import Any, Dict, TypeVar, cast, Final


# TypeVar 是一个泛型，用于表示任意类型
T = TypeVar("T")

# component 装饰器
COMPONENTS_REGISTRY: Final[Dict[str, Any]] = {}


def register_component_class(cls: T) -> T:
    COMPONENTS_REGISTRY[cast(Any, cls).__name__] = cls
    return cls


# action 装饰器
ACTIONS_REGISTRY_2: Final[Dict[str, Any]] = {}


def register_action_class_2(cls: T) -> T:
    ACTIONS_REGISTRY_2[cast(Any, cls).__name__] = cls
    return cls
