from loguru import logger
from typing import List, Any, Optional

######################################################################################################################################
def check_component_register(classname: str, actions_register: List[Any]) -> Any:
    for component in actions_register:
        if classname == component.__name__:
            return component
    logger.warning(f"{classname}不在{actions_register}中")
    return None
######################################################################################################################################
def check_conversation_action(actionname: str, actionvalues: List[str], actions_register: List[Any]) -> bool:
    from auxiliary.target_and_message_format_handle import parse_target_and_message
    from auxiliary.target_and_message_format_handle import check_target_and_message_format

    if actionname not in [component.__name__ for component in actions_register]:
        # 不是一个对话类型,不用检查
        return True
    
    # 检查带@target>message类型的Action有无错误内容
    for value in actionvalues:
        if check_target_and_message_format(value):
            pair = parse_target_and_message(value)
            target: Optional[str] = pair[0]
            message: Optional[str] = pair[1]
            if target is None or message is None:
                logger.error(f"target is None: {value}")
                return False
    # 是一个对话类型，检查完成
    return True
######################################################################################################################################