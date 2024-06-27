from rpg_game import RPGGame

class MultiplayersRPGGame():
    
    def __init__(self, host: str, game: RPGGame):
        self._host = host
        self._rpggame = game
