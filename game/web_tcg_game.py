from game.tcg_game import TCGGame
from game.tcg_game_context import TCGGameContext


class WebTCGGame(TCGGame):

    def __init__(self, name: str, context: TCGGameContext) -> None:
        super().__init__(name, context)
