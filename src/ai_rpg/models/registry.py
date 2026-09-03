"""ECS 组件类型注册模块。

提供全局组件类型注册表和装饰器，用于：
- 组件序列化/反序列化时的类型查找
- 动作组件的自动清理机制
"""

from typing import (
    Any,
    Dict,
    Final,
    Type,
    TypeVar,
)
from pydantic import create_model
from ..entitas.components import Component

############################################################################################################
COMPONENT_TYPES: Final[Dict[str, Type[Component]]] = {}
ComponentT = TypeVar("ComponentT", bound=Component)


############################################################################################################
def register_component_type(cls: Type[ComponentT]) -> Type[ComponentT]:
    """注册组件类型到全局注册表。"""
    # 检查：确保类是 Component 的子类
    if not issubclass(cls, Component):
        assert False, f"{cls.__name__} is not a valid BaseModel/Component class."

    # 注册类到全局字典
    class_name = cls.__name__
    if class_name in COMPONENT_TYPES:
        assert False, f"Class {class_name} is already registered."

    COMPONENT_TYPES[class_name] = cls
    return cls


############################################################################################################
ACTION_COMPONENT_TYPES: Final[Dict[str, Type[Component]]] = {}


def register_action_component_type(cls: Type[ComponentT]) -> Type[ComponentT]:
    """注册动作组件类型到全局注册表。"""
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
def create_component_type(class_name: str, **fields: Any) -> Type[Component]:
    """根据类名动态创建一个 Component 子类并注册到 COMPONENT_TYPES。

    用于为某个 Stage 生成唯一组件类型等场景；字段定义格式与
    pydantic.create_model 一致（字段名=(类型, 默认值)）。

    幂等：若同名类已注册，直接返回已有类（便于蓝图/存档跨进程重建）。

    示例：
        MyComponent = create_component_type("MyComponent")
    """
    assert (
        isinstance(class_name, str) and class_name.strip() != ""
    ), "动态组件类名不能为空"

    # 幂等：已注册则直接复用（同一标记在反序列化时可能被重复解析）
    existing = COMPONENT_TYPES.get(class_name)
    if existing is not None:
        return existing

    component_cls = create_model(class_name, __base__=Component, **fields)
    assert issubclass(
        component_cls, Component
    ), f"{class_name} is not a valid BaseModel/Component class."

    COMPONENT_TYPES[class_name] = component_cls
    return component_cls


############################################################################################################
def resolve_component_type(name: str, data: Dict[str, Any]) -> Type[Component]:
    """解析组件类型：优先查注册表；未注册时按 data 惰性重建。

    动态创建的组件类（如每个 Stage 的唯一组件）只存在于创建它的进程
    内存中。当蓝图/存档在另一个进程被反序列化时，需要根据序列化数据把
    这类组件类按需重建出来。字段类型从 data 的值推断（适用于标量字段；
    嵌套模型暂不支持动态重建）。
    """
    comp_cls = COMPONENT_TYPES.get(name)
    if comp_cls is not None:
        return comp_cls

    # 未注册：按 data 推断字段并动态重建（空 data 即无字段标记组件）
    fields = {key: (type(value), ...) for key, value in data.items()}
    return create_component_type(name, **fields)


############################################################################################################
