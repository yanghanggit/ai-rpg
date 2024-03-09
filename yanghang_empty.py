###
### 测试和LLM无关的工具型代码用
###

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
import sys
import json
from actor import Actor
from world import World
from stage import Stage
from stage import NPC
from player import Player
from action import Action, FIGHT, STAY, LEAVE
from make_plan import stage_plan_prompt, stage_plan, npc_plan
from console import Console
#
def main():
    #
    while True:
        usr_input = input("[user input]: ")
        if "/quit" in usr_input:
            sys.exit()

            
        print("==============================================")

        

if __name__ == "__main__":
    main()