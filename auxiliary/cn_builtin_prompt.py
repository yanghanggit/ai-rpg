from entitas import Entity # type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import NPCComponent, StageComponent
from typing import Dict, List
from auxiliary.base_data import PropData


###############################################################################################################################################
def init_memory_system_prompt(init_memory: str, entity: Entity, context: ExtendedContext) -> str:
    prompt = f"""# 世界即将开始运行。你需要做初始状态的设定。
## 你初始的设定状态如下: 
{init_memory}。
## 你需要将自己完全带入你的角色设定并开始游戏。
## 请遵循输出格式指南,仅通过返回MindVoiceActionComponent及相关内容来确认你的状态。"""
    return prompt
###############################################################################################################################################
def npc_plan_prompt(current_stage: str, stage_enviro_narrate: str, context: ExtendedContext) -> str:
    
    current_stage_prompt = "未知"
    if current_stage != "":
        current_stage_prompt = current_stage

#     current_stage_enviro_narrate_prompt = "无"
#     if stage_enviro_narrate != "":
#         current_stage_enviro_narrate_prompt = stage_enviro_narrate
#         ## 场景的环境描述如下(可以用于做参考信息):
# - {current_stage_enviro_narrate_prompt}

    prompt = f"""# 根据计划制定指南作出你的计划。
## 你当前所在的场景:{current_stage_prompt}。
## 要求:输出结果格式要遵循输出格式指南。结果中需要附带TagActionComponent。"""
    return prompt
###############################################################################################################################################
def first_time_npc_plan_prompt(current_stage: str, stage_enviro_narrate: str, context: ExtendedContext) -> str:

    current_stage_prompt = "未知"
    if current_stage != "":
        current_stage_prompt = current_stage

#     current_stage_enviro_narrate_prompt = "和上次相比没有变化"
#     if stage_enviro_narrate != "":
#         current_stage_enviro_narrate_prompt = stage_enviro_narrate
#         ## 场景的环境描述如下(可以用于做参考信息):
# - {current_stage_enviro_narrate_prompt}

    prompt = f"""# 根据计划制定指南作出你的计划。
## 你当前所在的场景:{current_stage_prompt}。
## 要求:
- 输出结果格式要遵循输出格式指南。
- 本次是你第一次制定计划,所以需要有PerceptionActionComponent与CheckStatusActionComponent,用于感知场景内的道具与确认自身状态。
- 结果还需要需要附带TagActionComponent。"""
    return prompt
###############################################################################################################################################
def stage_plan_prompt(props_in_stage: List[PropData], context: ExtendedContext) -> str:

    ## 场景内道具
    prompt_of_props = ""
    if len(props_in_stage) > 0:
        for prop in props_in_stage:
            prompt_of_props += prop_info_prompt(prop)
    else:
        prompt_of_props = "- 无任何道具。"

    prompt = f"""请根据‘计划制定指南’作出你的计划。
## 场景内道具:
{prompt_of_props}
## 要求：
- 输出结果格式要遵循‘输出格式指南’。
- 结果中需要有EnviroNarrateActionComponent,并附带TagActionComponent。"""
    return prompt
###############################################################################################################################################
def perception_action_prompt(who_perception: str, current_stage: str, ressult_npc_names: Dict[str, str], result_props_names: List[str]) -> str:

    prompt_of_npc = ""
    if len(ressult_npc_names) > 0:
        for other_name, other_appearance in ressult_npc_names.items():
            prompt_of_npc += f"""### {other_name}\n- 外貌信息:{other_appearance}\n"""
    else:
        prompt_of_npc = "- 目前场景内没有其他角色。"

    prompt_of_props = ""
    if len(result_props_names) > 0:
        for propname in result_props_names:
            prompt_of_props += f"- {propname}\n"
    else:
        prompt_of_props = "- 无任何道具。"

    final_prompt = f"""# {who_perception}当前在场景{current_stage}中。{who_perception}对{current_stage}执行PerceptionActionComponent,即使发起感知行为,结果如下:
## 场景内人物:
{prompt_of_npc}
## 场景内道具:
{prompt_of_props}
"""
    return final_prompt
###############################################################################################################################################
def prop_type_prompt(prop: PropData) -> str:
    _type = "未知"
    if prop.is_weapon():
        _type = "武器(提高攻击力)"
    elif prop.is_clothes():
        _type = "衣服(提高防御力)"
    elif prop.is_non_consumable_item():
        _type = "非消耗品"
    elif prop.is_role_component():
        _type = "特殊记忆与能力"
    return _type
###############################################################################################################################################
def prop_info_prompt(prop: PropData) -> str:
    proptype = prop_type_prompt(prop)
    prompt = f"""### {prop.name}
- 类型:{proptype}
- 描述:{prop.description}
"""
    return prompt
###############################################################################################################################################
def role_component_info_prompt(prop: PropData) -> str:
    prompt = f"""### {prop.name}
- {prop.description}
"""
    return prompt
###############################################################################################################################################
def check_status_action_prompt(who: str, props: List[PropData], health: float, role_components: List[PropData], events: List[PropData]) -> str:
    #百分比的
    health *= 100
    prompt_of_npc = f"生命值: {health:.2f}%"

    prompt_of_props = ""
    if len(props) > 0:
        for prop in props:
            prompt_of_props += prop_info_prompt(prop)
    else:
        prompt_of_props = "- 无任何道具。"

    prompt_of_role_components = ""
    if len(role_components) > 0:
        for role in role_components:
            prompt_of_role_components += role_component_info_prompt(role)
    else:
        prompt_of_role_components = "- 无任何特殊记忆与能力。"

    final_prompt = f"""# {who}对自身执行CheckStatusActionComponent,即对自身状态进行检查,结果如下:
## 健康状态:
{prompt_of_npc}
## 持有道具:
{prompt_of_props}
## 特殊记忆与能力:
{prompt_of_role_components}
"""
    return final_prompt
###############################################################################################################################################
def search_action_failed_prompt(npcname: str, prop_name:str) -> str:
    return f"""# {npcname}试图在场景内搜索"{prop_name}",但失败了。
## 原因可能如下:
1. "{prop_name}"可能并非是一个道具。'SearchActionComponent'只能支持搜索道具的行为与计划
2. 或者这个道具此时已不在本场景中（可能被其他角色搜索并获取了）。
## 建议与提示:
- {npcname}需重新考虑搜索目标。
- 可使用PerceptionActionComponent来感知场景内的道具,并确认合理目标。"""
###############################################################################################################################################
def search_action_success_prompt(npcname: str, prop_name:str, stagename: str) -> str:
    return f"""# {npcname}从{stagename}场景内成功找到并获取了道具:{prop_name}。
## 导致结果:
- {stagename}不再持有这个道具。"""
###############################################################################################################################################
def prison_break_action_begin_prompt(npcname: str, stagesname: str, context: ExtendedContext) -> str:
    return f"""# {npcname}意图离开{stagesname}
## 附加说明:
- {npcname}无法确认是否能够成功离开{stagesname}。可能会因为某些原因而失败。
- {npcname}无法确认将要前往的目的地。"""
################################################################################################################################################
def leave_for_target_stage_failed_because_no_exit_condition_match_prompt(npcname: str, stagename: str, tips: str, is_prison_break: bool) -> str:
    if is_prison_break:
        if tips == "":
            return f"""# {npcname}不能离开本场景。原因:当前不满足离开的条件。
## 建议:
- 可以通过CheckStatusActionComponent查看自己拥有的道具。
- 或者通过PerceptionActionComponent感知场景内的道具，找到离开的条件。"""
        
        return f"""# {npcname}不能离开本场景。
## 提示:
- {tips}"""
    
    else:
        if tips == "":
            return f"""# {npcname}不能离开本场景并去往{stagename}。原因：可能当前不满足离开的条件。
## 建议:
- 可以通过CheckStatusActionComponent查看自己拥有的道具，
- 或者通过PerceptionActionComponent感知场景内的道具，找到离开的条件。"""
        
        return f"""{npcname}不能离开本场景并去往{stagename}。
## 提示:
- {tips}"""
################################################################################################################################################
def someone_entered_my_stage_observed_his_appearance_prompt(someone: str, his_appearance: str) -> str:
    return f"""# 你所在场景发生如下事件：{someone}进入了场景。
## {someone}的外貌信息如下：
- {his_appearance}"""
################################################################################################################################################
def observe_appearance_after_entering_stage_prompt(myname: str, stagename: str, npc_appearance_in_stage: Dict[str, str]) -> str:
    prompt_of_npc = ""
    assert len(npc_appearance_in_stage) > 0
    if len(npc_appearance_in_stage) > 0:
        for other_name, other_appearance in npc_appearance_in_stage.items():
            prompt_of_npc += f"""### {other_name}\n- 外貌信息:{other_appearance}\n"""
    else:
        prompt_of_npc = "- 无任何外貌信息。"
    return f"""# {myname}进入{stagename}之后观察场景内的角色。
## 外貌信息如下:
{prompt_of_npc}"""
################################################################################################################################################
def enter_stage_prompt1(some_ones_name: str, target_stage_name: str) -> str:
    return f"{some_ones_name}进入了场景——{target_stage_name}。"
################################################################################################################################################
def enter_stage_prompt2(some_ones_name: str, target_stage_name: str, last_stage_name: str) -> str:
    return f"{some_ones_name}离开了{last_stage_name}, 进入了{target_stage_name}。"
################################################################################################################################################
def leave_stage_prompt(npc_name: str, current_stage_name: str, leave_for_stage_name: str) -> str:
    return f"{npc_name}离开了{current_stage_name} 场景。"
################################################################################################################################################







def whisper_action_prompt(srcname: str, destname: str, content: str, context: ExtendedContext) -> str:
    prompt = f"{srcname}对{destname}低语道:{content}"   
    return prompt

def broadcast_action_prompt(srcname: str, destname: str, content: str, context: ExtendedContext) -> str:
    prompt = f"{srcname}对{destname}里的所有人说:{content}"   
    return prompt

def speak_action_prompt(srcname: str, destname: str, content: str, context: ExtendedContext) -> str:
    prompt = f"{srcname}对{destname}说:{content}"   
    return prompt

def gen_npc_archive_prompt(context: ExtendedContext) -> str:
    prompt = """
请根据上下文，对自己知道的事情进行梳理总结成markdown格式后输出,但不要生成```markdown xxx```的形式:
# 游戏世界存档
## 地点
### xxx
#### 和我有关的事
- xxxx
- xxxx
- xxxx
- xxxx
### xxx
#### 和我有关的事
- xxxx
- xxxx
- xxxx
- xxxx
"""
    return prompt

def gen_stage_archive_prompt(context: ExtendedContext) -> str:
     prompt = """
请根据上下文，对自己知道的事情进行梳理总结成markdown格式后输出,但不要生成```markdown xxx```的形式:
# 游戏世界存档
## 地点
- xxxxx
## 发生的事情
- xxxx
- xxxx
- xxxx
"""
     return prompt
    

def gen_world_archive_prompt(context: ExtendedContext) -> str:
     prompt = """
请根据上下文，对自己知道的事情进行梳理总结成markdown格式后输出,但不要生成```markdown xxx```的形式:
# 游戏世界存档
## 地点
### xxx
#### 发生的事件
- xxxx
- xxxx
- xxxx
### xxx
#### 发生的事件
- xxxx
- xxxx
- xxxx
"""
     return prompt

def died_in_fight_prompt(context: ExtendedContext) -> str:
    return f"你已经死亡（在战斗中受到了致命的攻击）"






def kill_someone(attacker_name: str, target_name: str) -> str:
    return f"{attacker_name}对{target_name}发动了一次攻击,造成了{target_name}死亡。"

def attack_someone_prompt(attacker_name: str, target_name: str, damage: int, target_current_hp: int ,target_max_hp: int) -> str:
    health_percent = (target_current_hp - damage) / target_max_hp * 100
    return f"{attacker_name}对{target_name}发动了一次攻击,造成了{damage}点伤害,当前{target_name}的生命值剩余{health_percent}%。"

# def speak_action_system_invalid_target(target_name: str, speakcontent: str) -> str:
#     return f"[{target_name}]在你所在场景内无法找到，所以你不能对其说如下的内容：{speakcontent}"



def steal_action_prompt(whosteal: str, targetname: str, propname: str, stealres: bool) -> str:
    if not stealres:
        return f"{whosteal}从{targetname}盗取{propname}, 失败了"
    return f"{whosteal}从{targetname}成功盗取了{propname}"

def trade_action_prompt(fromwho: str, towho: str, propname: str, traderes: bool) -> str:
    if not traderes:
        return f"{fromwho}向{towho}交换{propname}, 失败了"
    return f"{fromwho}向{towho}成功交换了{propname}"



def leave_for_stage_failed_because_stage_is_invalid_prompt(npcname: str, stagename: str) -> str:
    return f"""#{npcname}不能离开本场景并去往{stagename}，原因可能如下:
1. {stagename}目前对于{npcname}并不是一个有效场景。游戏可能尚未对其开放，或者已经关闭。
2. {stagename}的内容格式不对，例如下面的表达：‘xxx的深处/北部/边缘/附近/其他区域’，其中xxx可能是合理场景名，但加上后面的词后则变成了“无效场景名”（在游戏机制上无法正确检索与匹配）。
## 所以 {npcname} 请参考以上的原因，需要重新考虑去往的目的地。"""

def leave_for_stage_failed_because_already_in_stage_prompt(npcname: str, stagename: str) -> str:
    return f"你已经在{stagename}场景中了。需要重新考虑去往的目的地。'LeaveForActionComponent'行动类型意图是离开当前场景并去往某地。"

def replace_all_mentions_of_your_name_with_you(content: str, your_name: str) -> str:
    if len(content) == 0 or your_name not in content:
        return content
    return content.replace(your_name, "你")

###
def updated_information_on_WhoDoYouKnow_prompt(npcname: str, who_you_know: str) -> str:
    if len(who_you_know) == 0:
        return f"# 你更新了关于‘你都认识哪些角色’的信息，目前你没有认识的角色。"
    return f"# 你更新了关于‘你都认识哪些角色’的信息，目前你所认识的角色有: {who_you_know}"

### 
def updated_information_about_StagesYouKnow_prompt(npcname: str, where_you_know: str) -> str:
    if len(where_you_know) == 0:
        return f"# 你更新了关于‘你都认知哪些场景’的信息，目前你没有认识的场景。你不能去任何地方。"
    return f"# 你更新了关于‘你都认知哪些场景’的信息，目前你所知道的场景有: {where_you_know}。如果你意图离开本场景并去往其他场景，你只能从这些场景中选择你的目的地。"


    



def interactive_prop_action_success_prompt(who_use: str, targetname: str, propname: str) -> str:
    return f"{who_use}对{targetname}使用了{propname},顺利打开了{targetname}"







