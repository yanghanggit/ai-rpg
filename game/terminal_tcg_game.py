from game.tcg_game_context import TCGGameContext
from game.tcg_game import TCGGame


class TerminalTCGGame(TCGGame):

    def __init__(self, name: str, context: TCGGameContext) -> None:
        super().__init__(name, context)
