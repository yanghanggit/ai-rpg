from entitas import ExecuteProcessor, Matcher, Entity  # type: ignore
from game.rpg_game_context import RPGGameContext
from loguru import logger
from components.components import (
    StageComponent,
    ActorComponent,
    PlayerActorFlagComponent,
    GUIDComponent,
    WeaponComponent,
    ClothesComponent,
    WorldSystemComponent,
    StageSpawnerComponent,
)
from typing import final, override, List
from game.rpg_game import RPGGame
from rpg_models.entity_models import (
    GameModel,
    ActorInstanceModel,
    PropInstanceModel,
    StageInstanceModel,
    WorldSystemInstanceModel,
)
from extended_systems.prop_file import PropFile
from pathlib import Path
from game.rpg_game_resource import RPGGameResource


@final
class SaveGameResourceSystem(ExecuteProcessor):

    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:

        self._context.agent_system.dump_chat_histories()

        assert self._game._game_resource is not None
        runtime_model = self._game._game_resource._runtime_model

        # 把runtime_model改掉，然后重新写入
        runtime_model.save_round = self._game.current_round
        self._save_players(runtime_model)
        self._save_actors(runtime_model)
        self._save_stages(runtime_model)
        self._save_world_systems(runtime_model)
        self._write_model(runtime_model, self._parse_write_path())

    ############################################################################################################
    def _save_players(self, runtime_game_model: GameModel) -> None:

        runtime_game_model.players.clear()

        player_entities = self._context.get_group(
            Matcher(all_of=[ActorComponent, PlayerActorFlagComponent, GUIDComponent])
        ).entities
        for player_entity in player_entities:
            runtime_game_model.players.append(
                self._generate_actor_instance_model(player_entity)
            )

    ############################################################################################################
    def _save_actors(self, runtime_game_model: GameModel) -> None:

        runtime_game_model.actors.clear()

        actor_entities = self._context.get_group(
            Matcher(
                all_of=[ActorComponent, GUIDComponent],
                none_of=[PlayerActorFlagComponent],
            )
        ).entities
        for actor_entity in actor_entities:
            runtime_game_model.actors.append(
                self._generate_actor_instance_model(actor_entity)
            )

    ############################################################################################################
    def _save_world_systems(self, runtime_game_model: GameModel) -> None:

        runtime_game_model.world_systems.clear()

        world_system_entities = self._context.get_group(
            Matcher(all_of=[WorldSystemComponent, GUIDComponent])
        ).entities
        for world_system_entity in world_system_entities:

            world_comp = world_system_entity.get(WorldSystemComponent)
            guid_comp = world_system_entity.get(GUIDComponent)
            runtime_game_model.world_systems.append(
                WorldSystemInstanceModel(name=world_comp.name, guid=guid_comp.GUID)
            )

    ############################################################################################################
    def _save_stages(self, runtime_game_model: GameModel) -> None:

        runtime_game_model.stages.clear()

        stage_entities = self._context.get_group(
            Matcher(all_of=[StageComponent, GUIDComponent, StageSpawnerComponent])
        ).entities
        for stage_entity in stage_entities:
            runtime_game_model.stages.append(
                self._generate_stage_instance_model(stage_entity)
            )

    ############################################################################################################
    def _generate_actor_instance_model(
        self, actor_entity: Entity
    ) -> ActorInstanceModel:

        actor_comp = actor_entity.get(ActorComponent)
        guid_comp = actor_entity.get(GUIDComponent)

        ret = ActorInstanceModel(
            name=actor_comp.name,
            guid=guid_comp.GUID,
            props=self._generate_prop_instance_models(actor_entity),
            actor_equipped_props=[],
        )

        if actor_entity.has(WeaponComponent):
            current_weapon_comp = actor_entity.get(WeaponComponent)
            ret.actor_equipped_props.append(current_weapon_comp.prop_name)

        if actor_entity.has(ClothesComponent):
            current_clothes_comp = actor_entity.get(ClothesComponent)
            ret.actor_equipped_props.append(current_clothes_comp.prop_name)

        return ret

    ############################################################################################################
    def _generate_prop_instance_models(self, entity: Entity) -> List[PropInstanceModel]:

        ret: List[PropInstanceModel] = []
        safe_name = self._context.safe_get_entity_name(entity)
        prop_files = self._context.file_system.get_files(PropFile, safe_name)

        for prop_file in prop_files:
            new_model = PropInstanceModel(
                name=prop_file.name, guid=prop_file.guid, count=prop_file.count
            )
            ret.append(new_model)

        return ret

    ############################################################################################################
    def _generate_stage_instance_model(
        self, stage_entity: Entity
    ) -> StageInstanceModel:

        stage_comp = stage_entity.get(StageComponent)
        guid_comp = stage_entity.get(GUIDComponent)
        stage_spawner_comp = stage_entity.get(StageSpawnerComponent)

        ret: StageInstanceModel = StageInstanceModel(
            name=stage_comp.name,
            guid=guid_comp.GUID,
            # props=self._generate_prop_instance_models(stage_entity),
            actors=[],
            spawners=stage_spawner_comp.spawners,
        )

        actor_entities = self._context.retrieve_actors_on_stage(stage_entity)
        for actor_entity in actor_entities:
            ret.actors.append(
                {"name": self._context.safe_get_entity_name(actor_entity)}
            )

        return ret

    ############################################################################################################
    def _write_model(self, runtime_game_model: GameModel, write_path: Path) -> int:
        try:
            dump_json = runtime_game_model.model_dump_json()
            return write_path.write_text(dump_json, encoding="utf-8")
        except Exception as e:
            logger.error(f"写文件失败: {write_path}, e = {e}")
        return -1

    ############################################################################################################
    def _parse_write_path(self) -> Path:
        game_resouce = self._game._game_resource
        assert game_resouce is not None
        assert game_resouce._runtime_dir.exists()
        return game_resouce._runtime_dir / RPGGameResource.generate_runtime_file_name(
            game_resouce._game_name
        )


############################################################################################################
