from game.rpg_game import RPGGame
from game.rpg_game_context import RPGGameContext


class WebRPGGame(RPGGame):

    def __init__(self, name: str, context: RPGGameContext):
        super().__init__(name, context)
