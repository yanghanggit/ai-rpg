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
    def execute(self) -> None:

        # 核心调用
        self._game.save()

        # 保存时，打印当前场景中的所有角色
        self._log_map()

    ############################################################################################################
    def _log_map(self) -> None:
        names_mapping: Dict[str, List[str]] = self._game.gen_map()
        logger.info(f"names_mapping = {names_mapping}")

    ############################################################################################################
