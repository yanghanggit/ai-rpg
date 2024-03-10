###
### 测试与LLM无关的代码，和一些尝试
###
import sys
import json
import os
from builder import WorldBuilder, StageBuilder, NPCBuilder


def main():

    try:
        path = "./yanghang_stage1.json"
        with open(path, "r") as file:
            json_data = json.load(file)
            print(json_data)
            #
            world_builder = WorldBuilder()
            world_builder.build(json_data)
            
            print(world_builder)
            for stage_builder in world_builder.stage_builders:
                print(stage_builder)
                for npc_builder in stage_builder.npc_builders:
                    print(npc_builder)

            print("==============================================")
            world = world_builder.all()
            print("?")



        
    except Exception as e:
        print(e)


            

        

if __name__ == "__main__":
    main()