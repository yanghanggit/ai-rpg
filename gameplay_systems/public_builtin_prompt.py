from extended_systems.files_def import PropFile
from enum import StrEnum


# 全局的常量，一些Tag类的可以做标记用于后续的提示词压缩
class ConstantPrompt(StrEnum):

    ACTOR_PLAN_PROMPT_TAG = "<%这是角色计划>"

    STAGE_PLAN_PROMPT_TAG = "<%这是场景计划>"

    COMPRESS_ACTOR_PLAN_PROMPT = "请做出你的计划，决定你将要做什么"

    COMPRESS_STAGE_PLAN_PROMPT = "请输出'你的当前描述'和'你的计划'"

    BROADCASE_ACTION_TAG = "<%这是广播行动结果>"

    SPEAK_ACTION_TAG = "<%这是说话行动结果>"

    WHISPER_ACTION_TAG = "<%这是私语行动结果>"

    BATCH_CONVERSATION_ACTION_EVENTS_TAG = "<%这是场景内对话事件>"

    STAGE_ENTRY_TAG = "场景进入限制"

    STAGE_EXIT_TAG = "场景离开限制"

    SUCCESS = "</成功>"

    CRITICAL_SUCCESS = "</大成功>"

    FAILURE = "</失败>"

    ACTOR_KICK_OFF_MESSAGE_PROMPT_TAG = "<%这是角色初始化>"

    STAGE_KICK_OFF_MESSAGE_PROMPT_TAG = "<%这是场景初始化>"

    WORLD_SYSTEM_KICK_OFF_MESSAGE_PROMPT_TAG = "<%这是世界系统初始化>"

    UNKNOWN_STAGE_NAME = "未知场景:"


###############################################################################################################################################
def generate_prop_type_prompt(prop_file: PropFile) -> str:

    ret = "未知"

    if prop_file.is_weapon:
        ret = "武器"
    elif prop_file.is_clothes:
        ret = "衣服"
    elif prop_file.is_non_consumable_item:
        ret = "非消耗品"
    elif prop_file.is_special:
        ret = "特殊能力"
    elif prop_file.is_skill:
        ret = "技能"

    return ret


###############################################################################################################################################
def generate_prop_prompt(
    prop_file: PropFile,
    description_prompt: bool,
    appearance_prompt: bool,
    attr_prompt: bool = False,
) -> str:

    prompt = f"""### {prop_file.name}
- 类型:{generate_prop_type_prompt(prop_file)}"""

    if description_prompt:
        prompt += f"\n- 道具描述:{prop_file.description}"

    if appearance_prompt:
        prompt += f"\n- 道具外观:{prop_file.appearance}"

    if attr_prompt:
        prompt += f"\n- 攻击力:{prop_file.attack}\n- 防御力:{prop_file.defense}"

    return prompt


################################################################################################################################################
def replace_you(content: str, your_name: str) -> str:
    if len(content) == 0 or your_name not in content:
        return content
    return content.replace(your_name, "你")


################################################################################################################################################
def generate_unknown_guid_stage_name_prompt(guid: int) -> str:
    return f"{ConstantPrompt.UNKNOWN_STAGE_NAME}{guid}"


################################################################################################################################################
def is_stage_name_unknown(stage_name: str) -> bool:
    return ConstantPrompt.UNKNOWN_STAGE_NAME in stage_name


################################################################################################################################################
def extract_stage_guid(stage_name: str) -> int:
    if not is_stage_name_unknown(stage_name):
        return -1
    return int(stage_name.split(":")[1])


################################################################################################################################################
