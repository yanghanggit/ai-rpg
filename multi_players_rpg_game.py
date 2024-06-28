from rpg_game.rpg_game import RPGGame

class MultiplayersRPGGame():
    
    def __init__(self, host: str, game: RPGGame):
        self._host: str = host
        self._rpggame: RPGGame = game
