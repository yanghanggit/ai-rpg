from rpg_game import RPGGame

# 多人游戏的类 server 模式专用
class MultiplayersGame():
    
    playername: str
    hostname: str
    rpggame: RPGGame

    def __init__(self, player: str, host: str, game: RPGGame):
        self.playername = player
        self.hostname = host
        self.rpggame = game
