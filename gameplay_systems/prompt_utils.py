from enum import StrEnum, unique


@unique
class PromptTag(StrEnum):

    ACTOR_PLAN_PROMPT_TAG = "<%角色计划>"

    STAGE_PLAN_PROMPT_TAG = "<%场景计划>"

    STAGE_ENTRY_TAG = "场景进入限制"

    STAGE_EXIT_TAG = "场景离开限制"


################################################################################################################################################
@unique
class SkillResultPromptTag(StrEnum):
    SUCCESS = "</成功>"
    CRITICAL_SUCCESS = "</大成功>"
    FAILURE = "</失败>"


################################################################################################################################################
def replace_you(input_text: str, your_name: str) -> str:
    if len(input_text) == 0 or your_name not in input_text:
        return input_text
    return input_text.replace(your_name, "你")


################################################################################################################################################
