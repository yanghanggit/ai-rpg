from rpg_game.rpg_game import RPGGame
from rpg_game.rpg_entitas_context import RPGEntitasContext


class WebGame(RPGGame):

    def __init__(self, name: str, context: RPGEntitasContext):
        super().__init__(name, context)
