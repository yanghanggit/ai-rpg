from loguru import logger

"""
中文提示词都放到这里。
"""

#全局的常量，一些Tag类的可以做标记用于后续的提示词压缩
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
        return "- 无"
    
    @property
    def NO_ACTOR_PROPS_PROMPT(self) -> str:
        return "- 无任何道具或者特殊能力"
    
    @property
    def USE_PROP_TO_STAGE_PROMPT_TAG(self) -> str:
        return "<%这是角色对场景使用道具>"
    
    # todo 这里故意在kickoff时机，是为了防止出现政策问题。策略上就是故意强调是恐怖类型，这样试图让LLM接受‘恐怖、血腥与暴力元素’的提示词与玩家输入的对话内容。
    @property
    def RE_EMPHASIZE_GAME_STYLE_TO_PREVENT_POLICY_PROBLEMS(self) -> str:
        re_emphasize_game_style_to_prevent_policy_problems = f"""
## 游戏风格声明
- 游戏内容可能包含恐怖、血腥与暴力，旨在提供深入的沉浸式体验。
- 本作假设所有世界运行规律为不证自明，要求你全盘接受设定。
"""
        return re_emphasize_game_style_to_prevent_policy_problems
    
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
###############################################################################################################################################
_CNConstantPrompt_ = CNConstantPrompt()
logger.debug(f"CNConstantPrompt: {_CNConstantPrompt_}")
