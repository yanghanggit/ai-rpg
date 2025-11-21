"""耳语动作系统模块。

该模块实现了游戏中角色之间的私密耳语交互系统，负责处理和验证耳语动作，
确保耳语仅在发起者和目标之间传递，其他角色无法得知耳语内容。

主要功能：
- 验证耳语目标的有效性（目标是否存在于当前场景）
- 格式化耳语通知消息和错误提示消息
- 实现私密通信机制（仅通知发起者和目标，其他角色不知道）
- 处理耳语失败的各种情况并提供反馈
- 与普通对话(SpeakAction)的区别在于耳语的私密性
"""

from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor
from ..game.rpg_entity_manager import InteractionValidationResult
from ..models import WhisperAction, WhisperEvent
from ..game.tcg_game import TCGGame


####################################################################################################################################
def _format_whisper_notification(
    speaker_name: str, target_name: str, content: str
) -> str:
    return f"# 通知！{speaker_name} 对 {target_name} 耳语道: {content}"


####################################################################################################################################
def _format_invalid_target_error(speaker_name: str, target_name: str) -> str:
    return f"""# 提示！{speaker_name} 试图对话，但 {target_name} 不在此处。

**提示：** 检查目标名称是否正确，或确认目标是否在当前场景中。"""


####################################################################################################################################


@final
class WhisperActionSystem(ReactiveProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: TCGGame = game_context

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
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_whisper_action(entity)

    ####################################################################################################################################
    def _process_whisper_action(self, entity: Entity) -> None:
        """处理实体的耳语动作。

        该方法负责处理一个实体的耳语动作，包括验证耳语目标的合法性，
        在目标有效时仅向发起者和目标发送耳语事件（保持私密性），
        在目标无效时添加错误提示消息。

        处理流程：
        1. 获取实体的 WhisperAction 组件
        2. 遍历所有目标及其耳语内容
        3. 验证每个目标的交互合法性
        4. 如果目标不存在，添加错误提示消息并跳过该目标
        5. 如果目标有效，获取目标实体
        6. 仅向发起者和目标双方发送 WhisperEvent（私密通信）

        Args:
            entity: 包含 WhisperAction 组件的游戏实体，代表发起耳语的角色

        Returns:
            None

        Note:
            - 该方法会处理 WhisperAction 中的所有目标消息
            - 对于无效目标，会通过 append_human_message 添加提示
            - 对于有效目标，会通过 notify_entities 仅通知双方（私密性保证）
            - 与 SpeakActionSystem 的区别：耳语不会广播到整个舞台，只通知双方
            - 目标实体必须存在且可访问，否则会记录错误
        """
        whisper_action = entity.get(WhisperAction)

        for target_name, whisper_content in whisper_action.target_messages.items():
            # 判断可交互性
            error = self._game.validate_interaction(entity, target_name)
            if error != InteractionValidationResult.SUCCESS:

                # 处理交互错误
                if error == InteractionValidationResult.TARGET_NOT_FOUND:

                    # 记录在上下文里！
                    self._game.append_human_message(
                        entity=entity,
                        message_content=_format_invalid_target_error(
                            whisper_action.name, target_name
                        ),
                    )
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
