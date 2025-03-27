from entitas import Entity, Matcher, GroupEvent  # type: ignore
from typing import final, override
from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem
from models.event_models import AgentEvent, SpeakEvent
from game.tcg_game import ConversationError
from components.actions_v_0_0_1 import SpeakAction


####################################################################################################################################
def _generate_prompt(speaker_name: str, target_name: str, content: str) -> str:
    return f"# 发生事件: {speaker_name} 对 {target_name} 说: {content}"


####################################################################################################################################
def _generate_invalid_prompt(speaker_name: str, target_name: str) -> str:
    return f"""# 提示: {speaker_name} 试图和一个不存在的目标 {target_name} 进行对话。
## 原因分析与建议
- 请检查目标的全名: {target_name}。
- 请检查目标是否存在于当前场景中。"""


####################################################################################################################################


@final
class SpeakActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SpeakAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(SpeakAction)

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

        speak_action = entity.get(SpeakAction)

        for target_name, speak_content in speak_action.data.items():

            error = self._game.validate_conversation(entity, target_name)
            if error != ConversationError.VALID:
                if error == ConversationError.INVALID_TARGET:
                    self._game.notify_event(
                        set({entity}),
                        AgentEvent(
                            message=_generate_invalid_prompt(
                                speak_action.name, target_name
                            )
                        ),
                    )
                continue

            assert self._game.get_entity_by_name(target_name) is not None
            self._game.broadcast_event(
                stage_entity,
                SpeakEvent(
                    message=_generate_prompt(
                        speak_action.name, target_name, speak_content
                    ),
                    speaker=speak_action.name,
                    listener=target_name,
                    dialogue=speak_content,
                ),
            )

    ####################################################################################################################################
