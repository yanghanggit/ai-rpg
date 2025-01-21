from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from components.actions import SpeakAction
from game.rpg_game_context import RPGGameContext
import rpg_game_systems.action_component_utils
from typing import final, override
import format_string.target_message
from game.rpg_game import RPGGame
from models.event_models import SpeakEvent, AgentEvent


####################################################################################################################################
def _generate_speak_prompt(speaker_name: str, target_name: str, content: str) -> str:
    return f"# 发生事件: {speaker_name} 对 {target_name} 说: {content}"


####################################################################################################################################
def _generate_invalid_speak_target_prompt(speaker_name: str, target_name: str) -> str:
    return f"""# 提示: {speaker_name} 试图和一个不存在的目标 {target_name} 进行对话。
## 原因分析与建议
- 请检查目标的全名: {target_name}，确保是完整匹配:游戏规则-全名机制
- 请检查目标是否存在于当前场景中。"""


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################


####################################################################################################################################
@final
class SpeakActionSystem(ReactiveProcessor):
    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

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
            self._process_speak_action(entity)

    ####################################################################################################################################
    def _process_speak_action(self, entity: Entity) -> None:

        speak_action = entity.get(SpeakAction)
        target_and_message = format_string.target_message.extract_target_message_pairs(
            speak_action.values
        )

        for target_name, message in target_and_message:

            # 关键的检查
            error = rpg_game_systems.action_component_utils.validate_conversation(
                self._context, entity, target_name
            )
            if error != rpg_game_systems.action_component_utils.ConversationError.VALID:

                if (
                    error
                    == rpg_game_systems.action_component_utils.ConversationError.INVALID_TARGET
                ):
                    self._context.notify_event(
                        set({entity}),
                        AgentEvent(
                            message=_generate_invalid_speak_target_prompt(
                                speak_action.name, target_name
                            ),
                        ),
                    )

                # 总之就是不对，不会继续执行。
                continue

            # 正式的对话
            assert self._context.get_entity_by_name(target_name) is not None
            self._context.broadcast_event(
                entity,
                SpeakEvent(
                    message=_generate_speak_prompt(
                        speak_action.name, target_name, message
                    ),
                    speaker_name=speak_action.name,
                    target_name=target_name,
                    content=message,
                ),
            )


####################################################################################################################################
