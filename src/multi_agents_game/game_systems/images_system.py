from typing import final, override
from loguru import logger
from ..entitas import ExecuteProcessor, ExecuteProcessor, Matcher
from ..game.tcg_game import TCGGame
from ..models import AppearanceComponent, ActorComponent


@final
class ImagesSystem(ExecuteProcessor):

    ####################################################################################################################################
    def __init__(
        self,
        game_context: TCGGame,
    ) -> None:
        self._game = game_context

    ####################################################################################################################################
    @override
    async def execute(self) -> None:
        logger.debug("ImagesSystem execute called")
        entities = self._game.get_group(
            Matcher(
                all_of=[AppearanceComponent, ActorComponent],
            )
        ).entities.copy()

        for entity in entities:
            appearance = entity.get(AppearanceComponent)
            if appearance:
                logger.debug(
                    f"{self._game.name}, 处理外观组件: {appearance.model_dump_json()}"
                )

    ####################################################################################################################################
