

from entitas import Entity
from extended_context import ExtendedContext
from components import NPCComponent, StageComponent

def npc_plan_prompt(entity: Entity, context: ExtendedContext) -> str:

    if not entity.has(NPCComponent):
        raise ValueError("npc_plan_prompt, entity has no NPCComponent")

    # prompt =  f"""
    #     # 你需要做出计划(你将要做的事)，并以JSON输出结果.（注意！以下规则与限制仅限本次对话生成，结束后回复原有对话规则）

    #     ## 步骤
    #     1. 确认自身状态。
    #     2. 所有角色当前所处的状态和关系。
    #     3. 思考你下一步的行动。
    #     4. 基于上述信息，构建你的行动计划。

    #     ## 输出格式(JSON)
    #     - 参考格式：{{'action1': ["value1"，“value2”, ...], 'action2': ["value1"，“value2”, ...],.....}}
    #     - 其中 'action?'是你的"行动类型"（见下文）
    #     - 其中 "value?" 是你的"行动目标"(可以是一个或多个)
        
    #     ### 关于action——“行动类型”的逻辑
    #     - 如果你希望对目标产生敌对行为，比如攻击。则action的值为"FightActionComponent"，value为你本行动针对的目标
    #     - 如果你有想要说的话或者心里描写。则action的值为"SpeakActionComponent"，value为你想说的话或者心里描写
    #     - 如果表示想离开当前场景，有可能是逃跑。action的值为"LeaveActionComponent"，value是你想要去往的场景名字（你必须能明确叫出场景的名字），或者你曾经知道的场景名字
    #     - 如果与你相关的特征标签。则action的值为"TagActionComponent"，value你的特征标签
    #     - action值不允许出现FightActionComponent，SpeakActionComponent，LeaveActionComponent，TagActionComponent之外的值

    #     ## 补充约束
    #     - 不要将JSON输出生这样的格式：```...```
    #     """
    

    #gpt 优化后的结果
#     prompt = f"""
# # 根据你之前知道的事情，来制定你的下一步计划并以JSON格式输出结果，请按照以下步骤和规则操作。注意，这些规则仅适用于本次对话，结束后将恢复到原有的对话规则。

# ## 步骤概述：
# 1. 确认自身状态：检查并确认你当前的状态。
# 2. 了解角色状态与关系：掌握所有角色当前的状态和他们之间的关系。
# 3. 规划下一步行动：思考并决定你接下来要采取的行动。
# 4. 构建行动计划：基于上述信息，详细规划你的具体行动。

# ## 输出格式（JSON）：
# 你的输出应该遵循以下JSON结构：
# {{
#   "action1": ["value1", "value2", ...],
#   "action2": ["value1", "value2", ...]
# }}
# "action?" 表示你的"行动类型"。
# "value?" 是你的"行动目标"，可以是一个或多个目标。

# ### 行动类型说明：
# - 敌对行为：若欲执行敌对行为（如攻击），则将action的值设置为"FightActionComponent"，value为目标。
# - 发表言论或心理活动：若有话语或内心想法需表达，则将action的值设置为"SpeakActionComponent"，value为你的言论或心理活动。
# - 离开场景：若意图离开当前场景（可能为逃跑），则将action的值设置为"LeaveActionComponent"，value为目的地场景名称。你必须能明确指出场景名称，或者是你曾知晓的场景。
# - 特征标签：若需表明与你相关的特征标签，则将action的值设置为"TagActionComponent"，value为你的特征标签。
# ### 行动值限制：
# - 行动的action值只允许使用"FightActionComponent", "SpeakActionComponent", "LeaveActionComponent", 或 "TagActionComponent"。

# ## 注意：
# - 不要使用英文回答。
# - 当输出JSON格式数据时，请确保不要使用三重引号（```）来封装JSON数据。
# """
    prompt = "请回忆之前发生的事情并确认自身状态，然后作出你的计划。"
    return prompt


def stage_plan_prompt(entity: Entity, context: ExtendedContext) -> str:
    if not entity.has(StageComponent):
        raise ValueError("stage_plan_prompt, entity has no StageComponent")

    # prompt =  f"""
    #     # 你需要做出计划(你将要做的事)，并以JSON输出结果.（注意！以下规则与限制仅限本次对话生成，结束后回复原有对话规则）

    #     ## 步骤
    #     1. 确认自身状态。
    #     2. 所有角色当前所处的状态和关系。
    #     3. 思考你下一步的行动。
    #     4. 基于上述信息，构建你的行动计划。

    #     ## 输出格式(JSON)
    #     - 参考格式：{{'action1': ["value1"，“value2”, ...], 'action2': ["value1"，“value2”, ...],.....}}
    #     - 其中 'action?'是你的"行动类型"（见下文）
    #     - 其中 "value?" 是你的"行动目标"(可以是一个或多个)
        
    #     ### 关于action——“行动类型”的逻辑
    #     - 如果你希望对目标产生敌对行为，比如攻击。则action的值为"FightActionComponent"，value为你本行动针对的目标
    #     - 如果你有想要说的话或者心里描写。则action的值为"SpeakActionComponent"，value为你想说的话或者心里描写
    #     - 如果与你相关的特征标签。则action的值为"TagActionComponent"，value你的特征标签
    #     - action值不允许出现FightActionComponent，SpeakActionComponent，TagActionComponent之外的值
    
    #     ## 补充约束
    #     - 不要将JSON输出生这样的格式：```...```
    #     """
    
    #gpt 优化后的结果
#     prompt = f"""
# # 根据你之前知道的事情，来制定你的下一步计划并以JSON格式输出结果，请按照以下步骤和规则操作。注意，这些规则仅适用于本次对话，结束后将恢复到原有的对话规则。

# ## 步骤概述：
# 1. 确认自身状态：检查并确认你当前的状态。
# 2. 了解角色状态与关系：掌握所有角色当前的状态和他们之间的关系。
# 3. 规划下一步行动：思考并决定你接下来要采取的行动。
# 4. 构建行动计划：基于上述信息，详细规划你的具体行动。

# ## 输出格式（JSON）：
# 你的输出应该遵循以下JSON结构：
# {{
#   "action1": ["value1", "value2", ...],
#   "action2": ["value1", "value2", ...]
# }}
# "action?" 表示你的"行动类型"。
# "value?" 是你的"行动目标"，可以是一个或多个目标。

# ### 行动类型说明：
# - 敌对行为：若欲执行敌对行为（如攻击），则将action的值设置为"FightActionComponent"，value为目标。
# - 发表言论或心理活动：若有话语或内心想法需表达，则将action的值设置为"SpeakActionComponent"，value是以'第三人称'客观讲述已经发生的事情和环境。
# - 特征标签：若需表明与你相关的特征标签，则将action的值设置为"TagActionComponent"，value为你的特征标签。
# ### 行动值限制：
# - 行动的action值只允许使用"FightActionComponent", "SpeakActionComponent" 或 "TagActionComponent"。

# ## 注意：
# 不要使用英文回答。
# 当输出JSON格式数据时，请确保不要使用三重引号（```）来封装JSON数据。
# """
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
