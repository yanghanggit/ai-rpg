from enum import StrEnum



# 全局的常量，一些Tag类的可以做标记用于后续的提示词压缩
class CNConstantPrompt(StrEnum):

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

###############################################################################################################################################
