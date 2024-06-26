
from entitas import ExecuteProcessor, Matcher, InitializeProcessor #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import (StageComponent, ActorComponent, WorldComponent, SimpleRPGAttrComponent)
import json
from typing import Dict, override, List
from auxiliary.file_system_helper import update_status_profile_file



   
class EndSystem(InitializeProcessor, ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    @override
    def initialize(self) -> None:
        pass
############################################################################################################
    @override
    def execute(self) -> None:
        self.debug_dump()
############################################################################################################
    def debug_dump(self) -> None:
        logger.debug(f"{'=' * 100}") #方便看
        # 打印所有的世界信息
        self.dump_world()
        # 打印一下所有的场景信息
        self.dump_stages_and_actors()
        # 打印一下所有的agent信息
        self.context.agent_connect_system.dump_chat_history()
        # 打印所有的道具归属
        self.dump_prop_files()
        # 打印所有的角色的状态信息（例如属性）
        self.dump_status_profile()
        logger.debug(f"{'=' * 100}")  #方便看
############################################################################################################
    def dump_world(self) -> None:
        worldentities = self.context.get_group(Matcher(WorldComponent)).entities
        for entity in worldentities:
            worldcomp: WorldComponent = entity.get(WorldComponent)
            logger.debug(f"/dump_world: {worldcomp.name}")
############################################################################################################
    def dump_stages_and_actors(self) -> None:
        infomap = self.simple_dump_stages_and_actors()
        if len(infomap.keys()) > 0:
            logger.debug(f"/dump_stages_and_actors: \n{infomap}")
        else:
            logger.debug("/dump_stages_and_actors: No stages and actors now")
############################################################################################################
    def simple_dump_stages_and_actors(self) -> Dict[str, List[str]]:
        stages_entities = self.context.get_group(Matcher(StageComponent)).entities
        actor_entities = self.context.get_group(Matcher(ActorComponent)).entities
        map: Dict[str, List[str]] = {}
        for entity in stages_entities:
            stagecomp: StageComponent = entity.get(StageComponent)
            ls = map.get(stagecomp.name, [])
            map[stagecomp.name] = ls

            for entity in actor_entities:
                actor_comp: ActorComponent = entity.get(ActorComponent)
                if actor_comp.current_stage == stagecomp.name:
                    ls.append(actor_comp.name)
        return map
############################################################################################################
    def dump_prop_files(self) -> None:
        file_system = self.context.file_system
        propfiles = file_system._prop_files

        dumpdict: Dict[str, str] = {}
        for ownername, propfilelist in propfiles.items():
            liststr = ",".join([str(propfile) for propfile in propfilelist])
            dumpdict[ownername] = liststr

        logger.debug(f"{json.dumps(dumpdict, ensure_ascii = False)}")
############################################################################################################
    def dump_status_profile(self) -> None:
        rpg_attr_entities = self.context.get_group(Matcher(SimpleRPGAttrComponent)).entities
        for entity in rpg_attr_entities:
            rpg_attr_comp: SimpleRPGAttrComponent = entity.get(SimpleRPGAttrComponent)
            _dict_ = rpg_attr_comp._asdict()
            assert len(_dict_) > 0
            update_status_profile_file(self.context.file_system, rpg_attr_comp.name, _dict_)
############################################################################################################