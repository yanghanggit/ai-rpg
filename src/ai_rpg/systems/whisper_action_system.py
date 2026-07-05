from typing import final, override, Dict, List
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.rpg_entity_manager import InteractionError
from ..models import HumanMessage, WhisperAction, WhisperEvent
from ..game.dbg_game import DBGGame


####################################################################################################################################
def _format_whisper_notification(
    speaker_name: str, target_name: str, content: str
) -> str:
    return f"# {speaker_name} 对 {target_name} 耳语道: {content}"


####################################################################################################################################
def _format_invalid_target_error(speaker_name: str, target_name: str) -> str:
    return f"""# 提示！{speaker_name} 试图对话，但 {target_name} 不在此处。

**提示：** 检查目标名称是否正确，或确认目标是否在当前场景中。"""


####################################################################################################################################


@final
class WhisperActionSystem(ReactiveProcessor):
    """角色耳语动作系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: DBGGame = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(WhisperAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(WhisperAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in entities:
            self._process_whisper_action(entity)

    ####################################################################################################################################
    def _process_whisper_action(self, entity: Entity) -> None:
        """处理实体的耳语动作。"""

        whisper_action = entity.get(WhisperAction)

        for target_name, whisper_content in whisper_action.target_messages.items():

            # 判断可交互性
            error = self._game.validate_actor_interaction(entity, target_name)
            if error != InteractionError.NONE:

                # 处理交互错误
                if error == InteractionError.TARGET_NOT_FOUND:

                    # 记录在上下文里！
                    self._game.add_human_message(
                        entity=entity,
                        human_message=HumanMessage(
                            content=_format_invalid_target_error(
                                whisper_action.name, target_name
                            )
                        ),
                    )
                continue

            # 目标存在，广播耳语事件
            if whisper_content is None or whisper_content.strip() == "":
                # 空内容，跳过
                continue

            # 通知双方，其余人不知道
            target_entity = self._game.get_entity_by_name(target_name)
            assert target_entity is not None, "前面过了这里必然能找到!"

            # 注意！仅通知双方，其余人不知道
            self._game.notify_entities(
                set({entity, target_entity}),
                WhisperEvent(
                    message=_format_whisper_notification(
                        whisper_action.name, target_name, whisper_content
                    ),
                    actor=whisper_action.name,
                    target=target_name,
                    content=whisper_content,
                ),
            )

    ####################################################################################################################################
