from entitas import ExecuteProcessor, Matcher, Entity, InitializeProcessor  # type: ignore
from game.rpg_game_context import RPGGameContext
from components.components import (
    ActorComponent,
    StageComponent,
    KickOffMessageComponent,
    RoundEventsRecordComponent,
)
from typing import Set, final, override, Dict
import rpg_game_systems.file_system_utils
from game.rpg_game import RPGGame
from extended_systems.archive_file import ActorArchiveFile, StageArchiveFile
import rpg_game_systems.file_system_utils
import rpg_game_systems.stage_entity_utils
from rpg_models.event_models import UpdateArchiveEvent


@final
class UpdateArchiveSystem(InitializeProcessor, ExecuteProcessor):

    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ###############################################################################################################################################
    @override
    def initialize(self) -> None:
        # 对于所有的actor，如果没有档案，就加一个档案
        actor_entities: Set[Entity] = self._context.get_group(
            Matcher(all_of=[ActorComponent, KickOffMessageComponent])
        ).entities
        self._archive_kick_off_actors(actor_entities, self.all_actor_names)
        self._archive_kick_off_stages(actor_entities, self.all_stage_names)

    ###############################################################################################################################################
    @override
    def execute(self) -> None:
        # todo
        actor_names = self.all_actor_names
        stage_names = self.all_stage_names
        # 自己的当前场景如果没有就加一个档案
        self._validate_and_register_archives(actor_names)
        # 从本轮消息中提取出所有的档案
        self._archive_round_events(actor_names, stage_names)
        # 更新必要的档案信息
        self._update_archives()

    ###############################################################################################################################################
    @property
    def all_actor_names(self) -> Set[str]:
        actor_entities: Set[Entity] = self._context.get_group(
            Matcher(all_of=[ActorComponent])
        ).entities
        return {
            actor_entity.get(ActorComponent).name for actor_entity in actor_entities
        }

    ###############################################################################################################################################
    @property
    def all_stage_names(self) -> Set[str]:
        stage_entities: Set[Entity] = self._context.get_group(
            Matcher(all_of=[StageComponent])
        ).entities
        return {
            stage_entity.get(StageComponent).name for stage_entity in stage_entities
        }

    ###############################################################################################################################################
    def _update_archives(self) -> None:

        stage_entities: Set[Entity] = self._context.get_group(
            Matcher(all_of=[StageComponent])
        ).entities

        for s_entity in stage_entities:
            actor_entities = self._context.retrieve_actors_on_stage(s_entity)
            if len(actor_entities) == 0:
                continue

            actor_appearance_mapping = self._context.retrieve_stage_actor_appearance(
                s_entity
            )

            for a_entity in actor_entities:
                self._update_actors_archives(
                    actor_entity=a_entity,
                    stage_entity=s_entity,
                    current_stage_actor_appearance_mapping=actor_appearance_mapping,
                )

    ###############################################################################################################################################
    def _update_actors_archives(
        self,
        actor_entity: Entity,
        stage_entity: Entity,
        current_stage_actor_appearance_mapping: Dict[str, str],
    ) -> None:

        # 更新actor的描述
        my_actor_name = self._context.safe_get_entity_name(actor_entity)
        for (
            other_name,
            other_appearance,
        ) in current_stage_actor_appearance_mapping.items():
            if my_actor_name == other_name:
                # 自己不需要更新自己
                continue

            other_actor_archive = self._context.file_system.get_file(
                ActorArchiveFile, my_actor_name, other_name
            )
            assert other_actor_archive is not None
            if other_actor_archive is None:
                continue

            if other_actor_archive.appearance != other_appearance:
                other_actor_archive.set_appearance(other_appearance)
                self._context.file_system.write_file(other_actor_archive)
                # 这里应该有一个通知
                self._notify_actor_appearance_change(
                    actor_entity, other_name, other_appearance
                )

        # 更新场景的描述
        my_stage_archive = self._context.file_system.get_file(
            StageArchiveFile,
            my_actor_name,
            self._context.safe_get_entity_name(stage_entity),
        )

        assert my_stage_archive is not None
        if my_stage_archive is not None:
            stage_narrate = (
                rpg_game_systems.stage_entity_utils.extract_current_stage_narrative(
                    self._context, stage_entity
                )
            )

            if my_stage_archive.stage_narrate != stage_narrate:
                my_stage_archive.set_stage_narrate(stage_narrate)
                self._context.file_system.write_file(my_stage_archive)
                # 这里应该有一个通知
                self._notify_stage_narrative_change(
                    actor_entity, stage_entity, stage_narrate
                )

    ###############################################################################################################################################
    def _notify_actor_appearance_change(
        self, actor_entity: Entity, other_name: str, other_appearance: str
    ) -> None:

        prompt = f"""# 提示: {other_name} 的外观信息更新:
{other_appearance}"""

        self._context.notify_event(
            set({actor_entity}),
            UpdateArchiveEvent(message=prompt),
        )

    ###############################################################################################################################################
    def _notify_stage_narrative_change(
        self, actor_entity: Entity, stage_entity: Entity, stage_narrate: str
    ) -> None:
        stage_name = self._context.safe_get_entity_name(stage_entity)

        prompt = f"""# 提示: {stage_name} 的场景描述更新:
{stage_narrate}"""

        self._context.notify_event(
            set({actor_entity}),
            UpdateArchiveEvent(message=prompt),
        )

    ###############################################################################################################################################
    def _archive_round_events(
        self, actor_names: Set[str], stage_names: Set[str]
    ) -> None:

        actor_entities: Set[Entity] = self._context.get_group(
            Matcher(all_of=[ActorComponent, RoundEventsRecordComponent])
        ).entities

        for actor_entity in actor_entities:
            round_events_comp = actor_entity.get(RoundEventsRecordComponent)
            round_messages = round_events_comp.events
            if len(round_messages) == 0:
                continue
            compiled_round_messages = " ".join(round_messages)
            self._archive_actor_files(
                actor_entity, compiled_round_messages, actor_names
            )
            self._archive_stage_files(
                actor_entity, compiled_round_messages, stage_names
            )

    ###############################################################################################################################################
    def _validate_and_register_archives(self, actor_names: Set[str]) -> None:

        for actor_name in actor_names:

            actor_entity = self._context.get_actor_entity(actor_name)
            assert actor_entity is not None

            stage_entity = self._context.safe_get_stage_entity(actor_entity)
            assert stage_entity is not None

            stage_name = self._context.safe_get_entity_name(stage_entity)

            # 取保拥有场景的档案
            if not self._context.file_system.has_file(
                StageArchiveFile, actor_name, stage_name
            ):
                rpg_game_systems.file_system_utils.register_stage_archives(
                    self._context.file_system, actor_name, {stage_name}
                )

            # 场景内所有的actor都要有档案
            appearance_mapping = self._context.retrieve_stage_actor_appearance(
                stage_entity
            )

            for other_name, _ in appearance_mapping.items():
                if actor_name == other_name:
                    continue

                if not self._context.file_system.has_file(
                    ActorArchiveFile, actor_name, other_name
                ):
                    rpg_game_systems.file_system_utils.register_actor_archives(
                        self._context.file_system, actor_name, {other_name}
                    )

    ###############################################################################################################################################
    def _archive_actor_files(
        self,
        entity: Entity,
        messages: str,
        candidate_actor_names: Set[str] = set(),
    ) -> None:

        safe_name = self._context.safe_get_entity_name(entity)
        for archive_actor_name in candidate_actor_names:

            if safe_name == archive_actor_name or archive_actor_name not in messages:
                continue

            if self._context.file_system.has_file(
                ActorArchiveFile, safe_name, archive_actor_name
            ):
                continue

            rpg_game_systems.file_system_utils.register_actor_archives(
                self._context.file_system, safe_name, {archive_actor_name}
            )

    ###############################################################################################################################################
    def _archive_stage_files(
        self,
        entity: Entity,
        messages: str,
        candidate_stage_names: Set[str] = set(),
    ) -> None:

        safe_name = self._context.safe_get_entity_name(entity)
        for archive_stage_name in candidate_stage_names:

            if safe_name == archive_stage_name or archive_stage_name not in messages:
                continue

            if self._context.file_system.has_file(
                StageArchiveFile, safe_name, archive_stage_name
            ):
                continue

            rpg_game_systems.file_system_utils.register_stage_archives(
                self._context.file_system, safe_name, {archive_stage_name}
            )

    ###############################################################################################################################################
    def _archive_kick_off_actors(
        self, actor_entities: Set[Entity], actors_to_archive: Set[str]
    ) -> None:

        for actor_entity in actor_entities:

            actor_comp = actor_entity.get(ActorComponent)
            kick_off_comp = actor_entity.get(KickOffMessageComponent)

            for actor_to_archive in actors_to_archive:
                if (
                    actor_to_archive == actor_comp.name
                    or actor_to_archive not in kick_off_comp.content
                ):
                    continue

                if self._context.file_system.has_file(
                    ActorArchiveFile, actor_comp.name, actor_to_archive
                ):
                    continue

                rpg_game_systems.file_system_utils.register_actor_archives(
                    self._context.file_system,
                    actor_comp.name,
                    {actor_to_archive},
                )

    ###############################################################################################################################################
    def _archive_kick_off_stages(
        self, actor_entities: Set[Entity], stages_to_archive: Set[str]
    ) -> None:

        for actor_entity in actor_entities:

            actor_comp = actor_entity.get(ActorComponent)
            kick_off_comp = actor_entity.get(KickOffMessageComponent)

            for stage_to_archive in stages_to_archive:

                if (
                    stage_to_archive == actor_comp.name
                    or stage_to_archive not in kick_off_comp.content
                ):
                    continue

                if self._context.file_system.has_file(
                    StageArchiveFile, actor_comp.name, stage_to_archive
                ):
                    continue

                rpg_game_systems.file_system_utils.register_stage_archives(
                    self._context.file_system,
                    actor_comp.name,
                    {stage_to_archive},
                )

    ###############################################################################################################################################
