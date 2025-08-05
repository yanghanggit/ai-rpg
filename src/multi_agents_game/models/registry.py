from typing import (
    Dict,
    Type,
    TypeVar,
    Final,
)
from ..entitas.components import Component

############################################################################################################
COMPONENTS_REGISTRY: Final[Dict[str, Type[Component]]] = {}
T_COMPONENT = TypeVar("T_COMPONENT", bound=Type[Component])


############################################################################################################
# 注册组件类的装饰器
def register_component_class(cls: T_COMPONENT) -> T_COMPONENT:

    # 检查：确保类是 BaseModel 的子类（包括我们的 Component 和 MutableComponent）
    if not issubclass(cls, Component):
        assert False, f"{cls.__name__} is not a valid BaseModel/Component class."

    # 注册类到全局字典
    class_name = cls.__name__
    if class_name in COMPONENTS_REGISTRY:
        assert False, f"Class {class_name} is already registered."

    COMPONENTS_REGISTRY[class_name] = cls

    # Pydantic 组件不需要手动添加 deserialize_component_data 方法
    # Pydantic 自带序列化/反序列化功能
    return cls


############################################################################################################
ACTION_COMPONENTS_REGISTRY: Final[Dict[str, Type[Component]]] = {}


# 注册动作类的装饰器，必须同时注册到 COMPONENTS_REGISTRY 中
def register_action_class(cls: T_COMPONENT) -> T_COMPONENT:

    # 注册类到全局字典
    class_name = cls.__name__
    if class_name in ACTION_COMPONENTS_REGISTRY:
        raise ValueError(f"Class {class_name} is already registered.")

    ACTION_COMPONENTS_REGISTRY[class_name] = cls
    return cls


############################################################################################################
