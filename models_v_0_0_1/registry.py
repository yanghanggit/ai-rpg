import sys
from typing import Any, Dict, NamedTuple, Type, TypeVar, Final, cast, get_origin
from pydantic import BaseModel

# 定义泛型
T_COMPONENT = TypeVar("T_COMPONENT", bound=Type[NamedTuple])
T_BASE_MODEL = TypeVar("T_BASE_MODEL", bound=Type[BaseModel])

############################################################################################################
COMPONENTS_REGISTRY: Final[Dict[str, Type[NamedTuple]]] = {}


# 注册组件类的装饰器
def register_component_class(cls: T_COMPONENT) -> T_COMPONENT:
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
    if _includes_set_type(cls):
        assert False, f"{class_name}: Component class contain set type !"

    return cls


############################################################################################################
ACTION_COMPONENTS_REGISTRY: Final[Dict[str, Type[NamedTuple]]] = {}


# 注册动作类的装饰器，必须同时注册到 COMPONENTS_REGISTRY 中
def register_action_class(cls: T_COMPONENT) -> T_COMPONENT:

    class_name = cls.__name__
    if class_name in ACTION_COMPONENTS_REGISTRY:
        raise ValueError(f"Class {class_name} is already registered.")

    ACTION_COMPONENTS_REGISTRY[class_name] = cls
    return cls


############################################################################################################
BASE_MODEL_REGISTRY: Final[Dict[str, Type[BaseModel]]] = {}


def register_base_model_class(cls: T_BASE_MODEL) -> T_BASE_MODEL:
    """
    注册 BaseModel 类到全局字典，避免重复注册。
    """
    class_name = cls.__name__
    if class_name in BASE_MODEL_REGISTRY:
        raise ValueError(f"Class {class_name} is already registered.")

    BASE_MODEL_REGISTRY[class_name] = cls

    if _includes_set_type(cls):
        assert False, f"{class_name}: BaseModel class contain set type !"

    return cls


############################################################################################################
def _includes_set_type(cls: Any) -> bool:
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

        if origin_type is BaseModel or attr_type is BaseModel:
            # 检查是否是 BaseModel 的子类
            return _includes_set_type(attr_type)

    return False


"""
@final
@register_component_class2
class TestComponent(NamedTuple):
    name: str
    runtime_index: int


def main() -> None:

    for key, value in __COMPONENTS_REGISTRY__.items():
        print(f"Key: {key}, Value: {value}")

    new_comp = TestComponent._make(("hello world", 1002))
    print(new_comp)

    component_data = new_comp._asdict()
    print(component_data)

    comp_class = __COMPONENTS_REGISTRY__.get(TestComponent.__name__)
    assert comp_class is not None

    restore_comp = comp_class(*component_data.values())
    assert restore_comp is not None
    print(restore_comp)
    assert restore_comp is not new_comp, "restore_comp should not be equal to new_comp"


if __name__ == "__main__":
    main()
"""
