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
from make_plan import stage_plan, npc_plan, MakePlan
from console import Console
from run_stage import run_stage

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
- 第2步：理解这些信息(尤其是和你有关的信息).
- 第3步：根据信息更新你的最新状态与逻辑.
## 输出规则：
- 保留关键信息(时间，地点，人物，事件)，不要推断，增加与润色。输出在保证语意完整基础上字符尽量少。
"""
#
def main():

    #load!!!!
    world_watcher = World("世界观察者")
    world_watcher.connect("http://localhost:8004/world/")
    log = world_watcher.call_agent(load_prompt)
    print(f"[{world_watcher.name}]:", log)
    print("==============================================")

    #
    old_hunter = NPC("卡斯帕·艾伦德")
    old_hunter.connect("http://localhost:8021/actor/npc/old_hunter/")
    log = old_hunter.call_agent(load_prompt)
    print(f"[{old_hunter.name}]:", log)
    print("==============================================")

     #
    old_hunters_cabin = Stage("老猎人隐居的小木屋")
    old_hunters_cabin.connect("http://localhost:8022/stage/old_hunters_cabin/")
    log = old_hunters_cabin.call_agent(load_prompt)
    print(f"[{old_hunters_cabin.name}]:", log)
    print("==============================================")

    #
    old_hunters_dog = NPC("小狗'断剑'")
    old_hunters_dog.connect("http://localhost:8023/actor/npc/old_hunters_dog/")
    log = old_hunters_dog.call_agent(load_prompt)
    print(f"[{old_hunters_dog.name}]:", log)
    print("==============================================")

    #
    melodious_forest_valley = Stage("悠扬林谷")
    melodious_forest_valley.connect("http://localhost:8024/stage/melodious_forest_valley/")
    log = melodious_forest_valley.call_agent(load_prompt)
    print(f"[{melodious_forest_valley.name}]:", log)
    print("==============================================")


    rat = NPC("坏运气先生")
    rat.connect("http://localhost:8025/actor/npc/rat/")
    log = rat.call_agent(load_prompt)
    print(f"[{rat.name}]:", log)
    print("==============================================")

    #
    world_watcher.add_stage(old_hunters_cabin)
    world_watcher.add_stage(melodious_forest_valley)
    #
    old_hunters_cabin.add_actor(old_hunter)
    old_hunters_cabin.add_actor(old_hunters_dog)
    old_hunters_cabin.add_actor(rat)

    #
    player = None
    console = Console("系统管理员")
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
            tp = console.parse_at_symbol(input_content)
            target = tp[0]
            content = tp[1]
            if target == None:
                print("/call 没有指定@目标") 
                continue

            speak2actors = []
            if target == "all":
                speak2actors = world_watcher.all_actors()
            else:
                find_actor = world_watcher.get_actor(target)
                if find_actor != None:
                    speak2actors.append(find_actor)

            for actor in speak2actors:
                print(f"[{actor.name}] /call:", actor.call_agent(content))
            print("==============================================")


        elif "/run" in usr_input:
            command = "/run"
            stage_name = console.parse_command(usr_input, command)
            if stage_name == None:
                print("/run error1 = ", stage_name, "没有找到这个场景") 
                continue
            stage = world_watcher.get_stage(stage_name)
            if stage == None:
                print("/run error2 = ", stage_name, "没有找到这个场景") 
                continue
            print(f"[{stage.name}] /run:")
            run_stage(stage, [])    
            print("==============================================")


        ##某人进入场景的事件
        elif "/player" in usr_input:
            command = "/player"
            description = console.parse_command(usr_input, command)
            print(f"/player:", description)
            if player == None:
                player = Player("yang_hang")
                if description != None or description != "":
                    player.description = description
                player.max_hp = 1000000
                player.hp = 1000000
                player.damage = 100000
                notify_world = world_watcher.call_agent(f"""你知道了如下事件：{player.name}加入了这个世界, 他是{player.description}""")
                print(f"[{world_watcher.name}]:", notify_world)
            else:
                print(f"[{player.name}]=>", f"你已经在这个世界了")


        elif "/enterstage" in usr_input:
            command = "/enterstage"
            stage_name = console.parse_command(usr_input, command)
            if stage_name == None:
                print("/enterstage error1 = ", stage_name, "没有找到这个场景") 
                continue
            stage = world_watcher.get_stage(stage_name)
            if stage == None:
                print("/enterstage error2 = ", stage_name, "没有找到这个场景") 
                continue
            if player == None:
                print("/enterstage error3 = ", "没有找到这个玩家") 
                continue
            if player.stage == stage:
                print(f"[{player.name}]=>", f"你已经在{stage.name}")
                continue

            if player.stage != None:
                old_stage = player.stage
                old_stage.remove_actor(player)
                print(f"[{player.name}]=>", f"你离开了{old_stage.name}")
                leave_event = f"""你知道了发生了如下事件：{player.name}离开了{old_stage.name}"""
                old_stage.add_memory(leave_event)
                print("==============================================")
    
            #
            stage.add_actor(player)
            print(f"[{player.name}]=>", f"你进入了{stage.name}")
            enter_event = f"""你知道了发生了如下事件：{player.name}进入了{stage.name}, 他是{player.description}"""
            stage.add_memory(enter_event)
            print("==============================================")

            
        elif "/talkall" in usr_input:
            command = "/talkall"
            content = console.parse_command(usr_input, command)
            if player == None:
                print("/talkall error1 = ", "没有找到这个玩家") 
                continue
            if player.stage == None:
                print(f"[{player.name}]=>", "你还没有进入任何场景")
                continue
            ###
            enter_event = f"""{player.name} 说 {content}"""
            print(f"[{player.name}]=>", enter_event)
            stage.add_memory(enter_event)
            run_stage(stage, [])         
            print("==============================================")

        elif "/attacknpc" in usr_input:
            command = "/attacknpc"
            target_name = console.parse_command(usr_input, command)
            if player == None:
                print("/talkall error1 = ", "没有找到这个玩家") 
                continue
            if player.stage == None:
                print(f"[{player.name}]=>", "你还没有进入任何场景")
                continue
                
            stage = player.stage
            target = stage.get_actor(target_name)
            if target == None:  
                print(f"[{player.name}]=>", f"没有找到这个人{target_name}")
                continue

            playaction = Action(player, [FIGHT], [target.name], [""], [""])
            run_stage(stage, [playaction])          
            print("==============================================")

       

if __name__ == "__main__":
    main()