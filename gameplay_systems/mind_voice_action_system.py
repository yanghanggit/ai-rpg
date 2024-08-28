from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from typing import override
from gameplay_systems.action_components import MindVoiceAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game import RPGGame


####################################################################################################
class MindVoiceActionSystem(ReactiveProcessor):
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ####################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(MindVoiceAction): GroupEvent.ADDED}

    ####################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(MindVoiceAction)

    ####################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ####################################################################################################
    def handle(self, entity: Entity) -> None:
        pass


####################################################################################################
