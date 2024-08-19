import re
from typing import List, Optional
from player.player_proxy import PlayerProxy


def is_valid_ipv4(ip: str) -> bool:
    ipv4_pattern = re.compile(
        r"^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    )
    return ipv4_pattern.match(ip) is not None


### 目前啥也不干，但留着有用的时候再用
PLAYER_PROXIES: List[PlayerProxy] = []


### 创建一个玩家代理
def create_player_proxy(playername: str) -> PlayerProxy:
    if get_player_proxy(playername) is not None:
        raise ValueError(f"玩家代理已经存在: {playername}")
    player = PlayerProxy(playername)
    PLAYER_PROXIES.append(player)
    return player


### 获取一个玩家代理
def get_player_proxy(playername: str) -> Optional[PlayerProxy]:
    for player in PLAYER_PROXIES:
        if player._name == playername:
            return player
    return None


def remove_player_proxy(playerproxy: PlayerProxy) -> None:
    PLAYER_PROXIES.remove(playerproxy)
