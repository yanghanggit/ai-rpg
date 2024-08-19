from loguru import logger
from typing import List, Any


######################################################################################################################################
def check_component_register(classname: str, actions_register: List[Any]) -> Any:
    for component in actions_register:
        if classname == component.__name__:
            return component
    logger.warning(f"{classname}不在{actions_register}中")
    return None


######################################################################################################################################
