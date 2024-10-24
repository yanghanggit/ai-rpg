from entitas import ExecuteProcessor, Matcher, Entity  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from gameplay_systems.components import (
    StageComponent,
    ActorComponent,
    PlayerComponent,
    GUIDComponent,
    RPGCurrentWeaponComponent,
    RPGCurrentClothesComponent,
    WorldComponent,
)
from typing import Dict, final, override, List, Any
from rpg_game.rpg_game import RPGGame
from my_models.models_def import (
    GameModel,
    ActorInstanceModel,
    PropInstanceModel,
    StageInstanceModel,
    WorldSystemInstanceModel,
)
from extended_systems.files_def import PropFile
from pathlib import Path
from rpg_game.rpg_game_resource import RPGGameResource


@final
class SaveGameResourceSystem(ExecuteProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:

        self._context._langserve_agent_system.dump_chat_histories()

        assert self._game._game_resource is not None
        runtime_model = self._game._game_resource._runtime_model

        # 把save_model改掉，然后重新写入
        runtime_model.save_round = self._game._runtime_game_round
        self._save_players(runtime_model)
        self._save_actors(runtime_model)
        self._save_stages(runtime_model)
        self._save_world_systems(runtime_model)
        self._write_model(runtime_model, self._parse_write_path())

    ############################################################################################################
    def _save_players(self, game_model: GameModel) -> None:

        game_model.players.clear()

        player_entities = self._context.get_group(
            Matcher(all_of=[ActorComponent, PlayerComponent])
        ).entities
        for player_entity in player_entities:
            actor_proxy_model = self._create_actor_proxy_model(player_entity)
            prop_proxy_models = self._create_prop_proxy_model(player_entity)
            actor_proxy_model.props = prop_proxy_models

            game_model.players.append(actor_proxy_model)

    ############################################################################################################
    def _save_actors(self, game_model: GameModel) -> None:

        game_model.actors.clear()

        actor_entities = self._context.get_group(
            Matcher(all_of=[ActorComponent], none_of=[PlayerComponent])
        ).entities
        for actor_entity in actor_entities:
            actor_proxy_model = self._create_actor_proxy_model(actor_entity)
            actor_proxy_model.props = self._create_prop_proxy_model(actor_entity)

            game_model.actors.append(actor_proxy_model)

    ############################################################################################################
    def _create_actor_proxy_model(self, actor_entity: Entity) -> ActorInstanceModel:

        ret = ActorInstanceModel(name="", guid=0, props=[], actor_current_using_prop=[])

        actor_comp = actor_entity.get(ActorComponent)
        ret.name = actor_comp.name

        guid_comp = actor_entity.get(GUIDComponent)
        ret.guid = guid_comp.GUID

        ret.actor_current_using_prop = []

        if actor_entity.has(RPGCurrentWeaponComponent):
            current_weapon_comp = actor_entity.get(RPGCurrentWeaponComponent)
            ret.actor_current_using_prop.append(current_weapon_comp.propname)

        if actor_entity.has(RPGCurrentClothesComponent):
            current_clothes_comp = actor_entity.get(RPGCurrentClothesComponent)
            ret.actor_current_using_prop.append(current_clothes_comp.propname)

        return ret

    ############################################################################################################
    def _create_prop_proxy_model(self, entity: Entity) -> List[PropInstanceModel]:

        ret: List[PropInstanceModel] = []
        safe_name = self._context.safe_get_entity_name(entity)
        prop_files = self._context._file_system.get_files(PropFile, safe_name)

        for prop_file in prop_files:
            new_model = PropInstanceModel(
                name=prop_file.name, guid=prop_file.guid, count=prop_file.count
            )
            ret.append(new_model)

        return ret

    ############################################################################################################
    def _save_stages(self, game_model: GameModel) -> None:

        game_model.stages.clear()

        stage_entities = self._context.get_group(Matcher(StageComponent)).entities
        for stage_entity in stage_entities:

            stage_proxy_model = self._create_stage_proxy_model(stage_entity)
            stage_proxy_model.props = self._create_prop_proxy_model(stage_entity)

            game_model.stages.append(stage_proxy_model)

    ############################################################################################################
    def _create_stage_proxy_model(self, stage_entity: Entity) -> StageInstanceModel:

        ret: StageInstanceModel = StageInstanceModel(
            name="", guid=0, props=[], actors=[]
        )

        stage_comp = stage_entity.get(StageComponent)
        ret.name = stage_comp.name

        guid_comp = stage_entity.get(GUIDComponent)
        ret.guid = guid_comp.GUID

        actor_entities = self._context.get_actors_in_stage(stage_entity)
        for actor_entity in actor_entities:
            data: Dict[str, Any] = {}
            data["name"] = self._context.safe_get_entity_name(actor_entity)
            ret.actors.append(data)

        return ret

    ############################################################################################################
    def _save_world_systems(self, game_model: GameModel) -> None:

        game_model.world_systems.clear()

        world_system_entities = self._context.get_group(
            Matcher(WorldComponent)
        ).entities
        for world_system_entity in world_system_entities:

            new_model = WorldSystemInstanceModel(name="", guid=0)

            world_comp = world_system_entity.get(WorldComponent)
            new_model.name = world_comp.name

            guid_comp = world_system_entity.get(GUIDComponent)
            new_model.guid = guid_comp.GUID

            game_model.world_systems.append(new_model)

    ############################################################################################################
    def _write_model(self, game_model: GameModel, write_path: Path) -> int:

        try:

            dump_json = game_model.model_dump_json()
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
