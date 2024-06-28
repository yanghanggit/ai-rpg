from typing import List, Optional
from loguru import logger
from my_format_string.target_and_message_format_string import is_target_and_message, parse_target_and_message

class ActorAction:

    def __init__(self, actor_name: str, action_name: str, values: List[str]) -> None:
        self._actor_name = actor_name  
        self._action_name = action_name
        self._values = values
#######################################################################################################################################
    def __str__(self) -> str:
        return f"ActorAction({self._actor_name}, {self._action_name}, {self._values})"
#######################################################################################################################################
    def __repr__(self) -> str:
        return f"ActorAction({self._actor_name}, {self._action_name}, {self._values})"
#######################################################################################################################################
    def join_values(self, symbol: str = " ") -> str:
        if len(self._values) == 0:
            return ""
        return symbol.join(self._values)
####################################################################################################################################### 
    def bool_value(self, index: int) -> bool:
        if index >= len(self._values):
            return False
        return self._values[index].lower() == "yes" or self._values[index].lower() == "true"
#######################################################################################################################################
    def value(self, index: int) -> str:
        if index >= len(self._values):
            return ""
        return self._values[index]
#######################################################################################################################################
    def target_and_message_values(self) -> List[tuple[str, str]]:

        result: List[tuple[str, str]] = []

        for value in self._values:
            if not is_target_and_message(value):
                #logger.error(f"target is None: {value}")
                continue

            tp = parse_target_and_message(value)
            target: Optional[str] = tp[0]
            message: Optional[str] = tp[1]
            if target is None or message is None:
                logger.error(f"target is None: {value}")
                continue
            
            result.append((target, message))

        return result
#######################################################################################################################################