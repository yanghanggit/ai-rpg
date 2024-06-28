from loguru import logger
from typing import List, Optional
from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from systems.components import StageComponent, ActorComponent, PlayerComponent
from enum import Enum
import re

class PLAYER_INPUT_MODE(Enum):
    INVALID = 0,
    WEB_HTTP_REQUEST = 1
    TERMINAL = 2

def is_valid_ipv4(ip: str) -> bool:
    ipv4_pattern = re.compile(r'^((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')  
    return ipv4_pattern.match(ip) is not None

def determine_player_input_mode(playername: List[str]) -> PLAYER_INPUT_MODE:
    for name in playername:
        if is_valid_ipv4(name):
            return PLAYER_INPUT_MODE.WEB_HTTP_REQUEST
    return PLAYER_INPUT_MODE.TERMINAL

### 目前啥也不干，但留着有用的时候再用
class PlayerProxy:

    def __init__(self, name: str) -> None:
        self.name = name
        self.client_messages: List[tuple[str, str]] = []
        self._inputs: List[str] = []

    def __str__(self) -> str:
        return f'PlayerProxy({self.name})'
    
    def add_message(self, sender: str, message: str) -> None:
        self.client_messages.append((sender, message))
        #logger.debug(f"PlayerProxy({self.name}).add_message({sender}, {message})")

    def add_system_message(self, message: str) -> None:
        self.add_message(f"[system]", message)

    def add_actor_message(self, actor_name: str, message: str) -> None:
        self.add_message(f"[{actor_name}]", message)

    def add_stage_message(self, stagename: str, message: str) -> None:
        self.add_message(f"[{stagename}]", message)

### 目前啥也不干，但留着有用的时候再用
PLAYERS: List[PlayerProxy] = []

### 创建一个玩家代理
def create_player_proxy(playername: str) -> PlayerProxy:
    if get_player_proxy(playername) is not None:
        raise ValueError(f"玩家代理已经存在: {playername}")
    player = PlayerProxy(playername)
    PLAYERS.append(player)
    return player

### 获取一个玩家代理
def get_player_proxy(playername: str) -> Optional[PlayerProxy]:
    for player in PLAYERS:
        if player.name == playername:
            return player
    return None

def remove_player_proxy(playerproxy: PlayerProxy) -> None:
    PLAYERS.remove(playerproxy)

###################################################################################################################
def add_client_actor_message(entity: Entity, message: str) -> None:
    if not entity.has(PlayerComponent):
        return

    playercomp: PlayerComponent = entity.get(PlayerComponent)
    playername: str = playercomp.name
    playerproxy = get_player_proxy(playername)
    if playerproxy is None:
        logger.error(f"notify_player_client, 玩家代理不存在{playername}???")
        return

    #登陆的消息
    actor_comp: ActorComponent = entity.get(ActorComponent)
    playerproxy.add_actor_message(actor_comp.name, message)
###################################################################################################################

    

    


