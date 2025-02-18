from entitas import Entity, Matcher, GroupEvent  # type: ignore
from components.actions import (
    WhisperAction,
)
from typing import final, override
from tcg_game_systems.base_action_reactive_system import (
    BaseActionReactiveSystem,
    ConversationError,
)
import format_string.target_message
from models.event_models import AgentEvent, WhisperEvent

####################################################################################################################################
@final
class WhisperActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(WhisperAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(WhisperAction)

    ####################################################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._prosses_whisper_action(entity)

    ####################################################################################################################################
    def _prosses_whisper_action(self, entity: Entity) -> None:
        stage_entity = self._context.safe_get_stage_entity(entity)
        if stage_entity is None:
            return
        
        whisper_action = entity.get(WhisperAction)
        target_and_message = format_string.target_message.extract_target_message_pairs(
            whisper_action.values
        )

        for target_name, message in target_and_message:

            error = self.validate_conversation(entity, target_name)
            if error != ConversationError.VALID:
                if error == ConversationError.INVALID_TARGET:
                    self._game.notify_event(
                        set({entity}),
                        AgentEvent(
                            message=_generate_invalid_speak_target_prompt(
                                whisper_action.name, target_name
                            )
                        ),
                    )
                continue

            assert self._context.get_entity_by_name(target_name) is not None
            self._game.notify_event(
                set({entity}),
                WhisperEvent(
                    message=_generate_speak_prompt(
                        whisper_action.name, target_name, message
                    ),
                    whisperer_name=whisper_action.name,
                    target_name=target_name,
                    content=message,
                ),
            )


    ####################################################################################################################################


def _generate_speak_prompt(speaker_name: str, target_name: str, content: str) -> str:
    return f"# 发生事件: {speaker_name} 对 {target_name} 私语: {content}"


def _generate_invalid_speak_target_prompt(speaker_name: str, target_name: str) -> str:
    return f"""# 提示: {speaker_name} 试图和一个不存在的目标 {target_name} 进行对话。
## 原因分析与建议
- 请检查目标的全名: {target_name}，确保是完整匹配:游戏规则-全名机制
- 请检查目标是否存在于当前场景中。"""
