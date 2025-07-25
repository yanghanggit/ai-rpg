from typing import (
    Any,
    Dict,
    NamedTuple,
    Type,
    TypeVar,
    Final,
    cast,
    get_origin,
    get_type_hints,
)
from pydantic import BaseModel
import inspect

############################################################################################################
COMPONENTS_REGISTRY: Final[Dict[str, Type[NamedTuple]]] = {}
T_COMPONENT = TypeVar("T_COMPONENT", bound=Type[NamedTuple])


# 注册组件类的装饰器
def register_component_class(cls: T_COMPONENT) -> T_COMPONENT:

    # 新增检查：确保类是通过 NamedTuple 创建的
    if not (
        issubclass(cls, tuple)
        and hasattr(cls, "_fields")
        and hasattr(cls, "__annotations__")
    ):
        assert False, f"{cls.__name__} is not a valid NamedTuple class."

    # 注册类到全局字典
    class_name = cls.__name__
    if class_name in COMPONENTS_REGISTRY:
        assert False, f"Class {class_name} is already registered."

    COMPONENTS_REGISTRY[class_name] = cls

    # 外挂一个方法到类上
    if not hasattr(cast(Any, cls), "__deserialize_component__"):
        ## 为了兼容性，给没有 __deserialize_component__ 方法的组件添加一个空实现
        def _dummy_deserialize_component__(component_data: Dict[str, Any]) -> None:
            pass

        cast(Any, cls).__deserialize_component__ = _dummy_deserialize_component__

    # 不允许有 set 类型的属性，影响序列化和存储
    if _has_set_attr(cls):
        assert False, f"{class_name}: Component class contain set type !"

    return cls


############################################################################################################
ACTION_COMPONENTS_REGISTRY: Final[Dict[str, Type[NamedTuple]]] = {}


# 注册动作类的装饰器，必须同时注册到 COMPONENTS_REGISTRY 中
def register_action_class(cls: T_COMPONENT) -> T_COMPONENT:

    # 注册类到全局字典
    class_name = cls.__name__
    if class_name in ACTION_COMPONENTS_REGISTRY:
        raise ValueError(f"Class {class_name} is already registered.")

    ACTION_COMPONENTS_REGISTRY[class_name] = cls
    return cls


############################################################################################################
# BASE_MODEL_REGISTRY: Final[Dict[str, Type[BaseModel]]] = {}
# T_BASE_MODEL = TypeVar("T_BASE_MODEL", bound=Type[BaseModel])


# def register_base_model_class(cls: T_BASE_MODEL) -> T_BASE_MODEL:

#     # 新增检查：确保类是通过 BaseModel 创建的
#     if not issubclass(cls, BaseModel):
#         assert False, f"{cls.__name__} is not a valid BaseModel class."

#     # 注册类到全局字典
#     class_name = cls.__name__
#     if class_name in BASE_MODEL_REGISTRY:
#         raise ValueError(f"Class {class_name} is already registered.")

#     BASE_MODEL_REGISTRY[class_name] = cls

#     # 不可以有 set 类型的属性，影响序列化和存储
#     if _has_set_attr(cls):
#         assert False, f"{class_name}: BaseModel class contain set type !"

#     return cls


############################################################################################################
def _is_set_type(t: type) -> bool:
    """检查类型是否为 set 或 typing.Set"""
    origin = get_origin(t) if t is not None else None
    return origin is set or t is set


############################################################################################################
def _is_user_defined_class(cls: type) -> bool:
    """检查是否为用户自定义类（非内置类型）"""
    return inspect.isclass(cls) and cls.__module__ not in ("builtins", "typing")


############################################################################################################
def _has_set_attr(cls: type, visited: set[type] | None = None) -> bool:
    """递归检查类中是否存在 set/Set 类型的属性"""
    if visited is None:
        visited = set()

    # 避免重复检查
    if cls in visited:
        return False
    visited.add(cls)

    try:
        # 获取类型注解（处理前向引用）
        annotations = get_type_hints(cls)
    except Exception:
        annotations = {}

    # 检查类型注解
    for attr_type in annotations.values():
        if _is_set_type(attr_type):
            return True
        if _is_user_defined_class(attr_type) and _has_set_attr(attr_type, visited):
            return True

    # 检查类属性值
    for attr_name in vars(cls):
        if attr_name.startswith("__") and attr_name.endswith("__"):
            continue  # 跳过魔术方法

        attr_value = getattr(cls, attr_name)

        # 跳过方法
        if inspect.ismethod(attr_value) or inspect.isfunction(attr_value):
            continue

        # 检查是否为 set 实例
        if isinstance(attr_value, set):
            return True

        # 检查值类型是否为用户自定义类
        attr_class = type(attr_value)
        if _is_user_defined_class(attr_class) and _has_set_attr(attr_class, visited):
            return True

    return False


############################################################################################################
