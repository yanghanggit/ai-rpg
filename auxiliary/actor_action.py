from typing import List, Dict
import json
from typing import Any
from loguru import logger

############################################################################################################
class ActorAction:
    def __init__(self, name: str = "", actionname: str = "", values: List[str] = []) -> None:
        self.name = name  
        self.actionname = actionname
        self.values = values
############################################################################################################
    def __str__(self) -> str:
        return f"ActorAction({self.name}, {self.actionname}, {self.values})"
############################################################################################################
    def __repr__(self) -> str:
        return f"ActorAction({self.name}, {self.actionname}, {self.values})"
############################################################################################################
    def single_value(self) -> str:
        return " ".join(self.values)
############################################################################################################





class ActorPlan:
    def __init__(self, name: str, raw_data: str) -> None:

        self.name: str = name  
        self.raw_data: str = raw_data
        self.json_data: Dict[str, List[str]] = {}
        self.actions: List[ActorAction] = []
        self.json_content = self.check_markdown_json_block_and_handle(self.raw_data)

        #核心执行
        self.load_then_build() 
############################################################################################################
    def load_then_build(self) -> None:
        try:
            json_data = json.loads(self.json_content)
            if not self.check_data_format(json_data):
                logger.error(f"[{self.name}] = ActorPlan, check_data_format error.")
                return
            
            self.json_data = json_data
            self.build(self.json_data)

        except Exception as e:
            logger.error(f"[{self.name}] = json.loads error.")
        return    
############################################################################################################
    def build(self, json: Dict[str, List[str]]) -> None:
        for key, value in json.items():
            action = ActorAction(self.name, key, value)
            self.actions.append(action)
############################################################################################################
    #gpt4 我也发现会出现这种情况。我会尝试解决这个问题。
    def check_markdown_json_block_and_handle(self, md_json_block: str) -> str:
        if "```json" in md_json_block:
            logger.error(f"ActorPlan: {self.name} has markdown json block {md_json_block}")
            copyvalue = str(md_json_block).strip()
            copyvalue = copyvalue.replace("```json", "").replace("```", "").strip()
            return copyvalue
        
        return md_json_block
############################################################################################################
    def check_data_format(self, json_data: Any) -> bool:
        for key, value in json_data.items():
            if not isinstance(key, str):
                return False
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                return False
        return True
############################################################################################################
    def __str__(self) -> str:
        return f"ActorPlan({self.name}, {self.raw_data})"
############################################################################################################
    def __repr__(self) -> str:
        return f"ActorPlan({self.name}, {self.raw_data})"
############################################################################################################