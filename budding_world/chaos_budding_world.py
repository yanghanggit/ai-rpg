from auxiliary.chaos_engineering_system import IChaosEngineering
from loguru import logger
from auxiliary.builders import WorldDataBuilder
from typing import Any, Optional

## 测试重复的json内容，应该是load不出来才对
error_repeat = f"""{{"RememberActionComponent": ["测试的字符串"]}}{{"WhisperActionComponent": ["测试的字符串"]}}"""

## 有额外的字符串
error_extra_string_added = f"""{{"LeaveForActionComponent": ["悠扬林谷"]}}一个测试的字符串，不应该出现在这里"""

## SpeakActionComponent的格式，value格式就不对。应该是"@目标名字>对话内容"
error_speak_format = f"""{{"SpeakActionComponent": ["这是一个错误的格式"]}}"""
error_speak_target_is_invalid = f"""{{"SpeakActionComponent": ["@一个测试的目标>测试的对话内容"]}}"""

## value必须以[]形式出现
error_value_is_not_array = f"""{{"LeaveForActionComponent": "悠扬林谷"}}"""


##{'老猎人隐居的小木屋': ['卡斯帕·艾伦德', '断剑', '坏运气先生'], '悠扬林谷': ['无名旅人'], '地下城': ['暗影巨龙']}

## 运行中的测试系统, 空的混沌工程系统
class ChaosBuddingWorld(IChaosEngineering):
    
    ##
    def __init__(self, name: str) -> None:
        self.name: str = name
        self.on_stage_system_excute_count = 0
        self.on_npc_system_excute_count = 0

    ##
    def on_pre_create_world(self, extended_context: Any, worlddata: WorldDataBuilder) -> None:
        logger.warning(f" {self.name}: on_pre_create_world")

    ##
    def on_post_create_world(self, extended_context: Any, worlddata: WorldDataBuilder) -> None:
        logger.warning(f" {self.name}: on_post_create_world")
    
    ##
    def on_read_memory_failed(self, extended_context: Any, name: str, readarchprompt: str) -> None:
        from auxiliary.extended_context import ExtendedContext
        context: ExtendedContext = extended_context
        #logger.error(f"{self.name}: on_read_memory_failed {name} = {readarchprompt}")
        agent_connect_system = context.agent_connect_system
        agent_connect_system._add_human_message_to_chat_history_(name, readarchprompt)
        agent_connect_system._add_ai_message_to_chat_history_(name, f"确认回忆")

    ##
    def on_stage_planning_system_excute(self, extended_context: Any) -> None:
        #logger.debug(f"{self.name}: on_stage_planning_system_excute")
        self.on_stage_system_excute_count += 1

    ##
    def on_npc_planning_system_execute(self, extended_context: Any) -> None:
        #logger.debug(f"{self.name}: on_npc_planning_system_execute")
        self.on_npc_system_excute_count += 1

    ##
    def hack_stage_planning(self, extended_context: Any, stagename: str, planprompt: str) -> Optional[str]:
        from auxiliary.extended_context import ExtendedContext
        #logger.debug(f"{self.name}: hack_stage_planning {stagename} {planprompt}")
        context: ExtendedContext = extended_context

        ### 测试代码，故意返回错误的格式，并填入chat_history
        if stagename == "悠扬林谷" or stagename == "老猎人隐居的小木屋" or stagename == "地下城":
            agent_connect_system = context.agent_connect_system
            agent_connect_system._add_human_message_to_chat_history_(stagename, planprompt)
            agent_connect_system._add_ai_message_to_chat_history_(stagename, error_repeat)
            return error_repeat

        return None

    ##
    def hack_npc_planning(self, extended_context: Any, npcname: str, planprompt: str) -> Optional[str]:
        from auxiliary.extended_context import ExtendedContext
        #logger.debug(f"{self.name}: hack_npc_planning {npcname} {planprompt}")
        context: ExtendedContext = extended_context

        ##{'老猎人隐居的小木屋': ['卡斯帕·艾伦德', '断剑', '坏运气先生'], '悠扬林谷': ['无名旅人'], '地下城': ['暗影巨龙']}

        ### 测试代码，故意返回错误的格式，并填入chat_history
        if npcname == "坏运气先生":
            agent_connect_system = context.agent_connect_system
            agent_connect_system._add_human_message_to_chat_history_(npcname, planprompt)
            agent_connect_system._add_ai_message_to_chat_history_(npcname, error_extra_string_added)
            return error_extra_string_added
        elif npcname == "卡斯帕·艾伦德":
            agent_connect_system = context.agent_connect_system
            agent_connect_system._add_human_message_to_chat_history_(npcname, planprompt)
            agent_connect_system._add_ai_message_to_chat_history_(npcname, error_speak_format)
            return error_speak_format
        elif npcname == "断剑":
            agent_connect_system = context.agent_connect_system
            agent_connect_system._add_human_message_to_chat_history_(npcname, planprompt)
            agent_connect_system._add_ai_message_to_chat_history_(npcname, error_value_is_not_array)
            return error_value_is_not_array
        elif npcname == "暗影巨龙":
            agent_connect_system = context.agent_connect_system
            agent_connect_system._add_human_message_to_chat_history_(npcname, planprompt)
            agent_connect_system._add_ai_message_to_chat_history_(npcname, error_speak_target_is_invalid)
            return error_speak_target_is_invalid
        return None