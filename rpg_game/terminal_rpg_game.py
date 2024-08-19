from rpg_game.rpg_entitas_context import RPGEntitasContext
from rpg_game.rpg_game import RPGGame


class TerminalRPGGame(RPGGame):

    def __init__(self, name: str, context: RPGEntitasContext) -> None:
        super().__init__(name, context)
