from loguru import logger


# 全局的常量，一些Tag类的可以做标记用于后续的提示词压缩
class CNConstantPrompt:

    @property
    def ACTOR_PLAN_PROMPT_TAG(self) -> str:
        return "<%这是角色计划>"

    @property
    def STAGE_PLAN_PROMPT_TAG(self) -> str:
        return "<%这是场景计划>"

    @property
    def COMPRESS_ACTOR_PLAN_PROMPT(self) -> str:
        return "请做出你的计划，决定你将要做什么"

    @property
    def COMPRESS_STAGE_PLAN_PROMPT(self) -> str:
        return "请输出'你的当前描述'和'你的计划'"

    @property
    def NONE_PROMPT(self) -> str:
        return "无"

    @property
    def NO_ACTOR_PROPS_PROMPT(self) -> str:
        return "无任何道具或者特殊能力"

    @property
    def USE_PROP_TO_STAGE_PROMPT_TAG(self) -> str:
        return "<%这是角色对场景使用道具>"

    @property
    def PERCEPTION_ACTION_TAG(self) -> str:
        return "<%这是感知行动结果>"

    @property
    def CHECK_STATUS_ACTION_TAG(self) -> str:
        return "<%这是查看自身状态行动结果>"

    @property
    def BROADCASE_ACTION_TAG(self) -> str:
        return "<%这是广播行动结果>"

    @property
    def SPEAK_ACTION_TAG(self) -> str:
        return "<%这是说话行动结果>"

    @property
    def WHISPER_ACTION_TAG(self) -> str:
        return "<%这是私语行动结果>"

    @property
    def BATCH_CONVERSATION_ACTION_EVENTS_TAG(self) -> str:
        return "<%这是场景内对话事件>"

    @property
    def STAGE_ENTRY_TAG(self) -> str:
        return f"场景进入限制"

    @property
    def STAGE_EXIT_TAG(self) -> str:
        return f"场景离开限制"

    @property
    def SUCCESS(self) -> str:
        return "</成功>"

    @property
    def BIG_SUCCESS(self) -> str:
        return "</大成功>"

    @property
    def FAILURE(self) -> str:
        return "</失败>"

    @property
    def BIG_FAILURE(self) -> str:
        return "</大失败>"


###############################################################################################################################################
_CNConstantPrompt_ = CNConstantPrompt()
