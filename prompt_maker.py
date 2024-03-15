

from entitas import Entity
from extended_context import ExtendedContext
from components import NPCComponent, StageComponent

def npc_plan_prompt(entity: Entity, context: ExtendedContext) -> str:
    if not entity.has(NPCComponent):
        raise ValueError("npc_plan_prompt, entity has no NPCComponent")
    prompt = "请回忆之前发生的事情并确认自身状态，然后作出你的计划。"
    return prompt


def stage_plan_prompt(entity: Entity, context: ExtendedContext) -> str:
    if not entity.has(StageComponent):
        raise ValueError("stage_plan_prompt, entity has no StageComponent")
    prompt = "请回忆之前发生的事情并确认自身状态，然后作出你的计划。"
    return prompt


def director_prompt(director_scripts: str, entity: Entity, context: ExtendedContext) -> str:

    if not entity.has(StageComponent):
        raise ValueError("director_prompt, entity has no StageComponent")

    prompt = f"""
        # 你按着我的给你的脚本来演绎过程，并适当润色让过程更加生动。
        ## 剧本如下:
        - {director_scripts}
        ## 步骤
        - 第1步：理解我的剧本
        - 第2步：根据剧本，完善你的故事讲述(同一个人物的行为描述要合并处理)。要保证和脚本的结果一致。
        - 第3步：更新你的记忆
        ## 输出规则
        - 输出在保证语意完整基础上字符尽量少。
        """
    
    return prompt


def load_prompt(archives: str, entity: Entity, context: ExtendedContext) -> str:
    load_prompt = f"""
    # 你需要做“恢复记忆”的行为。
    ## 步骤:
    - 第1步:记忆如下{archives}.
    - 第2步:理解其中所有的信息.
    - 第3步:理解其中关于你的信息（如果提到了你，那就是关于你的信息.）
    - 第4步:根据信息更新你的最新状态与逻辑.
    """
    return load_prompt