from entitas import ExecuteProcessor  # type: ignore
from typing import List, final, override, Dict
from game.tcg_game import TCGGame
from loguru import logger


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
        self._mapping()

    ############################################################################################################
    def _mapping(self) -> None:
        names_mapping: Dict[str, List[str]] = (
            self._game.retrieve_stage_actor_names_mapping()
        )
        logger.debug(f"names_mapping = {names_mapping}")

    ############################################################################################################
