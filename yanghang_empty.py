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





# #
# def parse_input(input_val: str, split_str: str)-> str:
#     if split_str in input_val:
#         return input_val.split(split_str)[1].strip()
#     return input_val


# test_input1 = "@p1 hello world!"

# def extract_input(input_val: str) -> tuple:
#     start_index = input_val.index("@") + 1
#     end_index = input_val.index(" ")
#     p1 = input_val[start_index:end_index]
#     message = input_val[end_index+1:]
#     return p1, message


# """
# @someone hello world!!!!!!
# """




#
def main():


    console = Console("console")


    
    #
    while True:
        usr_input = input("[user input]: ")
        if "/quit" in usr_input:
            sys.exit()

        # elif "/t" in usr_input:
        #     command = "/t"
        #     input_content = console.parse_command(usr_input, command)
        #     print(f"</talk>:", input_content)

        #     tp = console.parse_speak(input_content)
        #     tp1 = tp[0]
        #     tp2 = tp[1]
        #     print(tp1)
        #     print(tp2)


        elif "/s" in usr_input:
            command = "/s"
            input_content = console.parse_command(usr_input, command)
            print(f"</speak>:", input_content)
            tp = console.parse_speak(input_content)
            tp1 = tp[0]
            tp2 = tp[1]
            print(tp1)
            print(tp2)
            speak2actors = []
            if tp1 == "all":
                print("123")
                #speak2actors.append(world_watcher.all_actors())
            else:
                ##find_actor = world_watcher.get_actor(tp1)
                ##speak2actors.append(find_actor)

            for actor in speak2actors:
                print(f"[{actor.name}] /s:", actor.call_agent(tp2))

            for actor in speak2actors:
                actor_res = actor.call_agent(tp2)
                print(f"[{actor.name}]=>" + actor_res)


            
            # if player.stage == None:
            #     continue
            ###

            # console.parse_input(usr_input, "")


        # tp = console.extract_input(usr_input)
       


        ##某人进入场景的事件
       # elif "/0" in usr_input:
            
        print("==============================================")

        

if __name__ == "__main__":
    main()