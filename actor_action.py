
from typing import List
import json


class ActorAction:

    def __init__(self) -> None:
        self.name: str = ""  
        self.actionname: str = ""
        self.values: list[str] = []

    def init(self, name: str, actionname: str, values: list[str]) -> None:
        self.name: str = name  
        self.actionname: str = actionname
        self.values: list[str] = values

    def __str__(self) -> str:
        return f"Action({self.name}, {self.actionname}, {self.values})"


class ActorPlan:

    def __init__(self, name: str, jsonstr: str) -> None:
        self.name: str = name  
        self.jsonstr: str = jsonstr
        self.json: json = None
        self.actions: List[ActorAction] = []

        try:
            print(f"ActorPlan __init__ {self.name}: {self.jsonstr}")
            json_data = json.loads(self.jsonstr)
            if not self.check_data_format(json_data):
                print(f"stage_plan error = {self.name} json format error")
                return
            
            self.json = json_data
            self.build(self.json)

        except Exception as e:
            print(f"ActorPlan __init__ = {e}")
            return
        return    

    def check_data_format(self, json_data: dict) -> bool:
        for key, value in json_data.items():
            if not isinstance(key, str):
                return False
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                return False
        return True

    def build(self, json: json) -> None:
        for key, value in json.items():
            action = ActorAction()
            action.init(self.name, key, value)
            self.actions.append(action)

    def __str__(self) -> str:
        return f"Plan({self.name}, {self.jsonstr}, {self.json})"
