from loguru import logger
from entitas import Matcher, ExecuteProcessor  # type: ignore
from typing import final, override
from components.components import DestroyFlagComponent
from game.tcg_game import TCGGame


@final
class DestroySystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ####################################################################################################################################
    @override
    def execute(self) -> None:
        entities = self._game.get_group(Matcher(DestroyFlagComponent)).entities.copy()
        while len(entities) > 0:
            destory_entity = entities.pop()
            self._game.destroy_entity(destory_entity)
            logger.debug(f"Destroy entity: {destory_entity._name}")

    ####################################################################################################################################
