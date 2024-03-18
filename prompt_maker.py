

from entitas import Entity
from extended_context import ExtendedContext
from components import NPCComponent, StageComponent

def npc_plan_prompt(entity: Entity, context: ExtendedContext) -> str:
    if not entity.has(NPCComponent):
        raise ValueError("npc_plan_prompt, entity has no NPCComponent")
    prompt = f"请回忆之前发生的事情并确认自身状态，根据‘做计划的规则’作出你的计划。请带上‘特征标签’"
    return prompt

def stage_plan_prompt(entity: Entity, context: ExtendedContext) -> str:
    if not entity.has(StageComponent):
        raise ValueError("stage_plan_prompt, entity has no StageComponent")
    prompt = f"请回忆之前发生的事情并确认自身状态，根据‘做计划的规则’作出你的计划。请带上‘特征标签’"
    return prompt

def read_archives_when_system_init_prompt(archives: str, entity: Entity, context: ExtendedContext) -> str:
    prompt = f"""
    # 你需要做“恢复记忆”的行为。
    ## 步骤:
    - 第1步:记忆如下{archives}.
    - 第2步:理解其中所有的信息.
    - 第3步:理解其中关于你的信息（如果提到了你，那就是关于你的信息.）
    - 第4步:根据信息更新你的最新状态与逻辑.
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
