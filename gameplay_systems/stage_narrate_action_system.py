from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from typing import override
from gameplay_systems.action_components import StageNarrateAction
from gameplay_systems.components import StageArchiveComponent
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game import RPGGame


############################################################################################################
class StageNarrateActionSystem(ReactiveProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        super().__init__(context)
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(StageNarrateAction): GroupEvent.ADDED}

    ############################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(StageNarrateAction) and entity.has(StageArchiveComponent)

    ############################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.handle(entity)

    ############################################################################################################
    def handle(self, stage_entity: Entity) -> None:
        stage_narrate_action = stage_entity.get(StageNarrateAction)
        stage_narrate_content = " ".join(stage_narrate_action.values)
        if stage_narrate_content == "":
            return

        stage_archive_comp = stage_entity.get(StageArchiveComponent)
        stage_entity.replace(
            StageArchiveComponent,
            stage_archive_comp.name,
            stage_narrate_content,
            self._game.round,
        )

    ############################################################################################################
