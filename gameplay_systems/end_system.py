from entitas import ExecuteProcessor, Matcher  # type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from gameplay_systems.components import (
    StageComponent,
    ActorComponent,
)
from typing import override, List
from rpg_game.rpg_game import RPGGame
from collections import OrderedDict


class EndSystem(ExecuteProcessor):

    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:
        self._show_map_info()

    ############################################################################################################
    def _show_map_info(self) -> None:

        map_dumps = self._get_map_info()
        if len(map_dumps.keys()) > 0:
            logger.info(f"/show map info: \n{map_dumps}")

    ############################################################################################################
    def _get_map_info(self) -> OrderedDict[str, List[str]]:

        stage_entities = self._context.get_group(Matcher(StageComponent)).entities
        actor_entities = self._context.get_group(Matcher(ActorComponent)).entities

        ret: OrderedDict[str, List[str]] = OrderedDict()
        for stage_entity in stage_entities:

            stage_comp = stage_entity.get(StageComponent)
            name_list = ret.setdefault(stage_comp.name, [])

            for actor_entity in actor_entities:
                actor_comp = actor_entity.get(ActorComponent)
                if actor_comp.current_stage == stage_comp.name:
                    name_list.append(actor_comp.name)

        return ret


############################################################################################################
