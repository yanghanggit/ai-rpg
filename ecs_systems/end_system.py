from entitas import ExecuteProcessor, Matcher, InitializeProcessor #type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from ecs_systems.components import (StageComponent, ActorComponent, WorldComponent, SimpleRPGAttrComponent, SimpleRPGWeaponComponent, SimpleRPGArmorComponent)
import json
from typing import Dict, override, List, Any
import file_system.helper
from file_system.files_def import PropFile

class EndSystem(InitializeProcessor, ExecuteProcessor):
############################################################################################################
    def __init__(self, context: RPGEntitasContext) -> None:
        self._context: RPGEntitasContext = context
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
        #logger.debug(f"{'=' * 100}") #方便看
        # 打印所有的世界信息
        self.dump_world()
        # 打印一下所有的场景信息
        self.dump_stages_and_actors()
        # 打印一下所有的agent信息
        self._context._langserve_agent_system.dump_chat_history()
        # 打印所有的道具归属
        #self.dump_prop_files()
        # 打印所有的角色的状态信息（例如属性）
        self.dump_status_profile()
        #logger.debug(f"{'=' * 100}")  #方便看
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

        file_system.helper.update_stage_actors_map_file(self._context._file_system, simple_dump)
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
    # def dump_prop_files(self) -> None:
    #     prop_file_dict = self._context._file_system.get_base_file_dict(PropFile)
    #     dump_data: Dict[str, str] = {}
    #     for owner_name, prop_files in prop_file_dict.items():
    #         dump_data[owner_name] = ",".join([str(prop_file) for prop_file in prop_files])
    #     logger.debug(f"{json.dumps(dump_data, ensure_ascii = False)}")
############################################################################################################
    def dump_status_profile(self) -> List[Dict[str, Any]]:

        ret: List[Dict[str, Any]] = []

        entities = self._context.get_group(Matcher(any_of = [SimpleRPGAttrComponent, SimpleRPGWeaponComponent, SimpleRPGArmorComponent])).entities
        for entity in entities:

            final_dict: Dict[str, Any] = {}

            if entity.has(SimpleRPGAttrComponent):
                rpg_attr_comp = entity.get(SimpleRPGAttrComponent)
                attr_dict: Dict[str, Any] = {SimpleRPGAttrComponent.__name__: rpg_attr_comp._asdict()}
                assert len(attr_dict) > 0
                final_dict.update(attr_dict)

            if entity.has(SimpleRPGWeaponComponent):
                rpg_weapon_comp = entity.get(SimpleRPGWeaponComponent)
                weapon_dict: Dict[str, Any] = {SimpleRPGWeaponComponent.__name__: rpg_weapon_comp._asdict()}
                assert len(weapon_dict) > 0
                final_dict.update(weapon_dict)

            if entity.has(SimpleRPGArmorComponent):
                rpg_armor_comp = entity.get(SimpleRPGArmorComponent)
                armor_dict: Dict[str, Any] = {SimpleRPGArmorComponent.__name__: rpg_armor_comp._asdict()}
                assert len(armor_dict) > 0
                final_dict.update(armor_dict)

            ret.append(final_dict)
            file_system.helper.update_status_profile_file(self._context._file_system, rpg_attr_comp.name, final_dict)

        return ret
############################################################################################################