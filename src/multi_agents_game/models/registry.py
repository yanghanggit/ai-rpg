from typing import (
    Any,
    Dict,
    NamedTuple,
    Type,
    TypeVar,
    Final,
    cast,
)

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
