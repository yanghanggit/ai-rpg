from entitas import ExecuteProcessor, Matcher, Entity  # type: ignore
from typing import final, override, Set
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from rpg_game.rpg_game import RPGGame
from my_components.components import RoundEventsComponent


@final
class BeginSystem(ExecuteProcessor):
    ############################################################################################################
    def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
        self._context: RPGEntitasContext = context
        self._game: RPGGame = rpg_game

    ############################################################################################################
    @override
    def execute(self) -> None:

        # 每次进入这个系统就增加一个回合
        self._game._runtime_game_round += 1
        logger.debug(f"_runtime_game_round = {self._game._runtime_game_round}")

        # 清除这个临时用的数据结构
        self._clear_round_events()

    ############################################################################################################
    def _clear_round_events(self) -> None:

        entities: Set[Entity] = self._context.get_group(
            Matcher(all_of=[RoundEventsComponent])
        ).entities

        for entity in entities:
            rounds_comp = entity.get(RoundEventsComponent)
            entity.replace(RoundEventsComponent, rounds_comp.name, [])

    ############################################################################################################


############################################################################################################
