from typing import Any, Set, cast
from loguru import logger
from prototype_data.data_def import PropData, ActorData, StageData, WorldSystemData, Attributes
from prototype_data.data_base_system import DataBaseSystem
from pathlib import Path
from build_game.stage_builder import StageBuilder
from build_game.actor_builder import ActorBuilder
from build_game.world_system_builder import WorldSystemBuilder
from jsonschema import validate, ValidationError
from build_game.game_builder_data_schema import GAME_BUILDER_DATA_SCHEMA

class GameBuilder:

    """
    这是一个分析游戏json的数据的类。
    将游戏数据转换为游戏对象。
    内部管理着WorldSystemBuilder，PlayerBuilder，ActorBuilder，StageBuilder，DataBaseSystem。
    """

    def __init__(self, 
                 name: str, 
                 data: Any,
                 runtime_file_dir: Path) -> None:
        
        self._game_name: str = name
        self._raw_data: Any = data
        assert self._raw_data is not None
        assert self.check_json_jsonschema(self._raw_data, GAME_BUILDER_DATA_SCHEMA)
        self._runtime_dir: Path = runtime_file_dir
        assert self._runtime_dir is not None
        assert self._runtime_dir.exists()

        # 先全部给空的，就是临时创建出来
        self._world_system_builder: WorldSystemBuilder = WorldSystemBuilder()
        self._player_builder: ActorBuilder = ActorBuilder()
        self._actor_buidler: ActorBuilder = ActorBuilder()
        self._stage_builder: StageBuilder = StageBuilder()
        self._data_base_system: DataBaseSystem = DataBaseSystem()
###############################################################################################################################################
    def check_json_jsonschema(self, json_data: Any, _schema: Any) -> bool:
        if json_data is None:
            logger.error("JSON data is None.")
            return False
        try:
            validate(instance = json_data, schema = _schema)
            logger.debug("JSON data is valid.")
            return True
        except ValidationError as e:
            logger.error(f"JSON data is invalid: {e}")
        return False
###############################################################################################################################################
    @property
    def version(self) -> str:
        if self._raw_data is None:
            logger.error("WorldDataBuilder: data is None.")
            return ""
        return cast(str, self._raw_data['version'])  
###############################################################################################################################################
    @property
    def about_game(self) -> str:
        if self._raw_data is None:
            assert False, "WorldDataBuilder: data is None."
            return "?"
        return str(self._raw_data['about_game'])
###############################################################################################################################################
    def build(self) -> 'GameBuilder':

        if self._raw_data is None:
            logger.error("WorldDataBuilder: data is None.")
            return self
        
        try:

            data_base_value = self._raw_data['database']
            if data_base_value is None:
                logger.error("没有数据库(database)，请检查World.json配置。")
                return self
            
            # 常量
            actors_property_name = "actors"
            players_property_name = "players"
            stages_property_name = "stages"
            props_property_name = "props"
            world_systems_property_name = "world_systems"

            # 创建数据库，添加数据，直接盖掉。        
            self._data_base_system = DataBaseSystem()
            self._add_actors_2_db(data_base_value[actors_property_name], self._data_base_system)
            self._add_stages_2_db(data_base_value[stages_property_name], self._data_base_system)
            self._add_props_2_db(data_base_value[props_property_name], self._data_base_system)
            self._add_world_systems_2_db(data_base_value[world_systems_property_name], self._data_base_system)

            # 第三步，从JSON构建世界系统的数据
            self._world_system_builder.build(self._raw_data[world_systems_property_name], self._data_base_system)
            
            # 第四步，从JSON构建玩家与Actor的数据
            self._player_builder.build(self._raw_data[players_property_name], self._data_base_system)
            self._actor_buidler.build(self._raw_data[actors_property_name], self._data_base_system)
            
            # 第五步，从JSON构建场景的数据
            self._stage_builder.build(self._raw_data[stages_property_name], self._data_base_system)

        except KeyError:
            logger.error("Missing 'world_systems', 'players', 'actors' or 'stages' key in world block.")
            return self
    
        # 返回自己
        return self
###############################################################################################################################################
    def _add_actors_2_db(self, actors: Any, data_base_system: DataBaseSystem) -> None:
        if actors is None:
            logger.error("没有Actor数据内容，请检查World.json配置。")
            return
        
        for _actor in actors:
            _data = _actor['actor']
            assert _data is not None

            # 寻找角色关系
            actor_archives: Set[str] = set()
            _actor_archives_str_: str = _data["actor_archives"]
            if len(_actor_archives_str_) > 0:
                 actor_archives = set(_actor_archives_str_.split(';'))

             # 寻找角色与场景的关系关系
            stage_archives: Set[str] = set()
            _stage_archives_str_: str = _data["stage_archives"]
            if len(_stage_archives_str_) > 0:
                 stage_archives = set(_stage_archives_str_.split(';'))

            # 创建
            _actor = ActorData(_data["name"], 
                          _data["codename"], 
                          _data["url"], 
                          _data["kick_off_memory"], 
                          actor_archives,
                          stage_archives,
                          _data["appearance"],
                          _data["body"],
                          Attributes(_data["attributes"]))
            
            data_base_system.add_actor(_actor._name, _actor)
###############################################################################################################################################
    def _add_world_systems_2_db(self, world_systems: Any, data_base_system: DataBaseSystem) -> None:
        if world_systems is None:
            logger.error("没有世界系统数据内容(world_systems)，请检查World.json配置。")
            return
        for _ws_ in world_systems:
            core_data = _ws_['world_system']
            assert core_data is not None
            _ws_da_ = WorldSystemData(core_data["name"], 
                                        core_data["codename"], 
                                        core_data["url"])
            data_base_system.add_world_system(_ws_da_._name, _ws_da_)
###############################################################################################################################################
    def _add_stages_2_db(self, stages: Any, data_base_system: DataBaseSystem) -> None:
        if stages is None:
            logger.error("没有场景数据内容(stages)，请检查World.json配置。")
            return
        
        for stage in stages:
            #print(stage)
            core_data = stage['stage']
            assert core_data is not None

            stage = StageData(core_data["name"], 
                            core_data["codename"], 
                            core_data["description"], 
                            core_data["url"], 
                            core_data["kick_off_memory"], 
                            core_data['stage_entry_status'],
                            core_data['stage_entry_actor_status'],
                            core_data['stage_entry_actor_props'],
                            core_data['stage_exit_status'],
                            core_data['stage_exit_actor_status'],
                            core_data['stage_exit_actor_props'],
                            Attributes(core_data["attributes"])
                            )
            
            # 做连接关系 目前仅用名字
            exit_of_portal_and_goto_stagename: str = core_data["exit_of_portal"]
            if exit_of_portal_and_goto_stagename != "":
                stage.stage_as_exit_of_portal(exit_of_portal_and_goto_stagename)
            else:
                logger.debug(f"Stage {stage._name} has no exit_of_portal.")

            # 添加到数据库
            data_base_system.add_stage(stage._name, stage)
###############################################################################################################################################
    def _add_props_2_db(self, props: Any, data_base_system: DataBaseSystem) -> None:
        if props is None:
            logger.error("没有道具数据内容(props)，请检查World.json配置。")
            return

        for prop_data in props:
            propname = prop_data['name']
            _pd = PropData(
                propname, 
                prop_data['codename'], 
                prop_data['description'], 
                prop_data['isunique'], 
                prop_data['type'], 
                Attributes(prop_data['attributes']),
                prop_data['appearance']
                )
            data_base_system.add_prop(propname, _pd)
###############################################################################################################################################


