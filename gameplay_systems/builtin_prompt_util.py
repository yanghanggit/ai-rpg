from enum import StrEnum, unique


@unique
class ConstantPromptTag(StrEnum):

    ACTOR_PLAN_PROMPT_TAG = "<%这是角色计划>"

    STAGE_PLAN_PROMPT_TAG = "<%这是场景计划>"

    # BROADCASE_ACTION_TAG = "<%这是广播行动结果>"

    SPEAK_ACTION_TAG = "<%这是说话行动结果>"

    WHISPER_ACTION_TAG = "<%这是私语行动结果>"

    STAGE_ENTRY_TAG = "场景进入限制"

    STAGE_EXIT_TAG = "场景离开限制"

    ACTOR_KICK_OFF_MESSAGE_PROMPT_TAG = "<%这是角色初始化>"

    STAGE_KICK_OFF_MESSAGE_PROMPT_TAG = "<%这是场景初始化>"

    WORLD_SYSTEM_KICK_OFF_MESSAGE_PROMPT_TAG = "<%这是世界系统初始化>"

    UNKNOWN_STAGE_NAME_TAG = "未知场景:"


################################################################################################################################################
@unique
class ConstantSkillPrompt(StrEnum):
    SUCCESS = "</成功>"
    CRITICAL_SUCCESS = "</大成功>"
    FAILURE = "</失败>"


################################################################################################################################################
def replace_you(content: str, your_name: str) -> str:
    if len(content) == 0 or your_name not in content:
        return content
    return content.replace(your_name, "你")


################################################################################################################################################
def generate_unknown_stage_name(guid: int) -> str:
    return f"{ConstantPromptTag.UNKNOWN_STAGE_NAME_TAG}{guid}"


################################################################################################################################################
def is_unknown_stage_name(stage_name: str) -> bool:
    return ConstantPromptTag.UNKNOWN_STAGE_NAME_TAG in stage_name


################################################################################################################################################
def extract_guid_from_unknown_stage_name(stage_name: str) -> int:
    if not is_unknown_stage_name(stage_name):
        return -1
    return int(stage_name.split(":")[1])


################################################################################################################################################
