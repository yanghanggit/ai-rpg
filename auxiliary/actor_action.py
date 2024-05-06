
from typing import List
import json
from typing import Any
from loguru import logger

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
    
    def combine_all_string_values_to_output(self) -> str:
        return " ".join(self.values)
############################################################################################################
class ActorPlan:

    def __init__(self, name: str, jsonstr: str) -> None:
        self.name: str = name  
        self.jsonstr: str = jsonstr
        self.json: dict[str, list[str]] = {}
        self.actions: List[ActorAction] = []

        try:
            json_data = json.loads(self.jsonstr)
            if not self.check_data_format(json_data):
                logger.error(f"[{self.name}] = ActorPlan, check_data_format error.")
                return
            
            self.json = json_data
            self.build(self.json)

        except Exception as e:
            logger.error(f"[{self.name}] = json.loads error.")
            return
        return    

    def check_data_format(self, json_data: Any) -> bool:
        for key, value in json_data.items():
            if not isinstance(key, str):
                return False
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                return False
        return True

    def build(self, json: dict[str, list[str]]) -> None:
        for key, value in json.items():
            action = ActorAction(self.name, key, value)
            self.actions.append(action)

    def __str__(self) -> str:
        return f"ActorPlan({self.name}, {self.jsonstr})"
    
    def __repr__(self) -> str:
        return f"ActorPlan({self.name}, {self.jsonstr})"
############################################################################################################