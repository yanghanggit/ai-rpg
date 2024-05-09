from entitas import Entity # type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import NPCComponent, StageComponent
from typing import Dict

def npc_plan_prompt(entity: Entity, context: ExtendedContext) -> str:
    if not entity.has(NPCComponent):
        raise ValueError("npc_plan_prompt, entity has no NPCComponent")
    prompt = f"根据‘计划制定指南’作出你的计划。要求：输出结果格式要遵循‘输出格式指南’,请确保给出的响应符合规范。结果中需要附带TagActionComponent"
    return prompt

def stage_plan_prompt(entity: Entity, context: ExtendedContext) -> str:
    if not entity.has(StageComponent):
        raise ValueError("stage_plan_prompt, entity has no StageComponent")
    prompt = f"根据‘计划制定指南’作出你的计划。要求：输出结果格式要遵循‘输出格式指南’,请确保给出的响应符合规范。结果中需要有EnviroNarrateActionComponent，并附带TagActionComponent。"
    return prompt

def read_archives_when_system_init_prompt(archives: str, entity: Entity, context: ExtendedContext) -> str:
    prompt = f"""
# 你回忆起了如下信息:
{archives}
## 请理解其中的信息并更新的你的状态。
## 遵循‘输出格式指南’，仅返回‘RememberActionComponent’及相关内容即可。"""
    return prompt

def read_all_neccesary_info_when_system_init_prompt(
        init_memory: str, 
        prop_and_desc: str, 
        current_stage: str, 
        where_you_know: str, 
        who_you_know: str) -> str:
    
    prop_and_desc_prompt = f""" 
# 你有如下道具和其描述:
{prop_and_desc}"""
    if len(prop_and_desc) == 0:
        prop_and_desc_prompt = ""
    
    who_you_know_prompt = f"""
# 你认识的人有:
{who_you_know}.
"""
    if len(who_you_know) == 0:
        who_you_know_prompt = ""
    
    where_you_know_prompt = f"""如果你想前往其他场景，你只能从{where_you_know}中选择你的目的地."""
    if where_you_know is None or len(where_you_know) == 0:
        where_you_know_prompt = ""

    prompt = f"""
# 你回忆起了如下信息:
{init_memory}
{prop_and_desc_prompt}
# 你所在的场景是:{current_stage}.
{where_you_know_prompt}
{who_you_know_prompt}
## 请理解其中的信息并更新的你的状态。
## 遵循‘输出格式指南’，仅返回‘RememberActionComponent’及相关内容即可。"""
    return prompt

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


# 重构用 摩尔=>摩尔试图寻找奇异的声响，但奇异的声响在场景中不存在或者被其他人拿走了,需要再重新考虑目标。
def search_failed_prompt(npcname: str, prop_name:str) -> str:
    return f"""{npcname}试图在场景内搜索"{prop_name}"这个道具，但失败了。原因可能如下:
1. "{prop_name}"可能并非是一个道具。'SearchActionComponent'只能支持搜索道具的行为与计划
2. 或者这个道具此时已不在本场景中（可能被其他角色搜索并获取了）。
所以{npcname}需要再重新考虑搜索目标。可以使用PerceptionActionComponent来感知场景内的道具，并确认合理目标。"""

def search_success_prompt(npcname: str, prop_name:str, stagename: str) -> str:
    return f"{npcname}从{stagename}场景内成功找到并获取了道具:{prop_name}。{stagename}中不再存在这个道具。"

# def unique_prop_taken_away(entity: Entity, prop_name:str) -> str:
#     if entity.has(NPCComponent):
#         npc_name: str = entity.get(NPCComponent).name
#         return __unique_prop_taken_away__(npc_name, prop_name)
#         #return f"{npc_name}找到了{prop_name},{prop_name}只存在唯一一份，其他人无法再搜到了。"
#     #else:
#     return ""

    
# def fail_to_enter_stage(npc_name: str, stage_name: str, enter_condition: str) -> str:
#     return f"{npc_name}试图进入{stage_name} 但背包中没有{enter_condition}，不能进入，或许{npc_name}需要尝试搜索一下'{enter_condition}'."

# def fail_to_exit_stage(npc_name: str, stage_name: str, exit_condition: str) -> str:
#     return f"{npc_name}试图离开{stage_name} 但背包中没有{exit_condition}，不能离开，或许{npc_name}需要尝试搜索一下'{exit_condition}'."

#
def notify_all_already_in_target_stage_that_someone_enter_stage_prompt(some_ones_name: str, target_stage_name: str, last_stage_name: str) -> str:
    return f"{some_ones_name}进入了场景——{target_stage_name}。"

#
def notify_myself_leave_for_from_prompt(some_ones_name: str, target_stage_name: str, last_stage_name: str) -> str:
    return f"{some_ones_name}离开了{last_stage_name}, 进入了{target_stage_name}。"


def npc_leave_stage_prompt(npc_name: str, current_stage_name: str, leave_for_stage_name: str) -> str:
    return f"{npc_name}离开了{current_stage_name} 场景。"

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

def perception_action_prompt(stagename: str, npcnames: str, propnames: str) -> str:
    res = ""
    if len(npcnames) > 0:
        res += f"你感知到了你所在的场景——{stagename}内有这些角色:{npcnames}。"
    if len(propnames) > 0:
        res += f"{stagename}中有这些道具:{propnames}。"
    if len(res) == 0:
        return f"你感知到了你所在的场景——{stagename}中没有其他的角色。也没有任何道具。"
    return res

def check_status_action_prompt(who: str, propnames: str, props_and_desc: str) -> str:
    if len(propnames) == 0:
        return f"你目前没有任何道具。"
    
    res = ""
    if len(propnames) > 0:
        res += f"通过检查，你目前拥有这些道具: {propnames}。"

    res += "道具的信息如下:\n"
    res += props_and_desc
    return res

def leave_for_stage_failed_because_stage_is_invalid_prompt(npcname: str, stagename: str) -> str:
    return f"""#{npcname}不能离开本场景并去往{stagename}，原因可能如下:
1. {stagename}目前对于{npcname}并不是一个有效场景。游戏可能尚未对其开放，或者已经关闭。
2. {stagename}的内容格式不对，例如下面的表达：‘xxx的深处/北部/边缘/附近/其他区域’，其中xxx可能是合理场景名，但加上后面的词后则变成了“无效场景名”（在游戏机制上无法正确检索与匹配）。
## 所以 {npcname} 请参考以上的原因，需要重新考虑去往的目的地。"""

def leave_for_stage_failed_because_already_in_stage_prompt(npcname: str, stagename: str) -> str:
    return f"你已经在{stagename}场景中了。需要重新考虑去往的目的地。'LeaveForActionComponent'行动类型意图是离开当前场景并去往某地。"

def direct_stage_events_prompt(message: str, context: ExtendedContext) -> str:
    prompt = f"""
# 场景内发生了如下事件：
{message}
# 根据以上更新你的状态。并以此作为做后续计划的基础。"""
    return prompt

def direct_npc_events_prompt(message: str, context: ExtendedContext) -> str:
    prompt = f"""
# 场景内发生了如下事件(有些是你参与的，有些是你目睹或感知到的)：
{message}
# 根据以上更新你的状态。并以此作为做后续计划的基础。"""
    return prompt

def replace_all_mentions_of_your_name_with_you(content: str, your_name: str) -> str:
    if len(content) == 0 or your_name not in content:
        return content
    return content.replace(your_name, "你")

###
def known_information_update_who_you_know_prompt(npcname: str, who_you_know: str) -> str:
    if len(who_you_know) == 0:
        return f"# 你更新了记忆，你目前没有认识的角色。"
    return f"# 你更新了记忆，你所认识的角色目前有: {who_you_know}"

### 
def known_information_update_where_you_know_prompt(npcname: str, where_you_know: str) -> str:
    if len(where_you_know) == 0:
        return f"# 你更新了记忆，你目前没有认识的场景。你不能去任何地方。"
    return f"# 你更新了记忆，你所知道的场景有: {where_you_know}。如果你想前往其他场景，你只能从这些场景中选择你的目的地。"

##
def leave_for_stage_failed_because_no_exit_condition_match_prompt(npcname: str, stagename: str, tips: str) -> str:
    if tips == "":
        return f"""#{npcname}不能离开本场景并去往{stagename},可能当前不满足离开的条件。可以通过CheckStatusActionComponent查看自己拥有的道具，或者通过PerceptionActionComponent感知场景内的道具，找到离开的条件。"""
    return f"""{npcname}不能离开本场景并去往{stagename}。\n提示:{tips}"""

##
def direct_npc_events_before_leave_stage_prompt(message: str, current_stage_name: str, context: ExtendedContext) -> str:
    prompt = f"""
# 在你准备离开{current_stage_name}之前，{current_stage_name}内发生了如下事件(有些是你参与的，有些是你目睹或感知到的)：
{message}
# 你记录了这些事件，并更新了你的状态。"""
    return prompt






################################################################################################################################################
def remember_begin_before_game_start_prompt(npcname: str, memorycontent: str, context: ExtendedContext) -> str:
    if memorycontent == "":
        return f"""# 世界即将开始运行。你开始回忆关于你的信息与设定。目前你没有任何记忆。"""

    return f"""# 世界即将开始运行。在这之前，你需要先开始回忆关于你的信息与设定。
## 你最后的记忆是这样的:\n{memorycontent}"""
################################################################################################################################################          
def check_status_before_game_start_prompt(npcname: str, propsinfo: str, context: ExtendedContext) -> str:
    if propsinfo == "":
        return f"""# 你检查了自身的状态与持有的道具。目前你没有任何道具。"""
    
    return f"""# 你开始检查自身的状态与持有的道具。
## 目前已经拥有的道具如下:\n{propsinfo}"""
################################################################################################################################################
def remember_npc_archives_before_game_start_prompt(npcname: str, who_you_know: str, context: ExtendedContext) -> str:
    if who_you_know == "":
        return f"""# 你试图回顾你认识的角色。目前你并没有认识任何人。"""
    
    return f"""# 你试图回顾你认识的角色。
## 目前你认识的角色有:\n{who_you_know}"""
################################################################################################################################################
def confirm_current_stage_before_game_start_prompt(npcname: str, current_stage_name: str, context: ExtendedContext) -> str:
    if current_stage_name == "":
        return f"""# 你当前并不在任何场景中。"""
    
    return f"""# 目前你所在的场景是:{current_stage_name}"""
################################################################################################################################################
def confirm_stages_before_game_start_prompt(npcname: str, stages_names: str, context: ExtendedContext) -> str:
    if stages_names == "":
        return f"""# 目前你并不认识任何场景，根据游戏机制，也没有任何可以前往的场景。"""
        
    return f"""# 目前，你认识的场景有:{stages_names}。
## 根据游戏机制你可以前往这些场景。目前你只能从{stages_names}中选择你的目的地，随着你认识的场景更新，你可以去的场景也会增加。"""
################################################################################################################################################
def current_stage_you_saw_someone_appearance_prompt(safe_stage_name: str, npcname: str, appearance:str, context: ExtendedContext) -> str:
    return f"当前场景——{safe_stage_name}内，你看到了{npcname}，{appearance}"
################################################################################################################################################
def remember_end_before_game_start_prompt(npcname: str, context: ExtendedContext) -> str:
    return f"""# 你回顾了以上的信息，包括最后的记忆，自身状态(拥有道具及其信息)，认识的角色，所处场景(及场景的角色)与认识的场景。"""
################################################################################################################################################
def notify_game_start_prompt(npcname: str, context: ExtendedContext) -> str:
    return f"""# 现在世界开始运转，你——{npcname}，已经准备好了。你需要将自己完全带入你的角色设定并开始游戏。
请遵循输出格式指南，仅通过返回RememberActionComponent及相关内容来确认你的状态。"""
################################################################################################################################################
def someone_came_into_my_stage_his_appearance_prompt(someone: str, hisappearance: str) -> str:
    return f"""你发现{someone}进入了场景，其外貌信息如下：{hisappearance}"""
################################################################################################################################################
def npc_appearance_in_this_stage_prompt(myname: str, npc_appearance_in_stage: Dict[str, str]) -> str:
    batch = ""
    for npcname, appearance in npc_appearance_in_stage.items():
        batch += f"{npcname}，{appearance}\n"
    return f"""你观察到了你所在场景内的角色外貌信息如下:\n{batch}"""
################################################################################################################################################

