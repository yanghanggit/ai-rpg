from entitas import ExecuteProcessor, Matcher, InitializeProcessor  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from gameplay_systems.components import (
    StageComponent,
    ActorComponent,
    RPGAttributesComponent,
    RPGCurrentWeaponComponent,
    RPGCurrentClothesComponent,
)

from typing import Dict, override, List, Any
import file_system.helper
from rpg_game.rpg_game import RPGGame


class EndSystem(InitializeProcessor, ExecuteProcessor):
    ############################################################################################################
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

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

        # 打印一下所有的场景信息
        self.dump_stages_and_actors()

        # 打印一下所有的agent信息
        self._context._langserve_agent_system.dump_chat_history()

        # 打印所有的角色的状态信息（例如属性）
        self.dump_status_profile()

    ############################################################################################################
    def dump_stages_and_actors(self) -> None:
        simple_dump = self.simple_dump_stages_and_actors()
        if len(simple_dump.keys()) > 0:
            logger.debug(f"/dump_stages_and_actors: \n{simple_dump}")
        else:
            logger.warning("/dump_stages_and_actors: No stages and actors now")

        file_system.helper.update_stage_actors_map_file(
            self._context._file_system, simple_dump
        )

    ############################################################################################################
    def simple_dump_stages_and_actors(self) -> Dict[str, List[str]]:

        stage_entities = self._context.get_group(Matcher(StageComponent)).entities
        actor_entities = self._context.get_group(Matcher(ActorComponent)).entities

        ret: Dict[str, List[str]] = {}
        for stage_entity in stage_entities:

            stage_comp = stage_entity.get(StageComponent)
            name_list = ret.get(stage_comp.name, [])
            ret[stage_comp.name] = name_list

            for actor_entity in actor_entities:
                actor_comp = actor_entity.get(ActorComponent)
                if actor_comp.current_stage == stage_comp.name:
                    name_list.append(actor_comp.name)

        return ret

    ############################################################################################################
    def dump_status_profile(self) -> List[Dict[str, Any]]:

        ret: List[Dict[str, Any]] = []

        entities = self._context.get_group(
            Matcher(
                any_of=[
                    RPGAttributesComponent,
                    RPGCurrentWeaponComponent,
                    RPGCurrentClothesComponent,
                ]
            )
        ).entities
        for entity in entities:

            final_dict: Dict[str, Any] = {}

            if entity.has(RPGAttributesComponent):
                rpg_attr_comp = entity.get(RPGAttributesComponent)
                attr_dict: Dict[str, Any] = {
                    RPGAttributesComponent.__name__: rpg_attr_comp._asdict()
                }
                assert len(attr_dict) > 0
                final_dict.update(attr_dict)

            if entity.has(RPGCurrentWeaponComponent):
                rpg_weapon_comp = entity.get(RPGCurrentWeaponComponent)
                weapon_dict: Dict[str, Any] = {
                    RPGCurrentWeaponComponent.__name__: rpg_weapon_comp._asdict()
                }
                assert len(weapon_dict) > 0
                final_dict.update(weapon_dict)

            if entity.has(RPGCurrentClothesComponent):
                rpg_armor_comp = entity.get(RPGCurrentClothesComponent)
                armor_dict: Dict[str, Any] = {
                    RPGCurrentClothesComponent.__name__: rpg_armor_comp._asdict()
                }
                assert len(armor_dict) > 0
                final_dict.update(armor_dict)

            ret.append(final_dict)
            file_system.helper.update_status_profile_file(
                self._context._file_system, rpg_attr_comp.name, final_dict
            )

        return ret


############################################################################################################
