from entitas import ExecuteProcessor, Matcher, Entity, InitializeProcessor  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from gameplay_systems.components import ActorComponent, StageComponent, KickOffComponent
from typing import Set, final, override, Dict, List
import extended_systems.file_system_helper
from rpg_game.rpg_game import RPGGame
from extended_systems.files_def import ActorArchiveFile, StageArchiveFile
import extended_systems.file_system_helper


@final
class UpdateArchiveSystem(InitializeProcessor, ExecuteProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    @override
    def initialize(self) -> None:
        all_actor_names = self.get_all_actor_names()
        all_stage_names = self.get_all_stage_names()
        self.add_kick_off_actor_archive_files(all_actor_names)
        self.add_kick_off_archive_files(all_stage_names)

    ###############################################################################################################################################
    @override
    def execute(self) -> None:
        self.add_archive_to_actors()
        self.update_appearance_of_all_actor_archives()

    ###############################################################################################################################################
    def update_appearance_of_all_actor_archives(self) -> None:

        stage_entities: Set[Entity] = self._context.get_group(
            Matcher(all_of=[StageComponent])
        ).entities

        for stage_entity in stage_entities:
            actor_entities = self._context.get_actors_in_stage(stage_entity)
            if len(actor_entities) == 0:
                continue
            appearance_info = self._context.get_appearance_in_stage(stage_entity)
            for actor_entity in actor_entities:
                self.update_actor_appearance_of_archive(actor_entity, appearance_info)

    ###############################################################################################################################################
    def update_actor_appearance_of_archive(
        self, actor_entity: Entity, appearance_info: Dict[str, str]
    ) -> None:

        my_name = self._context.safe_get_entity_name(actor_entity)
        for actor_name, actor_appearance in appearance_info.items():
            if actor_name == my_name:
                continue

            if not self._context._file_system.has_file(
                ActorArchiveFile, my_name, actor_name
            ):
                extended_systems.file_system_helper.add_actor_archive_files(
                    self._context._file_system, my_name, set({actor_name})
                )

            actor_archive = self._context._file_system.get_file(
                ActorArchiveFile, my_name, actor_name
            )
            assert actor_archive is not None
            if actor_archive.appearance != actor_appearance:
                actor_archive.set_appearance(actor_appearance)
                self._context._file_system.write_file(actor_archive)

    ###############################################################################################################################################
    def add_archive_to_actors(self) -> None:

        all_actor_names = self.get_all_actor_names()
        all_stage_names = self.get_all_stage_names()

        actor_entities: Set[Entity] = self._context.get_group(
            Matcher(all_of=[ActorComponent])
        ).entities

        for actor_entity in actor_entities:

            messages = self._context.get_round_messages(actor_entity)
            if len(messages) == 0:
                continue
            batch_content = " ".join(messages)
            self.add_actor_archive_files(actor_entity, batch_content, all_actor_names)
            self.add_stage_archive_files(actor_entity, batch_content, all_stage_names)

    ###############################################################################################################################################
    def add_actor_archive_files(
        self,
        entity: Entity,
        messages: str,
        optional_range_actor_names: Set[str] = set(),
    ) -> Dict[str, List[ActorArchiveFile]]:
        ret: Dict[str, List[ActorArchiveFile]] = {}

        safe_name = self._context.safe_get_entity_name(entity)
        for archive_actor_name in optional_range_actor_names:

            if safe_name == archive_actor_name:
                continue

            if archive_actor_name not in messages:
                continue

            add_archives = extended_systems.file_system_helper.add_actor_archive_files(
                self._context._file_system, safe_name, {archive_actor_name}
            )

            if len(add_archives) > 0:
                ret[safe_name] = add_archives

        return ret

    ###############################################################################################################################################
    def add_stage_archive_files(
        self,
        entity: Entity,
        messages: str,
        optional_range_stage_names: Set[str] = set(),
    ) -> Dict[str, List[StageArchiveFile]]:
        ret: Dict[str, List[StageArchiveFile]] = {}

        safe_name = self._context.safe_get_entity_name(entity)
        for archive_stage_name in optional_range_stage_names:

            if safe_name == archive_stage_name:
                continue

            if archive_stage_name not in messages:
                continue

            add_archives = extended_systems.file_system_helper.add_stage_archive_files(
                self._context._file_system, safe_name, {archive_stage_name}
            )

            if len(add_archives) > 0:
                ret[safe_name] = add_archives

        return ret

    ###############################################################################################################################################
    def get_all_actor_names(self) -> Set[str]:
        actor_entities: Set[Entity] = self._context.get_group(
            Matcher(all_of=[ActorComponent])
        ).entities
        return {
            actor_entity.get(ActorComponent).name for actor_entity in actor_entities
        }

    ###############################################################################################################################################
    def get_all_stage_names(self) -> Set[str]:
        stage_entities: Set[Entity] = self._context.get_group(
            Matcher(all_of=[StageComponent])
        ).entities
        return {
            stage_entity.get(StageComponent).name for stage_entity in stage_entities
        }

    ###############################################################################################################################################
    def add_kick_off_actor_archive_files(
        self, optional_range_actor_names: Set[str] = set()
    ) -> Dict[str, List[ActorArchiveFile]]:

        ret: Dict[str, List[ActorArchiveFile]] = {}

        actor_entities: Set[Entity] = self._context.get_group(
            Matcher(all_of=[ActorComponent, KickOffComponent])
        ).entities

        for actor_entity in actor_entities:

            actor_comp = actor_entity.get(ActorComponent)
            kick_off_comp = actor_entity.get(KickOffComponent)

            for archive_actor_name in optional_range_actor_names:
                if archive_actor_name == actor_comp.name:
                    continue

                if archive_actor_name not in kick_off_comp.content:
                    continue

                add_archives = (
                    extended_systems.file_system_helper.add_actor_archive_files(
                        self._context._file_system,
                        actor_comp.name,
                        {archive_actor_name},
                    )
                )

                if len(add_archives) > 0:
                    ret[actor_comp.name] = add_archives

        return ret

    ###############################################################################################################################################
    def add_kick_off_archive_files(
        self, optional_range_stage_names: Set[str] = set()
    ) -> Dict[str, List[StageArchiveFile]]:
        ret: Dict[str, List[StageArchiveFile]] = {}

        actor_entities: Set[Entity] = self._context.get_group(
            Matcher(all_of=[ActorComponent, KickOffComponent])
        ).entities

        for actor_entity in actor_entities:

            actor_comp = actor_entity.get(ActorComponent)
            kick_off_comp = actor_entity.get(KickOffComponent)

            for archive_stage_name in optional_range_stage_names:

                if archive_stage_name == actor_comp.name:
                    continue

                if archive_stage_name not in kick_off_comp.content:
                    continue

                add_archives = (
                    extended_systems.file_system_helper.add_stage_archive_files(
                        self._context._file_system,
                        actor_comp.name,
                        {archive_stage_name},
                    )
                )

                if len(add_archives) > 0:
                    ret[actor_comp.name] = add_archives

        return ret

    ###############################################################################################################################################
