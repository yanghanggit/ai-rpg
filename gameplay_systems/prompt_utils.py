from enum import StrEnum, unique
from my_components.action_components import StageNarrateAction


@unique
class PromptTag(StrEnum):

    CURRENT_ROUND_TAG = "<当前回合数>"

    ACTOR_PLAN_PROMPT_TAG = "<角色计划>"

    STAGE_PLAN_PROMPT_TAG = "<场景计划>"

    STAGE_ENTRY_TAG = "场景进入限制"

    STAGE_EXIT_TAG = "场景离开限制"


################################################################################################################################################
@unique
class SkillResultPromptTag(StrEnum):
    SUCCESS = "<成功>"
    CRITICAL_SUCCESS = "<大成功>"
    FAILURE = "<失败>"


################################################################################################################################################
def replace_you(input_text: str, your_name: str) -> str:
    if len(input_text) == 0 or your_name not in input_text:
        return input_text
    return input_text.replace(your_name, "你")


################################################################################################################################################
def insert_stage_narrate_action_prompt() -> str:
    return f"""## 注意！{StageNarrateAction.__name__} —— 场景描述 生成规则
### 步骤
1. 事件回顾：回顾场景内已发生的角色行为、对话及道具使用，判断这些事件对场景状态的具体影响。场景会根据自身设定进行逻辑性变化，例如自然发展的状态变化（如火焰蔓延）。切勿推测未发生的活动。
2. 状态更新与描述：结合事件回顾和场景设定，推理并更新场景的最新状态。生成的场景描述应着重展示环境背景及关键细节，如光线、气味和音效。
3. 角色信息排除：移除描述中的所有角色相关信息，仅呈现场景本身的完整细节。
### 注意事项
- 输出必须清晰反映场景的当前状态及变化，不应包含角色行为或心理描写。
- 描述应有层次感，确保在确保‘角色信息排除’的基础上，场景状态更新全面而无遗漏。"""


################################################################################################################################################
