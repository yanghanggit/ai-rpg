from typing import final, override
from ..models.components import DeathComponent
from ..entitas import Entity, GroupEvent, Matcher, ReactiveProcessor

# from .base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    WolfKillAction,
    NightKillMarkerComponent,
)
from loguru import logger
from ..game.tcg_game import TCGGame


####################################################################################################################################
@final
class WolfKillActionSystem(ReactiveProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        super().__init__(game_context)
        self._game: TCGGame = game_context

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
        logger.info(
            f"🪓 狼人杀 => {entity.name},击杀时间标记 {self._game._werewolf_game_turn_counter}"
        )

        entity.replace(
            NightKillMarkerComponent,
            entity.name,
            self._game._werewolf_game_turn_counter,
        )
        entity.replace(DeathComponent, entity.name)

    ####################################################################################################################################
