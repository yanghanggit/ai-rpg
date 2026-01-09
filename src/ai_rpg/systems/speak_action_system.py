from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.rpg_entity_manager import InteractionError
from ..models import SpeakAction, SpeakEvent
from ..game.tcg_game import TCGGame


####################################################################################################################################
def _format_speak_notification(
    speaker_name: str, target_name: str, content: str
) -> str:
    return f"""# 通知！{speaker_name} 对 {target_name} 说: {content}"""


####################################################################################################################################
def _format_invalid_target_error(speaker_name: str, target_name: str) -> str:
    return f"""# 提示！{speaker_name} 试图对话，但 {target_name} 不在此处。

**提示：** 检查目标名称是否正确，或确认目标是否在当前场景中。"""


####################################################################################################################################


@final
class SpeakActionSystem(ReactiveProcessor):
    """角色说话动作系统。

    响应式处理器，监听 SpeakAction 组件触发，验证对话目标的有效性，
    并将对话事件广播到当前场景内的所有角色。

    功能特点：
    - 验证对话目标是否存在于当前场景
    - 目标有效时广播 SpeakEvent 到当前场景所有角色
    - 目标无效时向发起者添加错误提示消息
    - 适用于场景内公开对话交流

    广播范围：当前场景内所有角色（公开）

    Attributes:
        _game: 游戏实例引用
    """

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: TCGGame = game_context

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
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_speak_action(entity)

    ####################################################################################################################################
    def _process_speak_action(self, entity: Entity) -> None:
        """处理实体的对话动作。

        该方法负责处理一个实体的对话动作，包括验证对话目标的合法性，
        在目标有效时广播对话事件，在目标无效时添加错误提示消息。

        处理流程：
        1. 获取实体的 SpeakAction 组件
        2. 遍历所有目标及其对话内容
        3. 验证每个目标的交互合法性
        4. 如果目标不存在，添加错误提示消息并跳过该目标
        5. 如果目标有效，广播 SpeakEvent 到游戏舞台

        Args:
            entity: 包含 SpeakAction 组件的游戏实体，代表发起对话的角色

        Returns:
            None

        Note:
            - 该方法会处理 SpeakAction 中的所有目标消息
            - 对于无效目标，会通过 append_human_message 添加提示
            - 对于有效目标，会通过 broadcast_to_stage 广播事件
        """
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
