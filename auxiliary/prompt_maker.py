

from entitas import Entity # type: ignore
from auxiliary.extended_context import ExtendedContext
from auxiliary.components import NPCComponent, StageComponent

def npc_plan_prompt(entity: Entity, context: ExtendedContext) -> str:
    if not entity.has(NPCComponent):
        raise ValueError("npc_plan_prompt, entity has no NPCComponent")
    prompt = f"请回忆之前发生的事情并确认自身状态，根据‘做计划的规则’作出你的计划。要求：输出结果格式要遵循‘内容输出规则’。请带上‘特征标签’"
    return prompt

def stage_plan_prompt(entity: Entity, context: ExtendedContext) -> str:
    if not entity.has(StageComponent):
        raise ValueError("stage_plan_prompt, entity has no StageComponent")
    prompt = f"请回忆之前发生的事情并确认自身状态，根据‘做计划的规则’作出你的计划。要求：输出结果格式要遵循‘内容输出规则’。请带上‘特征标签’"
    return prompt

def read_archives_when_system_init_prompt(archives: str, entity: Entity, context: ExtendedContext) -> str:
    prompt = f"""
    # 你需要做“恢复记忆”的行为。
    ## 步骤:
    - 第1步:记忆如下{archives}.
    - 第2步:理解其中所有的信息.
    - 第3步:理解其中关于你的信息（如果提到了你，那就是关于你的信息.）
    - 第4步:根据信息更新你的最新状态与逻辑.
    - 根据‘做计划的规则’作出你的计划。要求：输出结果格式要遵循‘内容输出规则’
    """
    return prompt

def confirm_everything_after_director_add_new_memories_prompt(directorscripts: list[str], npcs_names: str, stagename: str, context: ExtendedContext) -> str:
    prompt = f"""
    # 下面是已经发生的事情,你目睹或者参与了这一切，并更新了你的记忆,如果与你记忆不相符则按照下面内容强行更新你的记忆:
    - {directorscripts}
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

def npc_memory_before_death(context: ExtendedContext) -> str:
    return f"你已经死亡（在战斗中受到了致命的攻击）"


def unique_prop_taken_away(entity: Entity, prop_name:str) -> str:
    if entity.has(NPCComponent):
        npc_name = entity.get(NPCComponent).name
        return f"{npc_name}找到了{prop_name},{prop_name}只存在唯一一份，其他人无法再搜到了。"
    else:
        return ""
    
def fail_to_enter_stage(npc_name: str, stage_name: str, enter_condition: str) -> str:
    return f"{npc_name}试图进入{stage_name} 但背包中没有{enter_condition}，不能进入，或许{npc_name}需要尝试搜索一下'{enter_condition}'."

def fail_to_exit_stage(npc_name: str, stage_name: str, exit_condition: str) -> str:
    return f"{npc_name}试图离开{stage_name} 但背包中没有{exit_condition}，不能离开，或许{npc_name}需要尝试搜索一下'{exit_condition}'."

def npc_enter_stage(npc_name: str, stage_name: str) -> str:
    return f"{npc_name}进入了{stage_name} 场景。"

def npc_leave_for_stage(npc_name: str, current_stage_name: str, leave_for_stage_name: str) -> str:
    return f"{npc_name}离开了{current_stage_name} 场景，前往{leave_for_stage_name} 场景。"

def kill_someone(attacker_name: str, target_name: str) -> str:
    return f"{attacker_name}对{target_name}发动了一次攻击,造成了{target_name}死亡。"

def attack_someone(attacker_name: str, target_name: str, damage: int, target_current_hp: int ,target_max_hp: int) -> str:
    health_percent = (target_current_hp - damage) / target_max_hp * 100
    return f"{attacker_name}对{target_name}发动了一次攻击,造成了{damage}点伤害,当前{target_name}的生命值剩余{health_percent}%。"