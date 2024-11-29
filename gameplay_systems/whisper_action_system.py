from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from components.action_components import WhisperAction
from game.rpg_entitas_context import RPGEntitasContext
from typing import final, override
import gameplay_systems.action_component_utils
import format_string.target_message
from game.rpg_game import RPGGame
from models.event_models import WhisperEvent, AgentEvent


################################################################################################################################################
def _generate_whisper_prompt(
    whisperer_name: str, target_name: str, content: str
) -> str:
    return f"# 发生事件: {whisperer_name} 对 {target_name} 私语: {content}"


####################################################################################################################################
def _generate_invalid_whisper_target_prompt(speaker_name: str, target_name: str) -> str:
    return f"""# 提示: {speaker_name} 试图和一个不存在的目标 {target_name} 进行私语。
## 原因分析与建议
- 请检查目标的全名: {target_name}，确保目标全名是完整匹配:游戏规则-全名机制
- 请检查目标是否存在于当前场景中。"""


####################################################################################################################################
####################################################################################################################################
####################################################################################################################################


####################################################################################################################################
@final
class WhisperActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

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
            self._process_whisper_action(entity)

    ####################################################################################################################################
    def _process_whisper_action(self, entity: Entity) -> None:
        whisper_action = entity.get(WhisperAction)
        target_and_message = format_string.target_message.extract_target_message_pairs(
            whisper_action.values
        )

        for target_name, message in target_and_message:

            # 关键的检查
            error = gameplay_systems.action_component_utils.validate_conversation(
                self._context, entity, target_name
            )
            if error != gameplay_systems.action_component_utils.ConversationError.VALID:

                if (
                    error
                    == gameplay_systems.action_component_utils.ConversationError.INVALID_TARGET
                ):
                    self._context.notify_event(
                        set({entity}),
                        AgentEvent(
                            message=_generate_invalid_whisper_target_prompt(
                                whisper_action.name, target_name
                            )
                        ),
                    )

                # 总之就是不对，不会继续执行。
                continue

            # 正式的执行。
            target_entity = self._context.get_entity_by_name(target_name)
            assert target_entity is not None
            # 注意，只有说话者和目标之间的私语才会被广播
            self._context.notify_event(
                set({entity, target_entity}),
                WhisperEvent(
                    message=_generate_whisper_prompt(
                        whisper_action.name, target_name, message
                    ),
                    whisperer_name=whisper_action.name,
                    target_name=target_name,
                    content=message,
                ),
            )


####################################################################################################################################
