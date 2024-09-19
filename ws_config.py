from enum import Enum
from pydantic import BaseModel
from typing import Dict, Set, List, Optional
from my_data.model_def import GameModel


class WS_CONFIG:
    LOCAL_HOST: str = "127.0.0.1"
    PORT: int = 8080
    SEND_MESSAGES_COUNT: int = 20


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################


class GameState(Enum):
    UNLOGGED = 0
    LOGGED_IN = 1
    GAME_CREATED = 3
    GAME_JOINED = 4
    PLAYING = 5
    REQUESTING_EXIT = 6


class GameStateWrapper:

    def __init__(self, game_stage: GameState) -> None:

        self._state: GameState = game_stage

        self._transition_protocol: Dict[GameState, Set[GameState]] = {
            GameState.UNLOGGED: {GameState.LOGGED_IN},
            GameState.LOGGED_IN: {GameState.GAME_CREATED},
            GameState.GAME_CREATED: {GameState.GAME_JOINED},
            GameState.GAME_JOINED: {GameState.PLAYING},
            GameState.PLAYING: {GameState.REQUESTING_EXIT},
            GameState.REQUESTING_EXIT: {GameState.GAME_CREATED},
        }

    @property
    def state(self) -> GameState:
        return self._state

    def can_transition(self, dst: GameState) -> bool:
        return dst in self._transition_protocol.get(self._state, set())

    def transition(self, dst: GameState) -> None:
        if self.can_transition(dst):
            self._state = dst
        else:
            raise ValueError(f"Can't transition from {self._state} to {dst}")


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################


# 测试用
class LoginData(BaseModel):
    response: bool = False
    user_name: str = ""


# 测试用
class CreateData(BaseModel):
    response: bool = False
    user_name: str = ""
    game_name: str = ""
    selectable_actor_names: List[str] = []
    game_model: Optional[GameModel] = None


# 测试用
class JoinData(BaseModel):
    response: bool = False
    user_name: str = ""
    game_name: str = ""
    ctrl_actor_name: str = ""


# 测试用
class StartData(BaseModel):
    response: bool = False
    user_name: str = ""
    game_name: str = ""
    ctrl_actor_name: str = ""


# 测试用
class ExitData(BaseModel):
    response: bool = False
    user_name: str = ""
    game_name: str = ""
    ctrl_actor_name: str = ""


# 测试用
class ExecuteData(BaseModel):
    response: bool = False
    error: str = ""
    user_name: str = ""
    game_name: str = ""
    ctrl_actor_name: str = ""
    user_input: List[str] = []
    messages: List[str] = []


# 测试用
class WatchData(BaseModel):
    response: bool = False
    user_name: str = ""
    game_name: str = ""
    ctrl_actor_name: str = ""
    message: str = ""


# 测试用
class CheckData(BaseModel):
    response: bool = False
    user_name: str = ""
    game_name: str = ""
    ctrl_actor_name: str = ""
    message: str = ""
