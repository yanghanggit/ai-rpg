from typing import final, override, Dict, List
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.rpg_entity_manager import InteractionError
from ..models import SpeakAction, SpeakEvent
from ..game.dbg_game import DBGGame


####################################################################################################################################
def _format_speak_notification(
    speaker_name: str, target_name: str, content: str
) -> str:
    return f"""# {speaker_name} 对 {target_name} 说: {content}"""


####################################################################################################################################
def _format_invalid_target_error(speaker_name: str, target_name: str) -> str:
    return f"""# 提示！{speaker_name} 试图对话，但 {target_name} 不在此处。

**提示：** 检查目标名称是否正确，或确认目标是否在当前场景中。"""


####################################################################################################################################


@final
class SpeakActionSystem(ReactiveProcessor):
    """角色说话动作系统。"""

    def __init__(self, game: DBGGame) -> None:
        super().__init__(game)
        self._game: DBGGame = game

    ####################################################################################################################################
    @override
    def get_trigger(self) -> Dict[Matcher, GroupEvent]:
        return {Matcher(SpeakAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(SpeakAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: List[Entity]) -> None:
        for entity in entities:
            self._process_speak_action(entity)

    ####################################################################################################################################
    def _process_speak_action(self, entity: Entity) -> None:
        """处理实体的对话动作。"""
        # 处理对话动作
        speak_action = entity.get(SpeakAction)
        for target_name, speak_content in speak_action.target_messages.items():

            # 验证交互合法性
            error = self._game.validate_actor_interaction(entity, target_name)
            if error != InteractionError.NONE:
                # 目标不存在，添加提示信息
                if error == InteractionError.TARGET_NOT_FOUND:
                    # 添加上下文提示!
                    self._game.add_human_message(
                        entity=entity,
                        message_content=_format_invalid_target_error(
                            speak_action.name, target_name
                        ),
                    )
                continue

            # 目标存在，广播对话事件
            if speak_content is None or speak_content.strip() == "":
                # 空内容，跳过
                continue

            # 广播对话事件
            self._game.broadcast_to_stage(
                entity,
                SpeakEvent(
                    message=_format_speak_notification(
                        speak_action.name, target_name, speak_content
                    ),
                    actor=speak_action.name,
                    target=target_name,
                    content=speak_content,
                ),
            )

    ####################################################################################################################################
