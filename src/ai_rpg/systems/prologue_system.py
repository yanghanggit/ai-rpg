"""Pipeline 首端占位入口，供将来插入前置检查或预热。"""

from typing import Final, final, override

from loguru import logger

from ..entitas import ExecuteProcessor
from ..game.rpg_game import RPGGame


@final
class PrologueSystem(ExecuteProcessor):
    """Pipeline 首端占位系统，未来可在此扩展前置操作。"""

    ############################################################################################################
    def __init__(self, game: RPGGame) -> None:
        self._game: Final[RPGGame] = game

    ############################################################################################################
    @override
    async def execute(self) -> None:
        logger.debug("🚀 Pipeline 起始系统执行 - PrologueSystem")

    ############################################################################################################
