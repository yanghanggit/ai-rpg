from rpg_game import RPGGame

class MultiplayersGame():
    
    playername: str
    hostname: str
    rpggame: RPGGame

    def __init__(self, player: str, host: str, game: RPGGame):
        self.playername = player
        self.hostname = host
        self.rpggame = game
