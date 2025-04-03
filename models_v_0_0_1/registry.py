from typing import Any, Dict, Type, TypeVar, cast, Final
from pydantic import BaseModel

# 注意，不允许动！
SCHEMA_VERSION: Final[str] = "0.0.1"

# TypeVar 是一个泛型，用于表示任意类型
T = TypeVar("T")


############################################################################################################
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


############################################################################################################
# action 装饰器
ACTIONS_REGISTRY: Final[Dict[str, Any]] = {}


def register_action_class(cls: T) -> T:

    # 注册动作类
    ACTIONS_REGISTRY[cast(Any, cls).__name__] = cls

    ## 为了兼容性，给没有 __deserialize_component__ 方法的组件添加一个空实现
    def _dummy_deserialize_component__(component_data: Dict[str, Any]) -> None:
        pass

    if not hasattr(cast(Any, cls), "__deserialize_component__"):
        cast(Any, cls).__deserialize_component__ = _dummy_deserialize_component__

    return cls


############################################################################################################
# 我的 base_model 装饰器，用于记住所有用到的 BaseModel
BASE_MODEL_REGISTRY: Final[Dict[str, Any]] = {}


def register_base_model_class(cls: T) -> T:

    assert issubclass(
        cast(Any, cls), BaseModel
    ), f"cls must be a subclass of BaseModel, but got {cast(Any, cls).__name__}"

    BASE_MODEL_REGISTRY[cast(Any, cls).__name__] = cls
    return cls
