from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher
from ..game_systems.base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    ActorComponent,
    MindVoiceAction,
    MindVoiceEvent,
)
from .query_action import get_query_service
from loguru import logger
from ..game.tcg_game import TCGGame


####################################################################################################################################
@final
class MindVoiceActionSystem(BaseActionReactiveSystem):
    """内心独白行动系统 - 处理角色的内心想法，并支持RAG查询增强"""

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._query_service = get_query_service()

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(MindVoiceAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(MindVoiceAction) and entity.has(ActorComponent)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_action(entity)

    ####################################################################################################################################
    def _process_action(self, entity: Entity) -> None:
        """处理内心独白行动"""
        mind_voice_action = entity.get(MindVoiceAction)
        assert mind_voice_action is not None

        # 使用查询服务获取相关信息
        related_info = self._query_service.query(mind_voice_action.message)
        logger.debug(f"💭 内心独白查询结果: {related_info}")

        # 如果有相关信息，指导AI将信息融入到后续对话中
        if related_info:
            self._game.append_human_message(
                entity,
                f"基于以下背景信息回答问题：\n{related_info}\n\n选择你认为最合适的信息出来作为参考来回答问题。",
            )
        else:
            self._game.append_human_message(
                entity,
                "没有找到相关背景信息。在接下来的对话中，如果涉及没有找到的或者不在你的上下文中的内容，请诚实地表示不知道，不要编造。",
            )

        # 生成内心独白事件
        self._game.notify_event(
            set({entity}),
            MindVoiceEvent(
                message=f"# 发生事件！{mind_voice_action.name} 的内心独白: {mind_voice_action.message}",
                actor=mind_voice_action.name,
                content=mind_voice_action.message,
            ),
        )

        logger.debug(f"💭 处理内心独白: {mind_voice_action.name} - {mind_voice_action.message}")

    ####################################################################################################################################
