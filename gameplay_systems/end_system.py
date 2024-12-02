from entitas import ExecuteProcessor, Matcher  # type: ignore
from game.rpg_game_context import RPGGameContext
from loguru import logger
from components.components import (
    StageComponent,
    ActorComponent,
)
from typing import final, override, List
from game.rpg_game import RPGGame
from collections import OrderedDict


@final
class EndSystem(ExecuteProcessor):

    def __init__(self, context: RPGGameContext, rpg_game: RPGGame) -> None:
        self._context: RPGGameContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:
        self._log_map_information()

    ############################################################################################################
    def _log_map_information(self) -> None:

        map_dumps = self._fetch_stage_actor_mapping()
        if len(map_dumps.keys()) > 0:
            logger.warning(f"/show map info: \n{map_dumps}")

    ############################################################################################################
    def _fetch_stage_actor_mapping(self) -> OrderedDict[str, List[str]]:

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
