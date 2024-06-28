from typing import Any, Set, cast
from loguru import logger
from prototype_data.data_def import PropData, ActorData, StageData, WorldSystemData, Attributes
from prototype_data.data_base_system import DataBaseSystem
from pathlib import Path
from build_game.stage_builder import StageBuilder
from build_game.actor_builder import ActorBuilder
from build_game.world_system_builder import WorldSystemBuilder

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
        self._runtime_dir: Path = runtime_file_dir
        assert self._runtime_dir is not None
        assert self._runtime_dir.exists()

        # 先全部给空的，就是临时创建出来
        self._world_system_builder: WorldSystemBuilder = WorldSystemBuilder()
        self._player_builder: ActorBuilder = ActorBuilder()
        self._actor_buidler: ActorBuilder = ActorBuilder()
        self._stage_builder: StageBuilder = StageBuilder()
        self._data_base_system: DataBaseSystem = DataBaseSystem("") # 空的
###############################################################################################################################################
    @property
    def version(self) -> str:
        if self._raw_data is None:
            logger.error("WorldDataBuilder: data is None.")
            return ""
        return cast(str, self._raw_data.get('version', ""))  
###############################################################################################################################################
    @property
    def about_game(self) -> str:
        if self._raw_data is None:
            assert False, "WorldDataBuilder: data is None."
            return "?"
        return str(self._raw_data.get('about_game', "无关于游戏的信息。"))
###############################################################################################################################################
    def build(self) -> 'GameBuilder':
        if self._raw_data is None:
            logger.error("WorldDataBuilder: data is None.")
            return self
        
        raw_data = self._raw_data
        assert raw_data is not None
        # 第一步，创建数据库
        database = raw_data.get('database', None)
        if database is None:
            assert False, "没有数据库(database)，请检查World.json配置。"
            return
        
        # 常量
        name_of_actor_data_block = "actors"
        name_of_player_data_block = "players"
        name_of_stage_data_block = "stages"
        name_of_prop_data_block = "props"
        name_of_world_system_data_block = "world_systems"

        # 创建数据库，添加数据，直接盖掉。        
        db_system = self._data_base_system = DataBaseSystem("data_base_system，it is a system that stores all the origin data from the settings.")
        self._add_actors_2_db(database.get(name_of_actor_data_block, None), db_system)
        self._add_stages_2_db(database.get(name_of_stage_data_block, None), db_system)
        self._add_props_2_db(database.get(name_of_prop_data_block, None), db_system)
        self._add_world_systems_2_db(database.get(name_of_world_system_data_block, None), db_system)

        # 第三步，创建世界级别的管理员
        self._world_system_builder.build(name_of_world_system_data_block, raw_data, db_system)
        
        # 第四步，创建玩家与Actor
        self._player_builder.build(name_of_player_data_block, raw_data, db_system)
        self._actor_buidler.build(name_of_actor_data_block, raw_data, db_system)
        
        # 第五步，创建场景
        self._stage_builder.build(name_of_stage_data_block, raw_data, db_system)

        # 返回自己
        return self
###############################################################################################################################################
    def _add_actors_2_db(self, actors: Any, data_base_system: DataBaseSystem) -> None:
        if actors is None:
            logger.error("没有Actor数据内容，请检查World.json配置。")
            return
        
        for _actor in actors:
            _data = _actor.get('actor', None)
            assert _data is not None

            # 寻找角色关系
            actor_archives: Set[str] = set()
            _actor_archives_str_: str = _data.get("actor_archives")
            if len(_actor_archives_str_) > 0:
                 actor_archives = set(_actor_archives_str_.split(';'))

             # 寻找角色与场景的关系关系
            stage_archives: Set[str] = set()
            _stage_archives_str_: str = _data.get("stage_archives")
            if len(_stage_archives_str_) > 0:
                 stage_archives = set(_stage_archives_str_.split(';'))

            # 创建
            _actor = ActorData(_data.get("name"), 
                          _data.get("codename"), 
                          _data.get("url"), 
                          _data.get("kick_off_memory"), 
                          actor_archives,
                          stage_archives,
                          _data.get("appearance"),
                          _data.get("body"),
                          Attributes(_data.get("attributes")))
            
            data_base_system.add_actor(_actor._name, _actor)
###############################################################################################################################################
    def _add_world_systems_2_db(self, world_systems: Any, data_base_system: DataBaseSystem) -> None:
        if world_systems is None:
            logger.error("没有世界系统数据内容(world_systems)，请检查World.json配置。")
            return
        for _ws_ in world_systems:
            core_data = _ws_.get('world_system', None)
            assert core_data is not None
            _ws_da_ = WorldSystemData(core_data.get("name"), 
                                        core_data.get("codename"), 
                                        core_data.get("url"))
            data_base_system.add_world_system(_ws_da_._name, _ws_da_)
###############################################################################################################################################
    def _add_stages_2_db(self, stages: Any, data_base_system: DataBaseSystem) -> None:
        if stages is None:
            logger.error("没有场景数据内容(stages)，请检查World.json配置。")
            return
        
        for stage in stages:
            #print(stage)
            core_data = stage.get('stage', None)
            assert core_data is not None

            stage = StageData(core_data.get("name"), 
                            core_data.get("codename"), 
                            core_data.get("description"), 
                            core_data.get("url"), 
                            core_data.get("kick_off_memory"), 
                            core_data.get('stage_entry_status'),
                            core_data.get('stage_entry_actor_status'),
                            core_data.get('stage_entry_actor_props'),
                            core_data.get('stage_exit_status'),
                            core_data.get('stage_exit_actor_status'),
                            core_data.get('stage_exit_actor_props'),
                            Attributes(core_data.get("attributes"))
                            )
            
            # 做连接关系 目前仅用名字
            exit_of_portal_and_goto_stagename: str = core_data.get("exit_of_portal")
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
            propname = prop_data.get('name')
            _pd = PropData(
                propname, 
                prop_data.get('codename'), 
                prop_data.get('description'), 
                prop_data.get('isunique'), 
                prop_data.get('type'), 
                Attributes(prop_data.get('attributes')),
                prop_data.get('appearance')
                )
            data_base_system.add_prop(propname, _pd)
###############################################################################################################################################


