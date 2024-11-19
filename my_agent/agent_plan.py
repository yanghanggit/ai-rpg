from dataclasses import dataclass
from typing import List, Dict, Any, Optional, cast
import json
from loguru import logger
from my_format_string.json_plan_response_handler import (
    JsonPlanResponseHandler,
)


@dataclass
class AgentAction:
    name: str
    action_name: str
    values: List[str]


#
class AgentPlanResponse:

    def __init__(self, name: str, response_content: str) -> None:

        self._name: str = name
        self._actions: List[AgentAction] = []
        self._raw_response_content: str = str(response_content)

        # 准备开始处理了
        if response_content != "":
            # 处理特殊的情况, 例如出现了markdown json block与重复json的情况
            # GPT4 也有可能输出markdown json block。以防万一，我们检查一下。
            # GPT4 也有可能输出重复的json。我们合并一下。有可能上面的json block的错误也犯了，所以放到第二个步骤来做
            fmt_string = (
                JsonPlanResponseHandler(response_content)
                .strip_json_code()
                .combine_duplicate_fragments()
                .output
            )

            # 核心执行
            json_data = self._load_json(fmt_string)
            self._build(json_data)

    ############################################################################################################
    @property
    def original_response_content(self) -> str:
        return self._raw_response_content

    ############################################################################################################
    def _load_json(self, input_str: str) -> Dict[str, List[str]]:

        try:

            load_ret = json.loads(input_str)
            if load_ret is None:
                logger.error(f"json.loads error. \n{input_str}")
                return {}

            if not self._check_fmt(load_ret):
                logger.error(f"ActorPlan, check_data_format error. \n{input_str}")
                return {}

            return cast(Dict[str, List[str]], load_ret)

        except Exception as e:
            logger.error(f"[{self._name}] = json.loads error. \n{e}")

        return {}

    ############################################################################################################
    def _build(self, json: Dict[str, List[str]]) -> None:
        self._actions.clear()
        for key, value in json.items():
            self._actions.append(AgentAction(self._name, key, value))

    ############################################################################################################
    def _check_fmt(self, json_data: Any) -> bool:

        if not isinstance(json_data, dict):
            logger.error(f"json_data is not dict: {json_data}")
            return False

        for key, value in json_data.items():
            if not isinstance(key, str):
                return False
            if not isinstance(value, list) or not all(
                isinstance(v, str) for v in value
            ):
                return False

        return True

    ############################################################################################################
    def get_action(self, action_name: str) -> Optional[AgentAction]:
        for action in self._actions:
            if action.action_name == action_name:
                return action
        return None

    ############################################################################################################
    def _concatenate_values(self, action_name: str) -> str:
        action = self.get_action(action_name)
        if action is None or len(action.values) == 0:
            return ""
        return " ".join(action.values)

    ############################################################################################################
    def _parse_boolean(self, action_name: str) -> bool:
        action = self.get_action(action_name)
        if action is None or len(action.values) == 0:
            return False
        return action.values[0].lower() == "yes" or action.values[0].lower() == "true"

    ############################################################################################################
