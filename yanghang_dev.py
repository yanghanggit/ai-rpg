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
######################################################################
##################################################################################################################################################################################################################
##################################################################################################################################################################################################################
##################################################################################################################################################################################################################
def director_prompt(stage, movie_script):
    return f"""
    # 你按着我的给你的脚本来演绎过程，并适当润色让过程更加生动。
    ## 剧本如下
    - {movie_script}
    ## 步骤
    - 第1步：理解我的剧本
    - 第2步：根据剧本，完善你的故事讲述。要保证和脚本的结果一致。
    - 第3步：更新你的记忆
    ## 输出规则
    - 输出在保证语意完整基础上字符尽量少。
    """
######################################################################
##################################################################################################################################################################################################################
##################################################################################################################################################################################################################
##################################################################################################################################################################################################################
#
def actor_confirm_prompt(actor, stage_state):
    stage = actor.stage
    actors = stage.actors
    actor_names = [actor.name for actor in actors]
    all_names = ' '.join(actor_names)
    return f"""
    # 这些事已经发生的事精，你更新了记忆
    - {stage_state}
    - 你知道 {all_names} 都还存在。
    """
######################################################################
##################################################################################################################################################################################################################
##################################################################################################################################################################################################################
##################################################################################################################################################################################################################

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
            if player.stage != None:
                print(f"[{player.name}]=>", f"你已经在{player.stage.name}里了")
                continue
            #
            stage.add_actor(player)
            #
            enter_event = f"""你知道了发生了如下事件：{player.name}进入了{stage.name}, 他是{player.description}"""
            print(f"/enterstage", enter_event)
            new_stage_memory(stage, enter_event)
            playeraction = Action(player, [STAY], [stage.name], [""], [""])
            run_stage(stage, [playeraction])      
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
            new_stage_memory(stage, enter_event)
            run_stage(old_hunters_cabin, [])         
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


######################################################################
def new_stage_memory(stage: Stage, content: str):
    stage.chat_history.append(HumanMessage(content=content))
    for actor in stage.actors:
        if isinstance(actor, NPC):
            actor.chat_history.append(HumanMessage(content=content))
######################################################################
            





#### 待重构！！！！！！！！！！！！！！            
def run_stage(current_stage: Stage, players_action: list[Action]) -> None:        
    #制作计划
    make_plan = MakePlan(current_stage)
    print("make_all_npcs_plan...")
    make_plan.make_all_npcs_plan()

    print("make_stage_paln...")
    make_plan.make_stage_paln()
    
    print("add_players_plan...")
    make_plan.add_players_plan(players_action)

    if len(make_plan.actions) == 0:
        print(f"{current_stage.name}目前没有行动与计划")
        return

    ##记录发生的事
    movie_script: list[str] = []
    ###谁想离开？
    who_wana_leave = make_plan.who_wana_leave()
    ###谁死了
    who_is_dead: list[Actor] = []

    print("所有人允许说话 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    for action in make_plan.actions:
        if (len(action.say) > 0):
            movie_script.append(f"{action.planer.name}说：{action.say[0]}")
            print(f"{action.planer.name}说：{action.say[0]}")

    print("处理战斗 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    fight_actions = make_plan.get_fight_actions()
    if len(fight_actions) > 0:
        #
        movie_script.append("发生了战斗！")
        print("发生了战斗！")
        #
        for action in fight_actions:
            print(f"fight action: {action}")
            movie_script.append(f"{action.planer.name}对{action.targets}发动了攻击")
            print(f"{action.planer.name}对{action.targets}发动了攻击")

            for target_name in action.targets:
                
                target = current_stage.get_actor(target_name)
                if target == None:
                    continue

                #被攻击不能走
                if target in who_wana_leave:
                    who_wana_leave.remove(target) 

                #最简单战斗计算
                target.hp -= action.planer.damage    
                movie_script.append(f"{action.planer.name}对{action.targets}产生了{action.planer.damage}点伤害")
                if target.hp <= 0:
                    who_is_dead.append(target)
                    movie_script.append(f"{target.name}已经死亡")
                    print(f"{target.name}已经死亡")
                else:
                    print(f"{target.name}剩余{target.hp/target.max_hp*100}%血量")
                print("-------------------------------------------------------------------------")

    print("处理战斗结果，死了的 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    for actor in who_is_dead:
        actor.stage.remove_actor(actor)
        movie_script.append(f"{actor.name}死了，离开了这个世界")
        print(f"{actor.name}死了，离开了这个世界")

    ##处理离开的
    print("脱离本场景的 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    for actor in who_wana_leave:
        actor.stage.remove_actor(actor)
        movie_script.append(f"{actor.name}离开了{current_stage.name}")
        print(f"{actor.name}离开了{current_stage.name}")
        
    print("最后组装剧本 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    movie_script_str = '\n'.join(movie_script)
    if len(movie_script_str) == 0:
        movie_script_str = "剧本为空，说明没有任何事发生，更新状态即可"
        print(f"{current_stage.name}剧本为空，说明没有任何事发生，更新状态即可")

    #
    print("按着剧本更新场景 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    director_prompt_str = director_prompt(current_stage, movie_script_str)
    director_res = current_stage.call_agent(director_prompt_str)
    print(f"[{current_stage.name}]:", director_res)

    ##
    print("npc确认行动++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    for actor in current_stage.get_all_npcs():
        last_memory = f"""
        # 你知道发生了下面的事，并更新了你的记忆：
        {movie_script_str}
        """
        actor.chat_history.append(AIMessage(content=last_memory))
        actor_comfirm_prompt_str = actor_confirm_prompt(actor, director_res)
        actor_res = actor.call_agent(actor_comfirm_prompt_str)
        print(f"[{actor.name}]~" + actor_res)

    print("最后处理离开或者战斗中逃跑的人，去往某个场景（必须知道场景名字），此时他们已经脱离本场景 ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    leave_actions = make_plan.get_leave_actions()
    for actor in who_wana_leave:
        if actor == current_stage:
            print(f"{actor.name} 是当前场景不能逃跑！！！")
            continue
        if actor.stage != None:
            print(f"{actor.name} 还有在{actor.stage.name}里，是个错误，说明上面没有移除成功")
            continue    
        for action in leave_actions:
            if actor != action.planer:
                continue
            target_stage = current_stage.world.get_stage(action.targets[0])
            if target_stage == None:
                print(f"{actor.name} 想要去{action.targets[0]}，但是世界上没有这个地方")
                continue
            target_stage.add_actor(actor)
            enter_event = f"""你知道了发生了如下事件：{actor.name}进入了{target_stage.name}"""
            new_stage_memory(target_stage, enter_event)
            run_stage(target_stage, [])      
            break

    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")

if __name__ == "__main__":
    main()