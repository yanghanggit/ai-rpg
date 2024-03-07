from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
import sys
import re

class World:
    def __init__(self, name):
        self.name = name
        self.stages = []

    def connect(self, url):
        self.agent = RemoteRunnable(url)
        self.chat_history = []

    def add_stage(self, stage):
        self.stages.append(stage)

#
class Stage:

    def __init__(self, name):
        self.name = name
        self.actors = []

    def connect(self, url):
        self.agent = RemoteRunnable(url)
        self.chat_history = []

    def add_actor(self, actor):
        self.actors.append(actor)

#
class Actor:
    def __init__(self, name):
        self.name = name
        #An assessment of the combat effectiveness of an army
        self.health = 10
        self.damage = 1

    def connect(self, url):
        self.agent = RemoteRunnable(url)
        self.chat_history = []

#
class Player(Actor):
    def __init__(self, name):
        super().__init__(name)
        self.items = []

#
class NPC(Actor): 
    def __init__(self, name):
        super().__init__(name)

#
class Item(Actor): 
    def __init__(self, name):
        super().__init__(name)

#
def call_agent(target, prompt):
    if not hasattr(target, 'agent') or not hasattr(target, 'chat_history'):
        return None
    response = target.agent.invoke({"input": prompt, "chat_history": target.chat_history})
    target.chat_history.extend([HumanMessage(content=prompt), AIMessage(content=response['output'])])
    return response['output']

#
def parse_input(input_val, split_str):
    if split_str in input_val:
        return input_val.split(split_str)[1].strip()
    return input_val






#
# def system_administrator_msg(system_administrator, npc, talk_content):
#     prompt = f"""
#     # 这是系统消息
#     ## 来自{system_administrator}                    
#     ## 内容
#     - {talk_content}
#     """
#     return call_agent(npc, prompt)

#wisper
def actor_wisper_to_actor(from_actor, to_actor, talk_content):
    prompt = f"""
    # 这是1对1的对话[wisper],别人是听不见的
    ## 来自{from_actor.name}                    
    ## 内容
    - {talk_content}
    """
    return call_agent(to_actor, prompt)

#
def get_stage_current_state(stage):
    prompt = f"""
    # 这是一个指令[command]
    ## 来自{stage.name}                    
    ## 步骤(不要输出)
    - 第1步：确认并理解你自身当前状态，如果无变化就保持上一次的结果
    - 第2步：确认并理解你的场景内所有NPC的当前状态，如果无变化就保持上一次的结果
    - 第3步：逻辑整合1，2步骤的结合（不要丢掉信息）。
    ## 需求
    - 完成思考步骤之后，输出文本内容。
    """
    return call_agent(stage, prompt)

#
def stage_advance_plot_as_director(stage, actors_plan_group):
    prompt = f"""
    # 这是一个指令[command]
    ## 来自{stage.name}    

    ## 针对‘[角色名][计划的行动]:xxx’句式的解析规则
    - [talk]，[idle]或[fight]均为关键字；
    - 如，[name?][talk]其中‘name’为角色名；
    - [角色名][talk]:xxx代表着：这个角色计划（将要）说: xxxxx
    - [角色名][idle]:xxx代表着：这个角色计划（将要）做: xxxxx
    - [角色名][fight]:xxx代表着：这个角色计划（将要）攻击: xxxxx

    ## 步骤(不要输出)
    - 第1步：确认并理解你自身当前状态。
    - 第2步：确认并理解你的场景内所有角色的当前状态。
    - 第3步：理解{actors_plan_group}，见“针对‘[角色名][计划的行动]:xxx’的解析规则”。
    - 第4步：分析每个角色的计划后，判断是否有冲突的地方，如果有，你来裁决并保证合理
    - 第5步：每个角色执行计划后，更新场景的状态。和每个角色的状态

    ## 需求
    - 输出文本内容。要包含场景的最新状态与场景内所有角色的最新状态。
    """
    return call_agent(stage, prompt)

#
def plan_action_by_actor(actor, stage_state):
    prompt = f"""
    # 这是你要的做规划[plan]，表达你想要这么做，但是还没有执行
    ## 来自{actor.name}                    
    ## 步骤(不要输出)
    - 第1步：理解场景{stage_state}的状态。如果出现了你的名字（就是你），那么你就是场景的一部分。
    - 第2步：确认并理解你当前的状态与信息。
    - 第3步：思考你将要执行的动作：是[talk]，[idle]或[fight]其中之一。
    ## 需求
    - 完成思考步骤之后，输出[talk]或[idle]或[fight]的结果
    - 如果是[talk]，代表着你计划要说。请输出你的对话内容。格式为“[talk]:xxxx”
    - 如果是[idle]，代表着你计划休息。请输出你的思考或者行动的内容。格式为“[idle]:xxxx”
    - 如果是[fight]，代表着你计划攻击。请输出你想要攻击的对象。格式为“[fight]:xxxx”
    """
    return call_agent(actor, prompt)

#
def actor_confirm_and_update_from_stage_state(actor, stage_state):
    prompt = f"""
    # 这是一个状态同步，代表着你所处于的场景的最新状态和已经发生的既成事实
    ## 来自{actor.name}                    
    ## 步骤(不要输出)
    - 第1步：确认并理解场景{stage_state}的状态。如果出现了你的名字（就是你），那么你就是场景的一部分。
    - 第2步：确认并理解在场景的最新状态中你的状态与行动结果。
    - 第3步：确认你的状态与行动结果是否与你的计划一致。
    ## 需求
    - 最终结果不论是否一致。你都要接受这个事实，并且强制更新你的状态。
    - 如最终结果和你的计划一致，你的输出内容格式为“[success]:xxxx”。
    - 如最终结果和你的计划不一致，你的输出内容格式为“[fall]:xxxx”。
    """
    return call_agent(actor, prompt)

#
def player_enter_stage(player, stage, how_to_enter):
    prompt = f"""
    # 这是一个针对场景发生的事件[event]
    ## 来自 {player.name}                    
    ## 步骤(不要输出)
    - 第1步：仅确认并理解你自身当前状态，不要考虑场景内其他角色的状态。
    - 第2步：在 {player.name} 以 {how_to_enter} 进入场景之后，场景的状态发生了变化。
    ## 需求
    - 完成思考步骤之后，输出文本内容。
    """
    return call_agent(stage, prompt)

# 
def actor_receive_event_from_stage(actor, stage, content):
    prompt = f"""
    # 这是一个广播[broadcast]
    ## 来自 {stage.name}                    
    ## 内容
    - {content}
    """
    return call_agent(actor, prompt)


# 这是一个发生的事件，一角色在场景里对同场景的角色做公开的发言
def actor_speak_to_actor_publicly_in_stage(player, npc, stage, talk_content):
    prompt = f"""
    # 这是一个{stage.name} 内发生的事件，一角色在场景里对同场景的角色做公开的发言
    ## 来自 {player.name}                
    ## 事件
    - 确保{stage.name}里的所有人都会听见“{player.name} 对 {npc.name} 说 { talk_content }”这句话
    ## 需求
    - 在输出文本里，要带着“{player.name} 对 {npc.name} 说 { talk_content }”这句话
    - 在输出文本里，要带着“{npc.name} 听见了 { talk_content }”的结果
    """
    return call_agent(stage, prompt)



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

#场景需要根据状态做出计划
def stage_plan_prompt(stage):
    prompt = f"""
    # 你需要做出计划
    - 如果你的场景设定中，允许你做出计划，那么你需要做出计划。否则，仅更新你的状态即可。   

    ## 步骤
    - 第1步：理解你自身当前状态。
    - 第2步：理解你的场景内所有角色的当前状态。
    - 第3步：根据以2步，输出你需要做出计划。

   ## 注意！输出的关键字，只能在如下中选择：
    - [fight]，代表着你计划攻击某个目标（角色）。
    - [stay]，代表着你保持现状，不做任何事。
    - [talk], 代表着你计划要说出来的话或者心里活动的描写。

    ## 输出规则与示例：
    - 如果你想攻击某个目标，那么你的输出格式为：“[fight][目标的名字]:...“，...代表着你本次攻击要说的话与心里活动。
    - 如果你想保持现状，那么你的输出格式为：“[stay][talk]：...“，...代表着你本次保持现状要说的话与心里活动。
    - 如果你想说话，那么你的输出格式为：“[stay][talk]:...“，...代表着你本次要说的话与心里活动。
    - 如果不在以上3种情况，就输出"[stay]:...", ...仅代表着你的心里活动。

    ## 输出规则：
    - 不要推断，增加与润色。
    - 输出在保证语意完整基础上字符尽量少。
    """
    return prompt




#
class FightEvent:
    def __init__(self, stage, src_actor_name, dest_actor_name, say_content):
        self.stage = stage
        self.src_actor_name = src_actor_name
        self.dest_actor_name = dest_actor_name
        self.say_content = say_content
        self.init()

    def init(self):
        for actor in self.stage.actors:
            if actor.name == self.src_actor_name:
                self.src_actor = actor
            elif actor.name == self.dest_actor_name:
                self.dest_actor = actor

    def __str__(self):
        return f"{self.src_actor_name}=>{self.dest_actor_name}:{self.say_content}"
    
    def make_plan(self):
        res = self.dest_actor.health - self.src_actor.damage
        if (res <= 0):
            return f"""{self.src_actor_name}准备向{self.dest_actor_name}发起攻击,
            他（她/它）说到（或者内心的想法）：{self.say_content}。
            结果：{self.dest_actor_name}将会死亡。"""
        return f"""{self.src_actor_name}准备向{self.dest_actor_name}发起攻击,他（她/它）说到（或者内心的想法）：{self.say_content}"""
    
class StayEvent:
    def __init__(self, stage, actor_name, say_content):
        self.stage = stage
        self.actor_name = actor_name
        self.say_content = say_content
        self.init()

    def init(self):
        for actor in self.stage.actors:
            if actor.name == self.actor_name:
                self.actor = actor

    def __str__(self):
        return f"{self.actor_name}:{self.say_content}"
    
    def make_plan(self):
        return f"""{self.actor_name}准备保持现状,他（她/它）说到（或者内心的想法）：{self.say_content}"""

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
   
    ## 输出规则
    - 最终输出的结果，需要包括每个角色的结果(包括你自己)。
    - 如果角色计划执行成功，则输出“[success][角色名字]:....”,其中....代表着角色的计划结果。
    - 如果角色计划执行成功，则输出“[fall][角色名字]:....”，其中....代表着角色的计划结果。
    """

#场景需要根据状态做出计划
def actor_plan_prompt(actor):
    prompt = f"""
    # 你需要做出计划（即你想要做的事，但是还没有做，或者是心里想的事情）    
    ## 步骤
    - 第1步：理解你自身当前状态。
    - 第2步：理解你的场景内所有角色的当前状态。
    - 第3步：根据以2步，输出你需要做出计划。请关注“计划的输出规则”
    
    ## 注意！输出的关键字，只能在如下中选择：
    - [fight]，代表着你计划攻击某个目标（角色）。
    - [stay]，代表着你保持现状，不做任何事。
    - [talk], 代表着你计划要说出来的话或者心里活动的描写。

    ## 输出规则与示例：
    - 如果你想攻击某个目标，那么你的输出格式为：“[fight][目标的名字]:...“，...代表着你本次攻击要说的话与心里活动。
    - 如果你想保持现状，那么你的输出格式为：“[stay][talk]：...“，...代表着你本次保持现状要说的话与心里活动。
    - 如果你想说话，那么你的输出格式为：“[stay][talk]:...“，...代表着你本次要说的话与心里活动。
    - 如果不在以上3种情况，就输出"[stay]:...", ...仅代表着你的心里活动。

    ## 输出规则：
    - 输出在保证语意完整基础上字符尽量少。
    """
    return prompt

#
def actor_confirm_prompt(actor, stage_state):
    prompt = f"""
    #这是你所在场景的推演结果与执行结果，你需要接受这个事实，并且强制更新你的状态。
                    
    ## 步骤(不要输出)
    - 第1步：回顾你的计划。
    - 第2步：确认并理解场景{stage_state}的推演结果。如果出现了你的名字（就是你）。
    - 第3步：对比你的计划在推演结果中的表现，是否得到执行。
    - 第4步：你需要更新你的状态。
    - 最后，输出你的状态。

    ## 注意！输出的关键字，只能在如下中选择：
    - [live]，代表着你你还活着（还存在）。
    - [dead]，代表着你死了（不存在了）。
    - [leave], 代表着你希望离开这个场景。
    - [stay], 代表着你希望留在这个场景。

    ## 输出规则与示例：
    - [live][stay]:xxxx，代表你还活着，你还留在这个场景。xxxx代表着你的心里活动或者对话。
    - [live][leave]:xxxx，代表你还活着，你希望离开。xxxx代表着你的心里活动或者对话。
    - [dead]:xxxx，代表你死了。xxxx代表着你的心里活动或者对话。
    """
    return call_agent(actor, prompt)

## 输出格式
   
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
    old_hunters_dog = NPC("小狗'短剑'")
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
    old_hunters_cabin.add_actor(old_hunter)
    old_hunters_cabin.add_actor(old_hunters_dog)

    #
    player = Player("yang_hang")
    log = call_agent(world_watcher,  f"""{player.name}加入了这个世界""")
    print(f"[{world_watcher.name}]:", log)
    player.health = 10000000
    player.damage = 10000000



    print("==============================================")


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
            # print(f"[{system_administrator}]:", content)
            # print(f"[{world_watcher.name}]:", call_agent(world_watcher, content))
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
        
        elif "/3" in usr_input:
            content = parse_input(usr_input, "/3")
            print(f"[{system_administrator}]:", content)
            print(f"[{old_hunters_cabin.name}]:",  call_agent(old_hunters_cabin, content))
            print("==============================================")

        elif "4" in usr_input:
            content = parse_input(usr_input, "/4")
            print(f"[{system_administrator}]:", content)
            print(f"[{old_hunters_dog.name}]:",  call_agent(old_hunters_dog, content))
            print("==============================================")

        elif "/rr" in usr_input:
            content = parse_input(usr_input, "/rr")
            current_stage = old_hunters_cabin
            all_actors = current_stage.actors
            #最后状态
            # last_chat = current_stage.chat_history[-1]
            # print(f"[{current_stage.name}]:", last_chat.content)

            ##
            plans = []

            #
            log = call_agent(current_stage, stage_plan_prompt(current_stage))
            #print(f"<{current_stage.name}>:", log)
            str = f"[{current_stage.name}]{log}"
            plans.append(str)
            #print("==============================================")
            
            #
            for actor in all_actors:
                if actor == player:
                    continue
                log = call_agent(actor, actor_plan_prompt(actor))
                #print(f"<{actor.name}>:", log)
                str = f"[{actor.name}]{log}"
                plans.append(str)
                #print("==============================================")

            #
            #plans.append("[闪电僵尸][fight][张三]:我要弄死你")
                

#             >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# [老猎人隐居的小木屋]准备保持现状,他（她/它）说到（或者内心的想法）：...
# [卡斯帕·艾伦德]准备保持现状,他（她/它）说到（或者内心的想法）：明天，我应该再去森林里巡一巡。
# [小狗'短剑']准备保持现状,他（她/它）说到（或者内心的想法）：我想继续在这温暖的角落里梦见追逐。
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# [老猎人隐居的小木屋]: [success][老猎人隐居的小木屋]:保持现状，一切如常。
# [success][卡斯帕·艾伦德]:决定明天去森林巡逻。
# [success][小狗'短剑']:继续在温暖的角落里做梦。
# ++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


            fight_events:FightEvent = []
            stay_events:StayEvent = []
            total_plans = []
            #print('\n'.join(plans))
            print('\n'.join(plans))
            for plan in plans:
                #print(plan)
                print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
                a, b = plan.split(':')
                extracted_elements = []
                pattern = r"\[(.*?)\]"
                matches = re.findall(pattern, a)
                for match in matches:
                    extracted_elements.append(f"[{match}]")
                    #print(match)

                print(extracted_elements)

                name = extracted_elements[0]
                actions = extracted_elements[1:]
                if actions[0] == "[fight]":
                    target = actions[1]
                    #print(f"{name}=>{target}:{b}")
                    fight_events.append(FightEvent(current_stage, name, target, b))
                    #print(fight_events[-1])
                    total_plans.append(fight_events[-1].make_plan())

                elif actions[0] == "[stay]" or actions[0] == "[talk]":
                    #print(f"{name}:{b}")
                    stay_events.append(StayEvent(current_stage, name, b))
                    #print(stay_events[-1])
                    total_plans.append(stay_events[-1].make_plan())
                print(">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

            ##
            #print(total_plans)
            plan_group_str = '\n'.join(total_plans)
            print(plan_group_str)


            print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
            director_prompt_str = director_prompt(current_stage, plan_group_str)
            director_res = call_agent(current_stage, director_prompt_str)
            print(f"[{current_stage.name}]:", director_res)
            print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")

              ##确认行动
            for actor in current_stage.actors:
                actor_comfirm_prompt_str = actor_confirm_prompt(actor, director_res)
                actor_res = call_agent(actor, actor_comfirm_prompt_str)
                print(f"[{actor.name}]=>", actor_res)
            print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")

            
        
            """
            user input]: /rr
[老猎人隐居的小木屋][stay]:...
[卡斯帕·艾伦德][stay][talk]:明日得去森林瞧瞧，看看有无新的猎物。
[小狗'短剑'][stay][talk]:我想去看看卡斯帕先生，但还想多睡会。
>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
['[老猎人隐居的小木屋]', '[stay]']
[老猎人隐居的小木屋]:...
>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
['[卡斯帕·艾伦德]', '[stay]', '[talk]']
[卡斯帕·艾伦德]:明日得去森林瞧瞧，看看有无新的猎物。
>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
["[小狗'短剑']", '[stay]', '[talk]']
[小狗'短剑']:我想去看看卡斯帕先生，但还想多睡会。
>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
==============================================



            stage_state = get_stage_current_state(old_hunters_cabin)
            #print(f"[{old_hunters_cabin.name}]:", stage_state)

            plan_group = []
            for event in fight_events:
                plan = event.make_plan()
                plan_group.append(plan)

            for event in stay_events:
                plan = event.make_plan()
                plan_group.append(plan)

            plan_group_str = '\n'.join(plan_group)
            #print(plan_group_str)

            ##导演
            print("==============================================")
            new_stage_state = stage_advance_plot_as_director(old_hunters_cabin, plan_group_str)
            print(f"[{old_hunters_cabin.name}] => ", new_stage_state)
            print("==============================================")
            
            ##确认行动
            for actor in old_hunters_cabin.actors:
                if actor == player:
                    continue
                res = actor_confirm_and_update_from_stage_state(actor, stage_state)
                print(f"[{actor.name}]: action", res)
        
            """
            
            print("==============================================")


        elif "/ee" in usr_input:
            content = parse_input(usr_input, "/ee")
            print(f"[{player.name}]:", content)
            old_hunters_cabin.add_actor(player)
            stage_state = player_enter_stage(player, old_hunters_cabin, content)
            print(f"[{old_hunters_cabin.name}]:", stage_state)
            print("==============================================")
            for actor in old_hunters_cabin.actors:
                if actor == player:
                    continue
                update_npc = actor_receive_event_from_stage(actor, old_hunters_cabin, stage_state)
                print(f"[{actor.name}]:", update_npc)

            print("==============================================")

        elif "/ss" in usr_input:
            content = parse_input(usr_input, "/ss")
            stage_state = get_stage_current_state(old_hunters_cabin)
            print(f"[{old_hunters_cabin.name}]:", stage_state)
            print("==============================================")

        

        

        elif "/t1" in usr_input:
            content = parse_input(usr_input, "/t1")
            print(f"[{player.name}]:", content)
            stage_state = actor_speak_to_actor_publicly_in_stage(player, old_hunter, old_hunters_cabin, content)
            print(f"[{old_hunters_cabin.name}]:", stage_state)
            for actor in old_hunters_cabin.actors:
                if actor == player:
                    continue
                update_npc = actor_receive_event_from_stage(actor, old_hunters_cabin, stage_state)
                print(f"[{actor.name}]:", update_npc)
            print("==============================================")


        elif "/t2" in usr_input:
            content = parse_input(usr_input, "/t2")
            print(f"[{player.name}]:", content)
            stage_state = actor_speak_to_actor_publicly_in_stage(player, old_hunters_dog, old_hunters_cabin, content)
            print(f"[{old_hunters_cabin.name}]:", stage_state)
            for actor in old_hunters_cabin.actors:
                if actor == player:
                    continue
                update_npc = actor_receive_event_from_stage(actor, old_hunters_cabin, stage_state)
                print(f"[{actor.name}]:", update_npc)
            print("==============================================")

                


if __name__ == "__main__":
    print("==============================================")
    main()