from typing import List, Optional

### 简单的类定义，后续再加
class PlayerProxy:

    def __init__(self, name: str) -> None:
        self._name: str = name
        self._client_messages: List[tuple[str, str]] = []
        self._input_commands: List[str] = []
    
    def add_message(self, sender: str, message: str) -> None:
        self._client_messages.append((sender, message))

    def add_system_message(self, message: str) -> None:
        self.add_message(f"[system]", message)

    def add_actor_message(self, actor_name: str, message: str) -> None:
        self.add_message(f"[{actor_name}]", message)

    def add_stage_message(self, stage_name: str, message: str) -> None:
        self.add_message(f"[{stage_name}]", message)
##########################################################################################################################################################
##########################################################################################################################################################
##########################################################################################################################################################

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
##########################################################################################################################################################