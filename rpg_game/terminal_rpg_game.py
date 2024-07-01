from my_entitas.extended_context import ExtendedContext
from rpg_game.rpg_game import RPGGame

class TerminalRPGGame(RPGGame):
    
    def __init__(self, name: str, context: ExtendedContext) -> None:
        super().__init__(name, context)
