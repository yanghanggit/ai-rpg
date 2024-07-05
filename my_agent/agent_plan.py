from typing import List, Dict, Any, Optional
import json
from loguru import logger
from my_agent.my_json import merge, is_repeat, is_markdown_json_block, extract_markdown_json_block
from my_agent.agent_action import AgentAction

############################################################################################################
############################################################################################################
############################################################################################################
class AgentPlanJSON:

    def __init__(self, raw_data: str) -> None:
        self._raw_data: str = str(raw_data)
        self._output: str = str(raw_data)

    def extract_md_json_block(self) -> 'AgentPlanJSON':
        if is_markdown_json_block(self._output):
            self._output = extract_markdown_json_block(self._output)
        return self
    
    def merge_repeat_json(self) -> 'AgentPlanJSON':
        if is_repeat(self._output):
            merge_res = merge(self._output)
            if merge_res is not None:
                self._output = json.dumps(merge_res, ensure_ascii=False)
        return self

    @property  
    def output(self) -> str:
        return self._output
    
    def __str__(self) -> str:
        return self._output
############################################################################################################
############################################################################################################
############################################################################################################
class AgentPlan:

    def __init__(self, name: str, raw_data: str) -> None:

        self._name: str = name  
        self._raw: str = raw_data
        self._json: Dict[str, List[str]] = {}
        self._actions: List[AgentAction] = []
        self._actions_dict: Dict[str, AgentAction] = {}

        # 处理特殊的情况, 例如出现了markdown json block与重复json的情况
        # GPT4 也有可能输出markdown json block。以防万一，我们检查一下。
        # GPT4 也有可能输出重复的json。我们合并一下。有可能上面的json block的错误也犯了，所以放到第二个步骤来做
        self.json_string = AgentPlanJSON(raw_data).extract_md_json_block().merge_repeat_json().output

        #核心执行
        self.load_then_build() 
############################################################################################################
    def load_then_build(self) -> None:
        try:
            json_data = json.loads(self.json_string)
            if not self.check_data_format(json_data):
                logger.error(f"[{self._name}] = ActorPlan, check_data_format error.")
                return
            
            self._json = json_data
            self.build(self._json)

        except Exception as e:
            logger.error(f"[{self._name}] = json.loads error.")
        return    
############################################################################################################
    def build(self, json: Dict[str, List[str]]) -> None:
        for key, value in json.items():
            action = AgentAction(self._name, key, value)
            self._actions.append(action)
            self._actions_dict[key] = action
############################################################################################################
    def check_data_format(self, json_data: Any) -> bool:
        for key, value in json_data.items():
            if not isinstance(key, str):
                return False
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                return False
        return True
############################################################################################################
    def get_action_by_key(self, actionname: str) -> Optional[AgentAction]:
        return self._actions_dict.get(actionname)
############################################################################################################
    def __str__(self) -> str:
        return f"ActorPlan({self._name}, {self._raw})"
############################################################################################################
    def __repr__(self) -> str:
        return f"ActorPlan({self._name}, {self._raw})"
############################################################################################################