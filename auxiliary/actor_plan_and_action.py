from typing import List, Dict, Any, Optional
import json
from loguru import logger
from auxiliary.error_json_handle import merge, is_repeat, is_markdown_json_block, extract_markdown_json_block


############################################################################################################
############################################################################################################
############################################################################################################
class MyJSONResponse:

    def __init__(self, raw_data: str) -> None:
        self._raw_data: str = str(raw_data)
        self._output: str = str(raw_data)

    def extract_md_json_block(self) -> 'MyJSONResponse':
        if is_markdown_json_block(self._output):
            self._output = extract_markdown_json_block(self._output)
        return self
    
    def merge_repeat_json(self) -> 'MyJSONResponse':
        if is_repeat(self._output):
            merge_res = merge(self._output)
            if merge_res is not None:
                self._output = json.dumps(merge_res)
        return self

    @property  
    def output(self) -> str:
        return self._output
    
    def __str__(self) -> str:
        return self._output
############################################################################################################
############################################################################################################
############################################################################################################
class ActorAction:
    def __init__(self, name: str = "", actionname: str = "", values: List[str] = []) -> None:
        self.name = name  
        self.actionname = actionname
        self.values = values

    def __str__(self) -> str:
        return f"ActorAction({self.name}, {self.actionname}, {self.values})"

    def __repr__(self) -> str:
        return f"ActorAction({self.name}, {self.actionname}, {self.values})"

    def single_value(self) -> str:
        if len(self.values) == 0:
            return ""
        return " ".join(self.values)
############################################################################################################
############################################################################################################
############################################################################################################
class ActorPlan:

    def __init__(self, name: str, raw_data: str) -> None:

        self.name: str = name  
        self._raw: str = raw_data
        self._json: Dict[str, List[str]] = {}
        self.actions: List[ActorAction] = []
        self.actions_dict: Dict[str, ActorAction] = {}

        # 处理特殊的情况, 例如出现了markdown json block与重复json的情况
        # GPT4 也有可能输出markdown json block。以防万一，我们检查一下。
        # GPT4 也有可能输出重复的json。我们合并一下。有可能上面的json block的错误也犯了，所以放到第二个步骤来做
        self.json_string = MyJSONResponse(raw_data).extract_md_json_block().merge_repeat_json().output

        #核心执行
        self.load_then_build() 
############################################################################################################
    def load_then_build(self) -> None:
        try:
            json_data = json.loads(self.json_string)
            if not self.check_data_format(json_data):
                logger.error(f"[{self.name}] = ActorPlan, check_data_format error.")
                return
            
            self._json = json_data
            self.build(self._json)

        except Exception as e:
            logger.error(f"[{self.name}] = json.loads error.")
        return    
############################################################################################################
    def build(self, json: Dict[str, List[str]]) -> None:
        for key, value in json.items():
            action = ActorAction(self.name, key, value)
            self.actions.append(action)
            self.actions_dict[key] = action
############################################################################################################
    def check_data_format(self, json_data: Any) -> bool:
        for key, value in json_data.items():
            if not isinstance(key, str):
                return False
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                return False
        return True
############################################################################################################
    def get_action_by_key(self, actionname: str) -> Optional[ActorAction]:
        return self.actions_dict.get(actionname)
############################################################################################################
    def __str__(self) -> str:
        return f"ActorPlan({self.name}, {self._raw})"
############################################################################################################
    def __repr__(self) -> str:
        return f"ActorPlan({self.name}, {self._raw})"
############################################################################################################