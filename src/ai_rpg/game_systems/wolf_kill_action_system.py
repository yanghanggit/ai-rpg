from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher
from .base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    WolfKillAction,
)
from loguru import logger


####################################################################################################################################
@final
class WolfKillActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(WolfKillAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(WolfKillAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_action(entity)

    ####################################################################################################################################
    def _process_action(self, entity: Entity) -> None:
        logger.debug(f"🪓 处理狼人杀人行动 = {entity.name}")

    ####################################################################################################################################
