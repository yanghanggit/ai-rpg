from game.rpg_game_context import RPGGameContext
from game.rpg_game import RPGGame


class TerminalRPGGame(RPGGame):

    def __init__(self, name: str, context: RPGGameContext) -> None:
        super().__init__(name, context)
