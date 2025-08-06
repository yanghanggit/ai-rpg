from loguru import logger
from ..entitas import Matcher, ExecuteProcessor
from typing import final, override
from ..models import DestroyComponent
from ..game.tcg_game import TCGGame


@final
class DestroyEntitySystem(ExecuteProcessor):

    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ####################################################################################################################################
    @override
    def execute(self) -> None:
        entities = self._game.get_group(Matcher(DestroyComponent)).entities.copy()
        while len(entities) > 0:
            destory_entity = entities.pop()
            self._game.destroy_entity(destory_entity)
            logger.debug(f"Destroy entity: {destory_entity._name}")

    ####################################################################################################################################
