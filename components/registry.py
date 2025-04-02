from typing import Any, Dict, TypeVar, cast, Final


# TypeVar 是一个泛型，用于表示任意类型
T = TypeVar("T")

# component 装饰器
COMPONENTS_REGISTRY: Final[Dict[str, Any]] = {}


def register_component_class(cls: T) -> T:

    # 注册组件类
    COMPONENTS_REGISTRY[cast(Any, cls).__name__] = cls

    ## 为了兼容性，给没有 __deserialize_component__ 方法的组件添加一个空实现
    def _dummy_deserialize_component__(component_data: Dict[str, Any]) -> None:
        pass

    if not hasattr(cast(Any, cls), "__deserialize_component__"):
        cast(Any, cls).__deserialize_component__ = _dummy_deserialize_component__

    return cls


# action 装饰器
ACTIONS_REGISTRY: Final[Dict[str, Any]] = {}


def register_action_class_2(cls: T) -> T:

    # 注册动作类
    ACTIONS_REGISTRY[cast(Any, cls).__name__] = cls

    ## 为了兼容性，给没有 __deserialize_component__ 方法的组件添加一个空实现
    def _dummy_deserialize_component__(component_data: Dict[str, Any]) -> None:
        pass

    if not hasattr(cast(Any, cls), "__deserialize_component__"):
        cast(Any, cls).__deserialize_component__ = _dummy_deserialize_component__

    return cls
