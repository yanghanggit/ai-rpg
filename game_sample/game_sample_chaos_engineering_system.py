#
import sys
from pathlib import Path
# 将项目根目录添加到sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
### 
from chaos_engineering.chaos_engineering_system import IChaosEngineering
from loguru import logger
from build_game.game_builders import GameBuilder
from typing import Any, Optional

## 测试重复的json内容，应该是load不出来才对
error_repeat = f"""{{"MindVoiceActionComponent": ["测试的字符串"]}}{{"WhisperActionComponent": ["测试的字符串"]}}"""

## 有额外的字符串
error_extra_string_added = f"""{{"GoToActionComponent": ["禁言铁棺"]}}一个测试的字符串，不应该出现在这里"""

## SpeakActionComponent的格式，value格式就不对。应该是"@目标名字>对话内容"
error_speak_format = f"""{{"SpeakActionComponent": ["这是一个错误的格式"]}}"""
error_speak_target_is_invalid = f"""{{"SpeakActionComponent": ["@教宗>你在读书吗？？"]}}"""

## value必须以[]形式出现
error_value_is_not_array = f"""{{"GoToActionComponent": "禁言铁棺"}}"""

## 运行中的测试系统, 空的混沌工程系统 my_chaos_engineering_system
class GameSampleChaosEngineeringSystem(IChaosEngineering):

    ##
    def __init__(self, name: str) -> None:
        self.name: str = name
        self.on_stage_system_excute_count = 0
        self.on_actor_system_excute_count = 0

    ##
    def on_pre_create_game(self, extended_context: Any, worlddata: GameBuilder) -> None:
        logger.warning(f" {self.name}: on_pre_create_world")

    ##
    def on_post_create_game(self, extended_context: Any, worlddata: GameBuilder) -> None:
        logger.warning(f" {self.name}: on_post_create_world")
    
    ##
    def on_read_memory_failed(self, extended_context: Any, name: str, readarchprompt: str) -> None:
        logger.debug(f"{self.name}: on_read_memory_failed {name} {readarchprompt}")
        from my_entitas.extended_context import ExtendedContext
        context: ExtendedContext = extended_context
        agent_connect_system = context.agent_connect_system
        agent_connect_system.add_human_message_to_chat_history(name, readarchprompt)
        agent_connect_system.add_ai_message_to_chat_history(name, f"尝试着确认回忆")

    ##
    def on_stage_planning_system_excute(self, extended_context: Any) -> None:
        self.on_stage_system_excute_count += 1

    ##
    def on_actor_planning_system_execute(self, extended_context: Any) -> None:
        self.on_actor_system_excute_count += 1

    ##
    def hack_stage_planning(self, extended_context: Any, stagename: str, planprompt: str) -> Optional[str]:
        from my_entitas.extended_context import ExtendedContext
        context: ExtendedContext = extended_context
        return None

    ##
    def hack_actor_planning(self, extended_context: Any, actor_name: str, planprompt: str) -> Optional[str]:
        from my_entitas.extended_context import ExtendedContext
        context: ExtendedContext = extended_context
        return None