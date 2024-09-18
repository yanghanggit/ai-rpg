from enum import Enum
from pydantic import BaseModel
from typing import Dict, Set


class WS_CONFIG(Enum):
    Host = "127.0.0.1"
    Port = 8080


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################


class GameState(Enum):
    NOTHING = 0
    LOGIN = 1
    WAIT = 2
    CREATE = 3
    JOIN = 4
    START = 5
    EXIT = 6


class GameStageManager:

    def __init__(self) -> None:
        self._state: GameState = GameState.NOTHING

        self._stage_transition: Dict[GameState, Set[GameState]] = {
            GameState.NOTHING: {GameState.LOGIN},
            GameState.LOGIN: {GameState.WAIT},
            GameState.WAIT: {GameState.CREATE},
            GameState.CREATE: {GameState.JOIN},
            GameState.JOIN: {GameState.START},
            GameState.START: {GameState.EXIT},
            GameState.EXIT: {GameState.WAIT},
        }

    def can_transition(self, src: GameState, dst: GameState) -> bool:
        return dst in self._stage_transition[src]

    def set_state(self, state: GameState) -> None:
        self._state = state

    def transition(self, dst: GameState) -> None:
        if self.can_transition(self._state, dst):
            self._state = dst
        else:
            raise ValueError(f"Can't transition from {self._state} to {dst}")


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class LoginData(BaseModel):
    username: str
    response: str = ""
