
from typing import List
import json
from typing import Any


class ActorAction:

    def __init__(self, name: str = "", actionname: str = "", values: List[str] = []) -> None:
        self.name = name  
        self.actionname = actionname
        self.values = values

    def __str__(self) -> str:
        return f"Action({self.name}, {self.actionname}, {self.values})"


class ActorPlan:

    def __init__(self, name: str, jsonstr: str) -> None:
        self.name: str = name  
        self.jsonstr: str = jsonstr
        self.json: dict[str, list[str]] = {}
        self.actions: List[ActorAction] = []

        #print(f"ActorPlan: {self.name} response = ", jsonstr)
        try:
            json_data = json.loads(self.jsonstr)
            if not self.check_data_format(json_data):
                print(f"ActorPlan __init__ json.loads = {self.name} error")
                return
            
            self.json = json_data
            self.build(self.json)

        except Exception as e:
            print(f"ActorPlan __init__ error = {e}")
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
        return f"Plan({self.name}, {self.jsonstr}, {self.json})"
