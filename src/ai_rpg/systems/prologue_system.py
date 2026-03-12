"""Pipeline 起始系统模块。

本模块实现了 Pipeline 首端的起始逻辑，作为每条管线执行前的占位入口。
未来可在此处扩展初始化检查、状态预热、日志记录等前置操作。
"""

from typing import Final, final, override
from ..entitas import ExecuteProcessor
from ..game.rpg_game import RPGGame
from loguru import logger


@final
class PrologueSystem(ExecuteProcessor):
    """Pipeline 起始系统。

    位于每条 Pipeline 的最首端，作为占位入口。
    未来可在此扩展前置检查、状态预热或其他起始操作。

    Attributes:
        _game: 游戏上下文实例，包含游戏的核心状态和数据。
    """

    ############################################################################################################
    def __init__(self, game_context: RPGGame) -> None:
        self._game: Final[RPGGame] = game_context

    ############################################################################################################
    @override
    async def execute(self) -> None:
        logger.debug("🚀 Pipeline 起始系统执行 - PrologueSystem")

    ############################################################################################################
