from entitas import ExecuteProcessor, Matcher, InitializeProcessor #type: ignore
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from ecs_systems.components import (StageComponent, ActorComponent, WorldComponent, SimpleRPGAttrComponent)
import json
from typing import Dict, override, List
from file_system.helper import update_status_profile_file, update_stage_actors_map_file


class EndSystem(InitializeProcessor, ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self._context: ExtendedContext = context
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
        self._context._langserve_agent_system.dump_chat_history()
        # 打印所有的道具归属
        self.dump_prop_files()
        # 打印所有的角色的状态信息（例如属性）
        self.dump_status_profile()
        logger.debug(f"{'=' * 100}")  #方便看
############################################################################################################
    def dump_world(self) -> None:
        world_entities = self._context.get_group(Matcher(WorldComponent)).entities
        for world_entity in world_entities:
            world_comp = world_entity.get(WorldComponent)
            logger.debug(f"/dump_world:{world_comp.name}")
############################################################################################################
    def dump_stages_and_actors(self) -> None:
        simple_dump = self.simple_dump_stages_and_actors()
        if len(simple_dump.keys()) > 0:
            logger.debug(f"/dump_stages_and_actors: \n{simple_dump}")
        else:
            logger.warning("/dump_stages_and_actors: No stages and actors now")

        update_stage_actors_map_file(self._context._file_system, simple_dump)
############################################################################################################
    def simple_dump_stages_and_actors(self) -> Dict[str, List[str]]:
        stage_entities = self._context.get_group(Matcher(StageComponent)).entities
        actor_entities = self._context.get_group(Matcher(ActorComponent)).entities
        map: Dict[str, List[str]] = {}
        for stage_entity in stage_entities:
            stage_comp = stage_entity.get(StageComponent)
            name_list = map.get(stage_comp.name, [])
            map[stage_comp.name] = name_list

            for actor_entity in actor_entities:
                actor_comp = actor_entity.get(ActorComponent)
                if actor_comp.current_stage == stage_comp.name:
                    name_list.append(actor_comp.name)
        return map
############################################################################################################
    def dump_prop_files(self) -> None:
        file_system = self._context._file_system
        prop_files = file_system._prop_files

        dump_data: Dict[str, str] = {}
        for owner_name, owners_prop_files in prop_files.items():
            name_list = ",".join([str(prop_file) for prop_file in owners_prop_files])
            dump_data[owner_name] = name_list

        logger.debug(f"{json.dumps(dump_data, ensure_ascii = False)}")
############################################################################################################
    def dump_status_profile(self) -> None:
        rpg_attr_entities = self._context.get_group(Matcher(SimpleRPGAttrComponent)).entities
        for rpg_attr_entity in rpg_attr_entities:
            rpg_attr_comp = rpg_attr_entity.get(SimpleRPGAttrComponent)
            _dict_ = rpg_attr_comp._asdict()
            assert len(_dict_) > 0
            update_status_profile_file(self._context._file_system, rpg_attr_comp.name, _dict_)
############################################################################################################