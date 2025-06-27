from ..entitas import Entity, Matcher, GroupEvent
from typing import final, override
from ..tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
from ..models import AgentEvent, WhisperEvent, WhisperAction
from ..game.tcg_game import ConversationError


####################################################################################################################################
def _generate_prompt(speaker_name: str, target_name: str, content: str) -> str:
    return f"# 发生事件: {speaker_name} 对 {target_name} 耳语道: {content}"


####################################################################################################################################
def _generate_invalid_prompt(speaker_name: str, target_name: str) -> str:
    return f"""# 提示: {speaker_name} 试图和一个不存在的目标 {target_name} 进行对话。
## 原因分析与建议
- 请检查目标的全名: {target_name}。
- 请检查目标是否存在于当前场景中。"""


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
            self._prosses_action(entity)

    ####################################################################################################################################
    def _prosses_action(self, entity: Entity) -> None:
        stage_entity = self._game.safe_get_stage_entity(entity)
        if stage_entity is None:
            return

        whisper_action = entity.get(WhisperAction)

        for target_name, whisper_content in whisper_action.data.items():

            error = self._game.validate_conversation(entity, target_name)
            if error != ConversationError.VALID:
                if error == ConversationError.INVALID_TARGET:
                    self._game.notify_event(
                        set({entity}),
                        AgentEvent(
                            message=_generate_invalid_prompt(
                                whisper_action.name, target_name
                            )
                        ),
                    )
                continue

            # 通知双方，其余人不知道
            target_entity = self._game.get_entity_by_name(target_name)
            assert target_entity is not None
            self._game.notify_event(
                set({entity, target_entity}),
                WhisperEvent(
                    message=_generate_prompt(
                        whisper_action.name, target_name, whisper_content
                    ),
                    speaker=whisper_action.name,
                    listener=target_name,
                    dialogue=whisper_content,
                ),
            )

    ####################################################################################################################################
