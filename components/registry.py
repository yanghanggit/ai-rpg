from typing import Dict, Any, Final

COMPONENTS_REGISTRY: Final[Dict[str, Any]] = {}


# component 装饰器
def register_component_class(cls: Any) -> Any:
    COMPONENTS_REGISTRY[cls.__name__] = cls
    return cls
