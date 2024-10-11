from entitas import ExecuteProcessor, Matcher  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from gameplay_systems.components import (
    StageComponent,
    ActorComponent,
)

from typing import Dict, override, List, Any, FrozenSet
import extended_systems.file_system_helper
from rpg_game.rpg_game import RPGGame
from my_data.model_def import ComponentDumpModel, EntityDumpModel


class EndSystem(ExecuteProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:
        self._dump()

    ############################################################################################################
    def _dump(self) -> None:

        #
        self._context._langserve_agent_system.dump_chat_histories()

        #
        map_dumps = self._get_map_dumps()
        if len(map_dumps.keys()) > 0:
            logger.info(f"/dump_map: \n{map_dumps}")

        extended_systems.file_system_helper.update_map_file(
            self._context._file_system, map_dumps
        )

        #
        entity_dumps = self._get_entity_dumps(
            frozenset({StageComponent, ActorComponent})
        )
        for key, value in entity_dumps.items():
            extended_systems.file_system_helper.update_entity_dump_file(
                self._context._file_system, key, value
            )

    ############################################################################################################
    def _get_map_dumps(self) -> Dict[str, List[str]]:

        stage_entities = self._context.get_group(Matcher(StageComponent)).entities
        actor_entities = self._context.get_group(Matcher(ActorComponent)).entities

        ret: Dict[str, List[str]] = {}
        for stage_entity in stage_entities:

            stage_comp = stage_entity.get(StageComponent)
            name_list = ret.setdefault(stage_comp.name, [])

            for actor_entity in actor_entities:
                actor_comp = actor_entity.get(ActorComponent)
                if actor_comp.current_stage == stage_comp.name:
                    name_list.append(actor_comp.name)

        return ret

    ############################################################################################################
    def _get_entity_dumps(
        self, component_types: FrozenSet[type[Any]]
    ) -> Dict[str, EntityDumpModel]:

        ret: Dict[str, EntityDumpModel] = {}

        entities = self._context.get_group(Matcher(any_of=component_types)).entities

        for entity in entities:

            safe_name = self._context.safe_get_entity_name(entity)
            if safe_name == "":
                continue

            entity_dump = EntityDumpModel(name=safe_name, components=[])
            for key, value in entity._components.items():
                entity_dump.components.append(
                    ComponentDumpModel(name=key.__name__, data=value._asdict())
                )

            ret[safe_name] = entity_dump

        return ret


############################################################################################################
