import asyncio
from typing import Dict, List, final, override
from loguru import logger
from ..entitas import ExecuteProcessor
from ..game.tcg_game import TCGGame


@final
class SaveSystem(ExecuteProcessor):

    ############################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    async def execute(self) -> None:

        # 保存时，打印当前场景中的所有角色
        names_mapping: Dict[str, List[str]] = self._game.get_stage_actor_distribution()
        logger.info(f"names_mapping = {names_mapping}")

        # 核心调用
        # self._game.save()
        logger.debug("开始保存游戏...")
        await asyncio.to_thread(self._game.save)

    ############################################################################################################
