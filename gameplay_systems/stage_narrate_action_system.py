from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
from typing import override
from gameplay_systems.action_components import StageNarrateAction
from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game import RPGGame
from file_system.files_def import StageArchiveFile
import file_system.helper


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
        return entity.has(StageNarrateAction)

    ############################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self.update_stage_archive(entity)

    ############################################################################################################
    def update_stage_archive(self, stage_entity: Entity) -> None:
        stage_narrate_action = stage_entity.get(StageNarrateAction)
        if len(stage_narrate_action.values) == 0:
            return

        stage_narrate_content = " ".join(stage_narrate_action.values)
        actor_entities = self._context.get_actors_in_stage(stage_entity)
        for actor_entity in actor_entities:

            actor_name = self._context.safe_get_entity_name(actor_entity)

            if not self._context._file_system.has_file(
                StageArchiveFile, actor_name, stage_narrate_action.name
            ):
                # 保证必须有
                file_system.helper.add_stage_archive_files(
                    self._context._file_system,
                    actor_name,
                    set({stage_narrate_action.name}),
                )

            stage_archive = self._context._file_system.get_file(
                StageArchiveFile, actor_name, stage_narrate_action.name
            )

            assert stage_archive is not None
            if stage_archive._stage_narrate != stage_narrate_content:
                stage_archive._stage_narrate = stage_narrate_content
                self._context._file_system.write_file(stage_archive)

    ############################################################################################################

    ############################################################################################################
