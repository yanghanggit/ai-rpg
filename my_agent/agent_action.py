from typing import List, Optional, Dict
from loguru import logger
import my_format_string.target_and_message_format_string 
import json


class AgentAction:

    def __init__(self, actor_name: str, action_name: str, values: List[str]) -> None:
        self._actor_name: str = actor_name
        self._action_name: str = action_name
        self._values: List[str] = values

    #######################################################################################################################################
    # def join_values(self, symbol: str = " ") -> str:
    #     if len(self._values) == 0:
    #         return ""
    #     return symbol.join(self._values)
    

    # " ".join()

    #######################################################################################################################################
    # def bool_value(self, index: int) -> bool:
    #     if index >= len(self._values):
    #         return False
    #     return (
    #         self._values[index].lower() == "yes"
    #         or self._values[index].lower() == "true"
    #     )

    #######################################################################################################################################
    # def value(self, index: int) -> str:
    #     if index >= len(self._values):
    #         return ""
    #     return self._values[index]

    #######################################################################################################################################
    # def target_and_message_values(self) -> List[tuple[str, str]]:

    #     result: List[tuple[str, str]] = []

    #     for value in self._values:
    #         if not my_format_string.target_and_message_format_string.is_target_and_message(value):
    #             # logger.error(f"target is None: {value}")
    #             continue

    #         tp = my_format_string.target_and_message_format_string.parse_target_and_message(value)
    #         target: Optional[str] = tp[0]
    #         message: Optional[str] = tp[1]
    #         if target is None or message is None:
    #             logger.error(f"target is None: {value}")
    #             continue

    #         result.append((target, message))

    #     return result

    #######################################################################################################################################
    # def serialization(self) -> str:

    #     out_put: Dict[str, List[str]] = {}
    #     out_put[self._action_name] = self._values
    #     return json.dumps(out_put, ensure_ascii=False)


#######################################################################################################################################
