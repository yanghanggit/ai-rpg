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
    
    #
    world_watcher.add_stage(old_hunters_cabin)
    world_watcher.add_stage(melodious_forest_valley)
    #
    old_hunters_cabin.add_actor(old_hunter)
    old_hunters_cabin.add_actor(old_hunters_dog)

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
def run_stage(current_stage: Stage, players_action: list[Action]) -> None:
        
    actions_collector: list[Action] = []

    ###场景的
    sp = stage_plan(current_stage)
    actions_collector.append(sp)

    ###npc
    for npc in current_stage.get_all_npcs():
        np = npc_plan(npc)
        actions_collector.append(np)

    ###角色的
    if len(players_action) > 0:
        actions_collector.extend(players_action)

    if len(actions_collector) == 0:
        print("没有行动")
        return
    print("-------------------------------------------------------------")


    ##记录用
    movie_script: list[str] = []

    # 先说话
    for action in actions_collector:
        if (len(action.say) > 0):
            movie_script.append(f"{action.planer.name}说：{action.say[0]}")
            print(f"{action.planer.name}说（或者是心里活动）：{action.say[0]}")
    print("-------------------------------------------------------------")

    fight_actions = []
    for action in actions_collector:
        if action.action[0] == FIGHT:
            fight_actions.append(action)

    leave_actions = []
    for action in actions_collector:
        if action.action[0] == LEAVE:
            leave_actions.append(action)

    stay_actions = []
    for action in actions_collector:
        if action.action[0] == STAY:
            stay_actions.append(action)

    ###先收集出来
    stay_actors: list[Actor] = []
    for action in stay_actions:
        print(f"stay action: {action}")
        if (action.planer == current_stage):
            continue
        stay_actors.append(action.planer)
        #movie_script.append(f"{action.planer.name}在{current_stage.name}里")
    
    ###先收集出来
    leave_actors: list[Actor] = []
    for action in leave_actions:
        print(f"leave action: {action}")
        leave_actors.append(action.planer)
        #movie_script.append(f"{action.planer.name}想要离开，并去往{action.targets}")

    print("-------------------------------------------------------------")

    #
    if len(fight_actions) > 0:
        movie_script.append("发生了战斗！")
    #
    dead_actors: list[Actor] = []
    for action in fight_actions:
        print(f"fight action: {action}")
        #进入战斗的不能跑
        if action.planer in leave_actors:
            leave_actors.remove(action.planer)

        #print(f"fight action: {action}")
        movie_script.append(f"{action.planer.name}对{action.targets}发动了攻击")

        for target_name in action.targets:
            target = current_stage.get_actor(target_name)
            if target == None or target == action.planer:
                continue

            #被攻击不能走
            if target in leave_actors:
                leave_actors.remove(target) 
                #movie_script.append(f"{target.name}被攻击，不能离开")

            #最简单战斗计算
            print("这是一个测试的战斗计算，待补充")
            target.hp -= action.planer.damage    
            movie_script.append(f"{action.planer.name}对{action.targets}产生了{action.planer.damage}点伤害")
            if target.hp <= 0:
                dead_actors.append(target)
                print(f"{target.name}已经死亡")
                movie_script.append(f"{target.name}已经死亡")
            else:
                print(f"{target.name}剩余{target.hp/target.max_hp*100}%血量")

    ##被打死的不能走
    for actor in dead_actors:
        if actor in leave_actors:
            leave_actors.remove(actor)
            #movie_script.append(f"{actor.name}已经死亡，不能离开")
        if  actor in stay_actors:
            stay_actors.remove(actor)
            #movie_script.append(f"{actor.name}已经死亡，不能留下")

    ##处理离开的
    for actor in leave_actors:
        actor.stage.remove_actor(actor)
        actor.stage = None
        movie_script.append(f"{actor.name}离开了{current_stage.name}")
        raise NotImplementedError("Code to handle leaving actors is not implemented yet.")
    
    for actor in dead_actors:
        actor.stage.remove_actor(actor)
        actor.stage = None
        movie_script.append(f"{actor.name}死了，离开了这个世界")

    ##处理留下的
    for actor in stay_actors:
        pass
        #print(f"{actor.name}留在{current_stage.name}")
        #movie_script.append(f"{actor.name}留在{current_stage.name}")

    movie_script_str = '\n'.join(movie_script)
    if len(movie_script_str) == 0:
        movie_script_str = "无事发生"
        #return

    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    director_prompt_str = director_prompt(current_stage, movie_script_str)
    director_res = current_stage.call_agent(director_prompt_str)
    print(f"[{current_stage.name}]:", director_res)
    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")

    ##确认行动
    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
    for actor in current_stage.get_all_npcs():
        last_memory = f"""
        # 你知道发生了下面的事，并更新了你的记忆：
        {movie_script_str}
        """
        actor.chat_history.append(AIMessage(content=last_memory))
        actor_comfirm_prompt_str = actor_confirm_prompt(actor, director_res)
        actor_res = actor.call_agent(actor_comfirm_prompt_str)
        print(f"[{actor.name}]=>" + actor_res)
    print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")




if __name__ == "__main__":
    main()