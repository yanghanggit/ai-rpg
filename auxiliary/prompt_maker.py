

from entitas import Entity # type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import NPCComponent, StageComponent

def npc_plan_prompt(entity: Entity, context: ExtendedContext) -> str:
    if not entity.has(NPCComponent):
        raise ValueError("npc_plan_prompt, entity has no NPCComponent")
    prompt = f"根据‘计划制定指南’作出你的计划。要求：输出结果格式要遵循‘输出格式指南’,请确保给出的响应符合规范。"
    return prompt

def stage_plan_prompt(entity: Entity, context: ExtendedContext) -> str:
    if not entity.has(StageComponent):
        raise ValueError("stage_plan_prompt, entity has no StageComponent")
    prompt = f"根据‘计划制定指南’作出你的计划。要求：输出结果格式要遵循‘输出格式指南’,请确保给出的响应符合规范。"
    return prompt

def read_archives_when_system_init_prompt(archives: str, entity: Entity, context: ExtendedContext) -> str:
    prompt = f"""
    # 你回忆起了如下信息:
    {archives}
    ## 请理解其中的信息并更新的你的状态。
    ## 遵循‘输出格式指南’，仅返回‘RememberActionComponent’及相关内容即可。
    """
    return prompt

def confirm_everything_after_director_add_new_memories_prompt(allevents: list[str], npcs_names: str, stagename: str, context: ExtendedContext) -> str:
    prompt = f"""
    # 下面是已经发生的事情,你目睹或者参与了这一切，并更新了你的记忆,如果与你记忆不相符则按照下面内容强行更新你的记忆:
    - {allevents}
    # 你能确认
    - {npcs_names} 都还在此 {stagename} 场景中。
    - 你需要更新你的状态并以此作为做后续计划的基础。
    """
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

def died_in_fight(context: ExtendedContext) -> str:
    return f"你已经死亡（在战斗中受到了致命的攻击）"


# 重构用 摩尔=>摩尔试图寻找奇异的声响，但奇异的声响在场景中不存在或者被其他人拿走了,需要再重新考虑目标。
def search_failed_prompt(npcname: str, prop_name:str) -> str:
    return f"""{npcname}试图在场景内搜索"{prop_name}"，但失败了。原因可能如下:
    1. "{prop_name}"并非是一个道具。'SearchActionComponent'只能支持搜索道具的行为与计划
    2. 或者其此时不在本场景中（有可能被其他角色搜索并获取了）。
    所以{npcname}需要再重新考虑搜索目标。"""


# def unique_prop_taken_away(entity: Entity, prop_name:str) -> str:
#     if entity.has(NPCComponent):
#         npc_name: str = entity.get(NPCComponent).name
#         return __unique_prop_taken_away__(npc_name, prop_name)
#         #return f"{npc_name}找到了{prop_name},{prop_name}只存在唯一一份，其他人无法再搜到了。"
#     #else:
#     return ""

    
def fail_to_enter_stage(npc_name: str, stage_name: str, enter_condition: str) -> str:
    return f"{npc_name}试图进入{stage_name} 但背包中没有{enter_condition}，不能进入，或许{npc_name}需要尝试搜索一下'{enter_condition}'."

def fail_to_exit_stage(npc_name: str, stage_name: str, exit_condition: str) -> str:
    return f"{npc_name}试图离开{stage_name} 但背包中没有{exit_condition}，不能离开，或许{npc_name}需要尝试搜索一下'{exit_condition}'."

def npc_enter_stage(npc_name: str, stage_name: str) -> str:
    return f"{npc_name}进入了{stage_name} 场景。"

def npc_leave_for_stage(npc_name: str, current_stage_name: str, leave_for_stage_name: str) -> str:
    return f"{npc_name}离开了{current_stage_name} 场景。"

def kill_someone(attacker_name: str, target_name: str) -> str:
    return f"{attacker_name}对{target_name}发动了一次攻击,造成了{target_name}死亡。"

def attack_someone(attacker_name: str, target_name: str, damage: int, target_current_hp: int ,target_max_hp: int) -> str:
    health_percent = (target_current_hp - damage) / target_max_hp * 100
    return f"{attacker_name}对{target_name}发动了一次攻击,造成了{damage}点伤害,当前{target_name}的生命值剩余{health_percent}%。"

def speak_action_system_invalid_target(target_name: str, speakcontent: str) -> str:
    return f"[{target_name}]在你所在场景内无法找到，所以你不能对其说如下的内容：{speakcontent}"

def perception_action_prompt(npcnames: str, propnames: str) -> str:
    return f"你感知到了场景中有这些角色{npcnames}, 场景中有这些道具{propnames}"

def steal_action_prompt(whosteal: str, targetname: str, propname: str, stealres: bool) -> str:
    if not stealres:
        return f"{whosteal}从{targetname}盗取{propname}, 失败了"
    return f"{whosteal}从{targetname}成功盗取了{propname}"

def trade_action_prompt(fromwho: str, towho: str, propname: str, traderes: bool) -> str:
    if not traderes:
        return f"{fromwho}向{towho}交换{propname}, 失败了"
    return f"{fromwho}向{towho}成功交换了{propname}"

def check_status_action_prompt(who: str, propnames: str) -> str:
    return f"{who}正在检查状态, 发现了这些道具{propnames}"

def leave_for_stage_is_invalid_prompt(npcname: str, stagename: str) -> str:
    return f"""#{npcname}不能离开本场景并去往{stagename}，原因可能如下:
    1. {stagename}目前并不是一个有效的场景，游戏可能尚未开放或者已经关闭。
    2. {stagename}的内容格式不对，例如：‘{stagename}的深处/边缘/附近/其他区域’，其中xxx是合理的场景名，加上后面的词后就变成了一个“无效的场景名”（在游戏机制上不能去往）。
    3. {npcname} 目前并不知道{stagename}的存在。
    ## 所以 {npcname} 需要重新考虑目标"""