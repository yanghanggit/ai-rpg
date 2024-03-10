import sys
from player import Player
from console import Console
from run_stage import run_stage
from actor_enter_stage import actor_enter_stage
from actor_broadcast import actor_broadcast
from actor_attack import actor_attack
import json
from builder import WorldBuilder
from actor import Actor
from world import World
from typing import Optional
from npc import NPC
from stage import Stage
from action import Action

######################################################################
##################################################################################################################################################################################################################
##################################################################################################################################################################################################################
##################################################################################################################################################################################################################
#
init_archivist = f"""
# 游戏世界存档
- 大陆纪元2000年1月1日，冬夜.
- 温斯洛平原的深处的“悠扬林谷”中的“老猎人隐居的小木屋”里。
- “卡斯帕·艾伦德”坐在他的“老猎人隐居的小木屋”中的壁炉旁，在沉思和回忆过往，并向壁炉中的火投入了一根木柴。
- 他的小狗（名叫"断剑"）在屋子里的一角睡觉。
- 一只老鼠（名叫"坏运气先生"）在屋子里的另一角找到了一些食物。
"""
load_prompt = f"""
# 你需要读取存档
## 步骤:
- 第1步，读取{init_archivist}.
- 第2步：理解其中所有的信息
- 第3步：理解其中关于你的信息（如何提到了你，那就是你）
- 第3步：根据信息更新你的最新状态与逻辑.
## 输出规则：
- 保留关键信息(时间，地点，人物，事件)，不要推断，增加与润色。输出在保证语意完整基础上字符尽量少。
"""
#
def main() -> None:

    world: Optional[World]  = None
    path: str = "./yanghang_stage1.json"
    console: Console = Console("系统管理员")
    player: Optional[Player]  = None

    try:
        with open(path, "r") as file:
            json_data = json.load(file)
          
            world_builder = WorldBuilder()
            world_builder.build(json_data)
    
            world = world_builder.create_world()
            world.connect_all()
            world.load_all(load_prompt)

    except Exception as e:
        print(e)
        return

    print("//////////////////////////////////////////////////////////////////////////////////////")
    print("//////////////////////////////////////////////////////////////////////////////////////")
    print("//////////////////////////////////////////////////////////////////////////////////////")
    #
    while True:
        usr_input = input("[user input]: ")
        if "/quit" in usr_input:
            sys.exit()
 
        elif "/call" in usr_input:
            command = "/call"
            input_content = console.parse_command(usr_input, command)
            print(f"</call>:", input_content)
            parse_res: tuple[str, str] = console.parse_at_symbol(input_content)
            target = parse_res[0]
            content = parse_res[1]
            if target == None:
                print("/call 没有指定@目标") 
                continue

            speak2actors: list[Actor] = []
            if target == "all":
                speak2actors = world.all_actors()
            else:
                find_actor = world.get_actor(target)
                if find_actor is not None:
                    speak2actors.append(find_actor)

            for actor in speak2actors:
                print(f"[{actor.name}] /call:", actor.call_agent(content))
            print("==============================================")

        ##
        elif "/createplayer" in usr_input:
            command = "/createplayer"
            profile_character = console.parse_command(usr_input, command)
            print(f"/createplayer:", profile_character)
            if player is None:
                player = Player("yang_hang")
                player.profile_character = profile_character
                player.max_hp = 1000000
                player.hp = 1000000
                player.damage = 100000
                notify_world = world.call_agent(f"""你知道了如下事件：{player.name}加入了这个世界, 他是{player.profile_character}""")
                print(f"[{world.name}]:", notify_world)
            else:
                print(f"[{player.name}]=>", f"你已经在这个世界了")

            #
            console.current_actor = player
            print("你控制了：", player.name)

        elif "/who" in usr_input:
            command = "/who"
            actor_name = console.parse_command(usr_input, command)
            change_actor = world.get_actor(actor_name)
            if change_actor is None or change_actor == console.current_actor:
                continue
            if console.current_actor is not None:
                print(f"/who 你 当前 控制=>", console.current_actor.name)
            console.current_actor = change_actor
            print(f"/who 你 现在 控制了=>", console.current_actor.name)
                   
        elif "/runstage" in usr_input:
            command = "/runstage"
            stage_name = console.parse_command(usr_input, command)    
            stage = world.get_stage(stage_name) 
            if stage is not None:
                run_stage(stage, [])    
            print("==============================================")

        elif "/enterstage" in usr_input:
            command = "/enterstage"
            stage_name = console.parse_command(usr_input, command)
            stage = world.get_stage(stage_name)
            if stage is None or console.current_actor is None:
                continue
            if isinstance(console.current_actor, Player) or isinstance(console.current_actor, NPC):
                actor_enter_stage(console.current_actor, stage)
            print("==============================================")
            
        elif "/say2everyone" in usr_input: 
            command = "/say2everyone"
            content = console.parse_command(usr_input, command)
            if console.current_actor is None:
                continue

            if isinstance(console.current_actor, Player) or isinstance(console.current_actor, NPC) or isinstance(console.current_actor, Stage):
                actor_broadcast(console.current_actor, content)
            print("==============================================")

        elif "/attack" in usr_input:
            command = "/attack"
            target_name = console.parse_command(usr_input, command)    
            if  console.current_actor is None:
                continue
            if isinstance(console.current_actor, Player) or isinstance(console.current_actor, NPC) or isinstance(console.current_actor, Stage):
                stage_and_action: tuple[Optional[Stage], Optional[Action]] = actor_attack(console.current_actor, target_name)
                stage = stage_and_action[0]
                action = stage_and_action[1]
                if stage is not None and action is not None:
                    run_stage(stage, [action])          
            print("==============================================")


if __name__ == "__main__":
    main()