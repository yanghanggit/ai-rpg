from enum import Enum
from pydantic import BaseModel
from typing import Dict, Set, List


class WS_CONFIG(Enum):
    Host = "127.0.0.1"
    Port = 8080


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################


class GameState(Enum):
    LOGOUT = 0
    LOGIN = 1
    CREATE = 3
    JOIN = 4
    START = 5
    EXIT = 6


class GameStateWrapper:

    def __init__(self, game_stage: GameState) -> None:
        self._state: GameState = game_stage

        self._state_transition_protocol: Dict[GameState, Set[GameState]] = {
            GameState.LOGOUT: {GameState.LOGIN},
            GameState.LOGIN: {GameState.CREATE},
            GameState.CREATE: {GameState.JOIN},
            GameState.JOIN: {GameState.START},
            GameState.START: {GameState.EXIT},
            GameState.EXIT: {GameState.CREATE},
        }

    @property
    def state(self) -> GameState:
        return self._state

    def can_transition(self, dst: GameState) -> bool:
        return self._can_transition(self._state, dst)

    def _can_transition(self, src: GameState, dst: GameState) -> bool:
        return dst in self._state_transition_protocol[src]

    def transition(self, dst: GameState) -> None:
        if self.can_transition(dst):
            self._state = dst
        else:
            raise ValueError(f"Can't transition from {self._state} to {dst}")


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class LoginData(BaseModel):
    response: bool = False
    user_name: str = ""


class CreateData(BaseModel):
    response: bool = False
    user_name: str = ""
    game_name: str = ""
    selectable_actor_names: List[str] = []


class JoinData(BaseModel):
    response: bool = False
    user_name: str = ""
    game_name: str = ""
    ctrl_actor_name: str = ""


class StartData(BaseModel):
    response: bool = False
    user_name: str = ""
    game_name: str = ""
    ctrl_actor_name: str = ""


class ExitData(BaseModel):
    response: bool = False
    user_name: str = ""
    game_name: str = ""
    ctrl_actor_name: str = ""


class ExecuteData(BaseModel):
    response: bool = False
    error: str = ""
    user_name: str = ""
    game_name: str = ""
    ctrl_actor_name: str = ""
    user_input: List[str] = []
    messages: List[str] = []


class WatchData(BaseModel):
    response: bool = False
    user_name: str = ""
    game_name: str = ""
    ctrl_actor_name: str = ""
    message: str = ""


class CheckData(BaseModel):
    response: bool = False
    user_name: str = ""
    game_name: str = ""
    ctrl_actor_name: str = ""
    message: str = ""
