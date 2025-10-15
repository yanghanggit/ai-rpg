from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher
from ..game_systems.base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    ActorComponent,
    MindVoiceAction,
    MindVoiceEvent,
)


####################################################################################################################################
@final
class MindVoiceActionSystem(BaseActionReactiveSystem):

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

        # 生成内心独白事件
        self._game.notify_entities(
            set({entity}),
            MindVoiceEvent(
                message=f"# 发生事件！{mind_voice_action.name} 的内心独白: {mind_voice_action.message}",
                actor=mind_voice_action.name,
                content=mind_voice_action.message,
            ),
        )

    ####################################################################################################################################
