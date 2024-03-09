###
### 测试和LLM无关的工具型代码用
###

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
import sys
import json
from actor import Actor
from world import World

#from make_plan import stage_plan_prompt, stage_plan, npc_plan


class Console:

    #
    def __init__(self, name: str):
        self.name = name

    #
    def parse_command(self, input_val: str, split_str: str)-> str:
        if split_str in input_val:
            return input_val.split(split_str)[1].strip()
        return input_val

    #
    def parse_speak(self, input_val: str) -> tuple:
        if "@" not in input_val:
            return None, input_val
        start_index = input_val.index("@") + 1
        end_index = input_val.index(" ")
        p1 = input_val[start_index:end_index]
        message = input_val[end_index+1:]
        return p1, message
    
