from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher
from .base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    SeerCheckAction,
)
from loguru import logger


####################################################################################################################################
@final
class SeerCheckActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(SeerCheckAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(SeerCheckAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_action(entity)

    ####################################################################################################################################
    def _process_action(self, entity: Entity) -> None:
        logger.debug(f"🔮 处理预言家查验行动 = {entity.name}")

    ####################################################################################################################################
