from loguru import logger
from typing import List, Optional

### 目前啥也不干，但留着有用的时候再用
class PlayerProxy:

    def __init__(self, name: str) -> None:
        self.name = name

    def __str__(self) -> str:
        return f'PlayerProxy({self.name})'
    

### 目前啥也不干，但留着有用的时候再用
PLAYERS: List[PlayerProxy] = []

### 创建一个玩家代理
def create_player_proxy(playername: str) -> PlayerProxy:
    player = PlayerProxy(playername)
    PLAYERS.append(player)
    return player

### 获取一个玩家代理
def get_player_proxy(playername: str) -> Optional[PlayerProxy]:
    for player in PLAYERS:
        if player.name == playername:
            return player
    return None

### 单人游戏，临时的名字
TEST_PLAYER_NAME = "北京柏林互动科技有限公司"

TEST_GAME_INSTRUCTIONS_WHEN_LOGIN_SUCCESS_FOR_FIRST_TIME = """
这是一个demo。xxxxxxxx..
"""
    


