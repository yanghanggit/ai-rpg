import sys
from typing import Any, Dict, TypeVar, cast, Final, get_origin

# TODO，后续可以用Type[T]来写的好一些。T = TypeVar("T", bound=Type[？])


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

    if _contains_set_type(cast(Any, cls)):
        assert False, f"{cast(Any, cls).__name__}: Component class contain set type !"
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

    if _contains_set_type(cast(Any, cls)):
        assert False, f"{cast(Any, cls).__name__}: Action class contain set type !"

    return cls


############################################################################################################
# 我的 base_model 装饰器，用于记住所有用到的 BaseModel
BASE_MODEL_REGISTRY: Final[Dict[str, Any]] = {}


def register_base_model_class(cls: T) -> T:

    BASE_MODEL_REGISTRY[cast(Any, cls).__name__] = cls

    if _contains_set_type(cast(Any, cls)):
        assert False, f"{cast(Any, cls).__name__}: BaseModel class contain set type !"

    return cls


############################################################################################################
def _contains_set_type(cls: Any) -> bool:
    """
    检查类的属性类型是否包含 set/Set, 本项目不允许有，会影响存储和序列化的流程。
    """
    annotations = getattr(cls, "__annotations__", {})
    for attr_name, attr_type in annotations.items():
        # 处理延迟注解（字符串形式的类型）
        if isinstance(attr_type, str):
            # 解析字符串类型（需要访问类的全局命名空间）
            global_namespace = sys.modules[cls.__module__].__dict__
            try:
                attr_type = eval(attr_type, global_namespace, {})
            except NameError:
                continue  # 忽略无法解析的类型

        # 获取泛型底层类型（如 Set[str] -> set）
        origin_type = get_origin(attr_type)
        if origin_type is set or attr_type is set:
            return True
    return False


############################################################################################################
