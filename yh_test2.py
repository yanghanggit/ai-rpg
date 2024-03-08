from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
import sys
import json
import re


# from yh_test2 import Stage
# from yh_test2 import World



"""
action: ["a1", "a2", "a3"],
targets: ["猎人", "小狗"],
say: ["hello", "world"],
tags: ["t1", "t2", "t3"]
"""

json_str = '''
{
    "action": ["", "", ""],
    "targets": ["", ""],
    "say": ["", ""],
    "tags": ["", "", ""]
}
'''
          
FIGHT: str = '/fight'
STAY: str = '/stay'
LEAVE: str = '/leave'
ALL_ACTIONS: list[str] = [FIGHT, STAY, LEAVE]

#
def check_data_format(action: any, targets: any, say: any, tags: any) -> bool:
    if not isinstance(action, list) or not all(isinstance(a, str) for a in action):
        return False
    if not isinstance(targets, list) or not all(isinstance(t, str) for t in targets):
        return False
    if not isinstance(say, list) or not all(isinstance(s, str) for s in say):
        return False
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        return False

#
class Actor:
    def __init__(self, name: str):
        self.name = name     

    def connect(self, url: str)-> None:
        self.agent = RemoteRunnable(url)
        self.chat_history = []

#
def call_agent(target: Actor, prompt: str) -> str:
    # if not hasattr(target, 'agent') or not hasattr(target, 'chat_history'):
    #     return None
    response = target.agent.invoke({"input": prompt, "chat_history": target.chat_history})
    target.chat_history.extend([HumanMessage(content=prompt), AIMessage(content=response['output'])])
    return response['output']

class Action:
    def __init__(self, action: list[str], targets: list[str], say: list[str], tags: list[str]):
        self.action = action
        self.targets = targets
        self.say = say
        self.tags = tags

    def __str__(self):
        return f"action: {self.action}, targets: {self.targets}, say: {self.say}, tags: {self.tags}"

class World(Actor):
    def __init__(self, name: str):
        self.name = name
        self.stages = []

    def add_stage(self, stage) -> None:
        self.stages.append(stage)

#
class Stage(Actor):
    def __init__(self, name:str):
        self.name = name
        self.actors = []
        self.world = None

    def add_actor(self, actor: Actor)-> None:
        self.actors.append(actor)

#
class Player(Actor):
    def __init__(self, name: str):
        super().__init__(name)
        self.stage = None

#
class NPC(Actor): 
    def __init__(self, name: str):
        super().__init__(name)
        self.stage = None

#
def parse_input(input_val: str, split_str: str)-> str:
    if split_str in input_val:
        return input_val.split(split_str)[1].strip()
    return input_val


######################################################################
##################################################################################################################################################################################################################
##################################################################################################################################################################################################################
##################################################################################################################################################################################################################
#
init_archivist = f"""
# 游戏世界存档
- 大陆纪元2000年1月1日，冬夜.
- “卡斯帕·艾伦德”坐在他的“老猎人隐居的小木屋”中的壁炉旁，在沉思和回忆过往，并向壁炉中的火投入了一根木柴。
- 他的小狗（名叫"断剑"）在屋子里的一角睡觉。
"""
load_prompt = f"""
# 你需要读取存档
## 步骤:
- 第1步，读取{init_archivist}.
- 第2步：理解这些信息(尤其是和你有关的信息).
- 第3步：根据信息更新你的最新状态与逻辑.
- 第4部：如果是你角色输则出你在做什么，如果你是场景则输出场景中正在发生的一切.
## 输出规则：
- 保留关键信息(时间，地点，人物，事件)，不要推断，增加与润色。输出在保证语意完整基础上字符尽量少。
"""
######################################################################
##################################################################################################################################################################################################################
##################################################################################################################################################################################################################
##################################################################################################################################################################################################################


#场景需要根据状态做出计划
def actor_plan_prompt(actor):
    return f"""
    # 你需要做出计划（即你想要做的事还没做）    
    ## 步骤
    - 第1步：理解你自身当前状态。
    - 第2步：理解你的场景内所有角色的当前状态。
    - 第3步：输出你需要做出计划。
    ## 输出规则：
    - 如果你想攻击某个目标，就必须输出目标的名字。
    - 如果你想离开本场景，就必须输出你所知道的地点的名字。
    - 输出在保证语意完整基础上字符尽量少。
    """
##
def director_prompt(stage, plans_group):
    return f"""
    # 你需要根据所有角色（可能包括你自己）的计划，做出最终的决定，推演与执行。
    ## 所有角色的计划如下
    - {plans_group}
    ## 步骤（不需要输出）
    - 第1步：理解所有角色的计划，不要漏掉任何相关角色。
    - 第2步：做出推演与判断（决定每个角色的计划能否能成功）。
    - 第3步：执行所有计划。
    - 第4步：根据执行结果更新场景的状态以及所有角色的状态。
    - 第5步：输出。
    ## 输出规则
    - 最终输出的结果，需要包括每个角色的结果(包括你自己)。
    """
#
def actor_confirm_prompt(actor, stage_state):
    return f"""
    #这是你所在场景的推演结果与执行结果，你需要接受这个事实，并且强制更新你的状态。
    ## 步骤(不要输出)
    - 第1步：回顾你的计划。
    - 第2步：确认并理解场景{stage_state}的推演结果（可能会提到你）。
    - 第3步：对比你的计划在推演结果中的表现，是否得到执行。
    - 第4步：你需要更新你的状态。
    - 第5步：输出你的状态
    """
#
def main():
    #
    system_administrator = "系统管理员"

    #load!!!!
    world_watcher = World("世界观察者")
    world_watcher.connect("http://localhost:8004/world/")
    log = call_agent(world_watcher,  load_prompt)
    print(f"[{world_watcher.name}]:", log)
    print("==============================================")

    #
    old_hunter = NPC("卡斯帕·艾伦德")
    old_hunter.connect("http://localhost:8021/actor/npc/old_hunter/")
    log = call_agent(old_hunter, load_prompt)
    print(f"[{old_hunter.name}]:", log)
    print("==============================================")

    #
    old_hunters_dog = NPC("小狗'断剑'")
    old_hunters_dog.connect("http://localhost:8023/actor/npc/old_hunters_dog/")
    log = call_agent(old_hunters_dog, load_prompt)
    print(f"[{old_hunters_dog.name}]:", log)
    print("==============================================")

    #
    old_hunters_cabin = Stage("老猎人隐居的小木屋")
    old_hunters_cabin.connect("http://localhost:8022/stage/old_hunters_cabin/")
    log = call_agent(old_hunters_cabin, load_prompt)
    print(f"[{old_hunters_cabin.name}]:", log)
    print("==============================================")

    #
    world_watcher.add_stage(old_hunters_cabin)
    old_hunters_cabin.world = world_watcher
    #
    old_hunters_cabin.add_actor(old_hunter)
    old_hunter.stage = old_hunters_cabin

    old_hunters_cabin.add_actor(old_hunters_dog)
    old_hunters_dog.stage = old_hunters_cabin

    #
    player = Player("yang_hang")
    #player.connect("http://localhost:8023/12345/")
    log = call_agent(world_watcher,  f"""你知道了如下事件：{player.name}加入了这个世界""")
    print(f"[{world_watcher.name}]:", log)
    # player.health = 10000000
    # player.power = 10000000

    print("//////////////////////////////////////////////////////////////////////////////////////")
    print("//////////////////////////////////////////////////////////////////////////////////////")
    print("//////////////////////////////////////////////////////////////////////////////////////")

    #
    while True:
        usr_input = input("[user input]: ")
        if "/quit" in usr_input:
            sys.exit()
        if "/cancel" in usr_input:
            continue
        
        elif "/0" in usr_input:
            content = parse_input(usr_input, "/0")
            print(f"[{system_administrator}]:", content)

            ## 必须加上！！！！！！！
            old_hunters_cabin.add_actor(player)
            player.stage = old_hunters_cabin
            ###
            event_prompt = f"""{player.name}, {content}"""
            print(f"[{player.name}]=>", event_prompt)

            old_hunters_cabin.chat_history.append(HumanMessage(content=event_prompt))
            print(f"[{old_hunters_cabin.name}]:", call_agent(old_hunters_cabin, "更新你的状态"))

            for actor in old_hunters_cabin.actors:
                if (actor == player):
                    continue
                actor.chat_history.append(HumanMessage(content=event_prompt))
                print(f"[{actor.name}]:", call_agent(actor, "更新你的状态"))
            print("==============================================")


        elif "/1" in usr_input:
            content = parse_input(usr_input, "/1")
            print(f"[{system_administrator}]:", content)
            print(f"[{world_watcher.name}]:", call_agent(world_watcher, content))
            print("==============================================")

        elif "/2" in usr_input:
            content = parse_input(usr_input, "/2")
            print(f"[{system_administrator}]:", content)
            print(f"[{old_hunter.name}]:",  call_agent(old_hunter, content))
            print("==============================================")

        elif "3" in usr_input:
            content = parse_input(usr_input, "/3")
            print(f"[{system_administrator}]:", content)
            print(f"[{old_hunters_dog.name}]:",  call_agent(old_hunters_dog, content))
            print("==============================================")
        
        elif "/4" in usr_input:
            # 所有人都知道了这件事
            content = parse_input(usr_input, "/4")
            print(f"[{system_administrator}]:", content)

            old_hunters_cabin.chat_history.append(HumanMessage(content=content))
            print(f"[{old_hunters_cabin.name}]:", call_agent(old_hunters_cabin, "更新你的状态"))

            for actor in old_hunters_cabin.actors:
                actor.chat_history.append(HumanMessage(content=content))
                print(f"[{actor.name}]:", call_agent(actor, "更新你的状态"))
            print("==============================================")

        
        elif "/rr" in usr_input:
            flag = "/rr"
            input_content = parse_input(usr_input, flag)
        
            #current_stage = old_hunters_cabin
            this_stage_plan = stage_plan(old_hunters_cabin)

            print("111")
            




            #all_actors = current_stage.actors








            # #最后状态
            # #last_chat = current_stage.chat_history[-1]
            # #print(f"[{current_stage.name}]%", last_chat.content)
            # ##
            # plans_collector = []
            # #
            # log = call_agent(current_stage, stage_plan_prompt(current_stage))
            # print(f"<{current_stage.name}>:", log)
            # str = f"[{current_stage.name}]的计划是: {log}"
            # plans_collector.append(str)
            # #print("==============================================")
            
            # #
            # for actor in all_actors:
            #     if (actor == player):
            #         print(f"{player.name}不需要做出计划,因为你是玩家角色。")
            #         continue
            #     log = call_agent(actor, actor_plan_prompt(actor))
            #     #print(f"<{actor.name}>:", log)
            #     str = f"[{actor.name}]的计划是: {log}"
            #     plans_collector.append(str)
            #     #print("==============================================")
            # print("==============================================")

            # ##
            # #print(total_plans)
            # plan_group_str = '\n'.join(plans_collector)
            # print(plan_group_str)
            # ## 

            # ## 战斗分析
            # fight_analysis = f"""\n
            # ## 你的决策中，如果出现了战斗的事件，你需要分析。规则如下。
            # - {player.name} 无比强大是绝对无可战胜的存在，任何攻击他的人都会死亡
            # - {old_hunter.name} 普通勇者的战斗力
            # - {old_hunters_dog.name} 没有任何战斗力
            # """
            # plan_group_str += fight_analysis

            # print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
            # director_prompt_str = director_prompt(current_stage, plan_group_str)
            # director_res = call_agent(current_stage, director_prompt_str)
            # print(f"[{current_stage.name}]:", director_res)
            # print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
            # ##确认行动
            # for actor in current_stage.actors:
            #     if (actor == player):
            #         print(f"{player.name}接受行动？因为没有agent?")
            #         continue
            #     actor_comfirm_prompt_str = actor_confirm_prompt(actor, director_res)
            #     actor_res = call_agent(actor, actor_comfirm_prompt_str)
            #     print(f"[{actor.name}]=>" + actor_res)
            # print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")



######################################################################
#
def check_actions_is_valid(actions: list[str]) -> bool:
    for action in actions:
        if action not in ALL_ACTIONS:
            return False
    return True

#
def check_targets_is_valid_actor_in_stage(stage: Stage, targets: list[str]) -> bool:
    for target in targets:
        if not any(actor.name == target for actor in stage.actors):
            return False
    return True

#
def check_stage_is_valid_in_world(world: World, stage_name: str) -> bool:
    if not any(stage.name == stage_name for stage in world.stages):
        return False
    return True

#场景需要根据状态做出计划
def stage_plan_prompt(stage: Stage)-> str:

    ###
    sample_json = {
    "action": ["", "", ""],
    "targets": ["", "", ""],
    "say": ["", "", ""],
    "tags": ["", "", ""]
    }
    sample_json_str = json.dumps(sample_json)

    return f"""
    # 你需要做出计划
    ## 步骤
    - 第1步：理解你的当前状态。
    - 第2步：理解场景内所有角色的当前状态。
    - 第3步：输出你的计划。如果没有更新你的状态。   

    ## 输出规则（最终输出为JSON）：
    - 你的输出必须是一个JSON，包括action, targets, say, tags四个字段。
    - action: 默认是[""]，只能是["/fight", "/stay", "/leave"]中的一个（即都是字符串），不允许多个。
    - targets: 默认是[""]，可以是多个，必须是场景内的角色名字或者是你的名字，即都是字符串
    - say: 默认是[""]，可以是多个，但是必须是字符串；
    - tags: 默认是[""]，可以是多个，但是必须是字符串；
    ### 输出格式请参考: {sample_json_str}
   
    ### action与targets说明
    - "/fight"：代表你想对某个角色发动攻击或者敌意行为，targets是场景内某个角色的名字
    - "/leave"：代表你想离开本场景，targets是你知道的这个在这个世界某个地点的名字
    - 关于"/stay"：除了"/fight"，"/leave"，之外的其他行为都是"/stay"，代表你想保持现状, targets你在这个场景的名字（如果你自己就是场景，那就是你的名字）

    ### say与tags说明
    - say: 你的输出的话(或者心里活动)，可以是多个，但是必须是字符串。如果没什么想说的就说“无事想做”
    - tags: 输出的标签（你的特点），可以是多个，但是必须是字符串
    
    ## 输出限制：
    - 按着如上规则，输出JSON
    - 不要推断，增加与润色。
    - 输出在保证语意完整基础上字符尽量少。
    """
      
def stage_plan(stage: Stage) -> Action:

    make_prompt = stage_plan_prompt(stage)
    print(f"stage_plan_prompt:", make_prompt)

    call_res = call_agent(stage, make_prompt)
    print(f"<{stage.name}>:", call_res)

    error_action = Action([STAY], [stage.name], [""], [""])

    try:
        json_data = json.loads(call_res)
        if not check_data_format(json_data['action'], json_data['targets'], json_data['say'], json_data['tags']):
            return error_action

        #
        action = Action(json_data['action'], json_data['targets'], json_data['say'], json_data['tags'])
        if not (check_actions_is_valid(action.action) 
                or check_targets_is_valid_actor_in_stage(stage, action.targets) 
                or check_stage_is_valid_in_world(stage.world, stage.name)):
            return error_action
        
    except Exception as e:
        print(f"stage_plan error = {e}")
        return error_action

    return error_action















            




        



if __name__ == "__main__":
    print("==============================================")
    main()