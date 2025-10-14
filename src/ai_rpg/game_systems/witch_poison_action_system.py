from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher
from .base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    WitchPoisonAction,
)
from loguru import logger


####################################################################################################################################
@final
class WitchPoisonActionSystem(BaseActionReactiveSystem):

    ####################################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(WitchPoisonAction): GroupEvent.ADDED}

    ####################################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(WitchPoisonAction)

    ####################################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_action(entity)

    ####################################################################################################################################
    def _process_action(self, entity: Entity) -> None:
        logger.debug(f"🧪 处理女巫毒杀行动 = {entity.name}")

    ####################################################################################################################################
