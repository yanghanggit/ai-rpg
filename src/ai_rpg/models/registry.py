"""ECS 组件类型注册模块。

提供全局组件类型注册表和装饰器，用于：
- 组件序列化/反序列化时的类型查找
- 动作组件的自动清理机制
"""

from typing import (
    Dict,
    Final,
    Type,
    TypeVar,
)
from loguru import logger
from ..entitas.components import Component, MutableComponent

############################################################################################################
COMPONENT_TYPES: Final[Dict[str, Type[Component]]] = {}
ComponentT = TypeVar("ComponentT", bound=Component)


############################################################################################################
def register_component_type(cls: Type[ComponentT]) -> Type[ComponentT]:
    """注册组件类型到全局注册表。

    将组件类注册到 COMPONENT_TYPES，用于序列化/反序列化时的类型查找。
    如果组件是 MutableComponent，会发出警告。

    Args:
        cls: 要注册的组件类，必须继承自 Component

    Returns:
        原组件类（支持装饰器语法）

    Raises:
        AssertionError: 如果类不是 Component 子类或已被注册
    """
    # 检查：确保类是 BaseModel 的子类（包括我们的 Component 和 MutableComponent）
    if not issubclass(cls, Component):
        assert False, f"{cls.__name__} is not a valid BaseModel/Component class."

    # 检查：如果是 MutableComponent，发出警告
    if issubclass(cls, MutableComponent):
        logger.warning(
            f"⚠️ 警告: {cls.__name__} 是一个 MutableComponent，使用可变组件可能会导致 ECS 系统中的状态不一致问题，请谨慎使用。"
        )

    # 注册类到全局字典
    class_name = cls.__name__
    if class_name in COMPONENT_TYPES:
        assert False, f"Class {class_name} is already registered."

    COMPONENT_TYPES[class_name] = cls
    return cls


############################################################################################################
ACTION_COMPONENT_TYPES: Final[Dict[str, Type[Component]]] = {}


def register_action_component_type(cls: Type[ComponentT]) -> Type[ComponentT]:
    """注册动作组件类型到全局注册表。

    将动作组件类注册到 ACTION_COMPONENT_TYPES，用于自动清理系统。
    必须在调用此装饰器前先使用 @register_component_type 注册。

    Args:
        cls: 要注册的动作组件类，必须已在 COMPONENT_TYPES 中注册

    Returns:
        原组件类（支持装饰器语法）

    Raises:
        AssertionError: 如果类未先注册到 COMPONENT_TYPES
        ValueError: 如果类已被注册到 ACTION_COMPONENT_TYPES
    """
    assert issubclass(
        cls, Component
    ), f"{cls.__name__} is not a valid BaseModel/Component class."
    assert (
        cls.__name__ in COMPONENT_TYPES
    ), f"{cls.__name__} must be registered in COMPONENT_TYPES before registering as an action."

    # 注册类到全局字典
    class_name = cls.__name__
    if class_name in ACTION_COMPONENT_TYPES:
        raise ValueError(f"Class {class_name} is already registered.")

    ACTION_COMPONENT_TYPES[class_name] = cls
    return cls


############################################################################################################
