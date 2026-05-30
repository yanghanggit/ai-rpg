from typing import Final, final
from overrides import override
from ..entitas import ExecuteProcessor
from ..game.tcg_game import TCGGame


#######################################################################################################################################
@final
class ActorAppearanceInitSystem(ExecuteProcessor):
    """角色外观初始化系统（Init 语义）。"""

    def __init__(self, game: TCGGame) -> None:
        self._game: Final[TCGGame] = game

    #######################################################################################################################################
    @override
    async def execute(self) -> None:

        # Step 1: 所有角色 appearance == "" → base_body（含 Enemy）
        self._initialize_appearances()

    #######################################################################################################################################
    def _initialize_appearances(self) -> None:
        pass

    #######################################################################################################################################
