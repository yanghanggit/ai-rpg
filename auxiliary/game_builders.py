from typing import Any, Optional, List, Set, Dict, cast
from loguru import logger
from auxiliary.base_data import PropData, ActorData, StageData, WorldSystemData, ActorDataProxy, PropDataProxy, Attributes
from auxiliary.data_base_system import DataBaseSystem
from pathlib import Path

########################################################################################################################
########################################################################################################################
########################################################################################################################
class GameBuilder:

    def __init__(self, 
                 name: str, 
                 data: Any,
                 runtimepath: str, 
                 data_base_system: DataBaseSystem, 
                 runtime_file_dir: Path) -> None:
        
        self.name = name
        self.runtimepath = runtimepath
        self._data: Any = data
        assert self._data is not None
        self.world_system_builder = WorldSystemBuilder("world_systems")
        self.player_builder = ActorBuilder("players")
        self.actor_buidler = ActorBuilder("actors")
        self.stage_builder = StageBuilder()
        self.data_base_system = data_base_system ## 依赖注入的方式，将数据库系统注入到这里
        self.about_game: str = ""
        self.runtime_dir: Path = runtime_file_dir
###############################################################################################################################################
    @property
    def version(self) -> str:
        if self._data is None:
            logger.error("WorldDataBuilder: data is None.")
            return ""
        return cast(str, self._data.get('version', ""))  
###############################################################################################################################################
    def build(self) -> 'GameBuilder':
        if self._data is None:
            logger.error("WorldDataBuilder: data is None.")
            return self
        # 第一步，创建数据库
        self._create_data_base_system()
        # 第二步，创建配置
        self._build_config(self._data)
        # 第三步，创建世界级别的管理员
        self.world_system_builder.build(self._data, self.data_base_system)
        # 第四步，创建玩家与Actor
        self.player_builder.build(self._data, self.data_base_system)
        self.actor_buidler.build(self._data, self.data_base_system)
        # 第五步，创建场景
        self.stage_builder.build(self._data, self.data_base_system)
        #
        return self
###############################################################################################################################################
    def _build_config(self, data: Dict[str, Any]) -> None:
        self.about_game = data.get('about_game', "无关于游戏的信息。")
###############################################################################################################################################
    def _create_actor_data_base(self, actors: Any) -> None:
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
                          set(), 
                          actor_archives,
                          stage_archives,
                          _data.get("appearance"),
                          _data.get("body"),
                          Attributes(_data.get("attributes")))
            
            self.data_base_system.add_actor(_actor._name, _actor)
###############################################################################################################################################
    def _create_world_system_data_base(self, world_systems: Any) -> None:
        if world_systems is None:
            logger.error("没有世界系统数据内容(world_systems)，请检查World.json配置。")
            return
        for _ws_ in world_systems:
            core_data = _ws_.get('world_system', None)
            assert core_data is not None
            _ws_da_ = WorldSystemData(core_data.get("name"), 
                                        core_data.get("codename"), 
                                        core_data.get("url"))
            self.data_base_system.add_world_system(_ws_da_._name, _ws_da_)
###############################################################################################################################################
    def _create_stage_data_base(self, stages: Any) -> None:
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
                            set(), 
                            set(),
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
            self.data_base_system.add_stage(stage._name, stage)
###############################################################################################################################################
    def _create_prop_data_base(self, props: Any) -> None:
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
                Attributes(prop_data.get('attributes'))
                )
            self.data_base_system.add_prop(propname, _pd)
###############################################################################################################################################
    def _create_data_base_system(self) -> None:
        database = self._data.get('database', None)
        if database is None:
            logger.error("没有数据库(database)，请检查World.json配置。")
            return
        self._create_actor_data_base(database.get('actors', None))
        self._create_stage_data_base(database.get('stages', None))
        self._create_prop_data_base(database.get('props', None))
        self._create_world_system_data_base(database.get('world_systems', None))
########################################################################################################################
class StageBuilder:
    def __init__(self) -> None:
        self.datalist: Optional[Dict[str, Any]] = None
        self.stages: List[StageData] = []

    def __str__(self) -> str:
        return f"StageBuilder: {self.datalist}"      

    def props_proxy_in_stage(self, props_data: List[Any]) -> Set[PropData]:
        res: Set[PropData] = set()
        for obj in props_data:
            prop = PropDataProxy(obj.get("name"))
            res.add(prop)
        return res
    #
    def actors_proxy_in_stage(self, _data: List[Any]) -> Set[ActorData]:
        res: Set[ActorData] = set()
        for obj in _data:
            _d = ActorDataProxy(obj.get("name"))
            res.add(_d)
        return res
    #
    def build(self, json_data: Dict[str, Any], data_base_system: DataBaseSystem) -> None:
        self.datalist = json_data.get("stages")
        if self.datalist is None:
            logger.error("StageBuilder: stages data is None.")
            return

        for data in self.datalist:
            stagedata = data.get("stage")    
            assert stagedata is not None    
            #
            stage = data_base_system.get_stage(stagedata.get('name'))
            assert stage is not None
            #连接
            propsinstage: Set[PropData] = self.props_proxy_in_stage(stagedata.get("props"))
            stage._props = propsinstage
            #连接
            actors_in_stage: Set[ActorData] = self.actors_proxy_in_stage(stagedata.get("actors"))
            stage._actors = actors_in_stage
            #
            self.stages.append(stage)
########################################################################################################################
########################################################################################################################
########################################################################################################################
class ActorBuilder:

    def __init__(self, dataname: str) -> None:
        self.datalist: Optional[Dict[str, Any]] = None
        self.actors: List[ActorData] = []
        self.dataname = dataname

    def __str__(self) -> str:
        return f"ActorBuilder: {self.datalist}"       

    #
    def build(self, json_data: Dict[str, Any], data_base_system: DataBaseSystem) -> None:
        self.datalist = json_data.get(self.dataname)
        if self.datalist is None:
            logger.error(f"ActorBuilder: {self.dataname} data is None.")
            return
        
        for datablock in self.datalist:
            _props: Set[PropData] = set()
            propdata = datablock.get("props")
            for propdata in propdata:
                prop = PropDataProxy(propdata.get("name"))
                _props.add(prop)

            # Actor核心数据
            _core_ = datablock.get("actor")
            actor_name = _core_.get("name")
            actor_data = data_base_system.get_actor(actor_name)
            if actor_data is None:
                logger.error(f"ActorBuilder: {actor_name} not found in database.")
                continue
            # 连接
            actor_data._props = _props
            #
            self.actors.append(actor_data)
########################################################################################################################
########################################################################################################################
########################################################################################################################
class WorldSystemBuilder:

    def __init__(self, data_name: str) -> None:
        self._data_list: Optional[Dict[str, Any]] = None
        self._world_system_datas: List[WorldSystemData] = []
        self._data_name = data_name

    def __str__(self) -> str:
        return f"WorldSystemBuilder: {self._data_list}"       

    #
    def build(self, json_data: Dict[str, Any], data_base_system: DataBaseSystem) -> None:
        self._data_list = json_data.get(self._data_name)
        if self._data_list is None:
            logger.error(f"WorldSystemBuilder: {self._data_name} data is None.")
            return
        
        for datablock in self._data_list:
            _core_ = datablock.get("world_system")
            _name = _core_.get("name")
            world_system_data = data_base_system.get_world_system(_name)
            if world_system_data is None:
                logger.error(f"WorldSystemBuilder: {_name} not found in database.")
                continue
     
            self._world_system_datas.append(world_system_data)