from enum import Enum
from pydantic import BaseModel
from typing import Dict, Set, List, Optional, Final
from my_data.model_def import GameModel, WatchActionModel, CheckActionModel
from my_data.model_def import PlayerClientMessage


class WS_CONFIG:
    LOCAL_HOST: Final[str] = "127.0.0.1"
    PORT: Final[int] = 8080
    SEND_MESSAGES_COUNT: Final[int] = 20


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
class LoginRequest(BaseModel):
    user_name: str = ""


class LoginResponse(BaseModel):
    user_name: str = ""
    game_list: List[str] = []
    error: int = 0
    message: str = ""


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class CreateRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""


class CreateResponse(BaseModel):
    user_name: str = ""
    game_name: str = ""
    selectable_actors: List[str] = []
    game_model: Optional[GameModel] = None
    error: int = 0
    message: str = ""


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################


class JoinRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""


class JoinResponse(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    error: int = 0
    message: str = ""


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################


class StartRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""


class StartResponse(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    error: int = 0
    message: str = ""


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################


class ExitRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""


class ExitResponse(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    error: int = 0
    message: str = ""


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################


class ExecuteRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    user_input: List[str] = []


class ExecuteResponse(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    player_input_enable: bool = False
    error: int = 0
    message: str = ""


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################


class WatchRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""


class WatchResponse(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    action_model: WatchActionModel = WatchActionModel()
    error: int = 0
    message: str = ""


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################


class CheckRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""


class CheckResponse(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    action_model: CheckActionModel = CheckActionModel()
    error: int = 0
    message: str = ""


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################


class FetchMessagesRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    index: int = 0
    count: int = 10


class FetchMessagesResponse(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    messages: List[PlayerClientMessage] = []
    total: int = 0
    error: int = 0
    message: str = ""


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
