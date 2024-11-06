from dataclasses import dataclass
from enum import Enum
from pydantic import BaseModel
from typing import Dict, Set, List, Optional, Final
from my_models.entity_models import GameModel
from my_models.config_models import APIRoutesConfigModel, GenGamesConfigModel
from my_models.player_models import (
    WatchActionModel,
    CheckActionModel,
    RetrieveActorArchivesModel,
    RetrieveStageArchivesActionModel,
    PlayerClientMessage,
)

# from loguru import logger


@dataclass
class WS_CONFIG:
    LOCAL_HOST: Final[str] = "127.0.0.1"
    PORT: Final[int] = 8080
    FETCH_MESSAGES_COUNT: Final[int] = 9999  # 多要一点得了。


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


class GameStateManager:

    def __init__(self, game_stage: GameState) -> None:

        self._state: GameState = game_stage

        self._transition_protocol: Dict[GameState, Set[GameState]] = {
            GameState.UNLOGGED: {GameState.LOGGED_IN},
            GameState.LOGGED_IN: {GameState.GAME_CREATED},
            GameState.GAME_CREATED: {GameState.GAME_JOINED},
            GameState.GAME_JOINED: {GameState.PLAYING},
            GameState.PLAYING: {GameState.REQUESTING_EXIT},
            GameState.REQUESTING_EXIT: {GameState.UNLOGGED},
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
class APIRoutesConfigRequest(BaseModel):
    content: str = ""


class APIRoutesConfigResponse(BaseModel):
    content: str = ""
    api_routes: APIRoutesConfigModel = APIRoutesConfigModel()
    error: int = 0
    message: str = ""


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class LoginRequest(BaseModel):
    user_name: str = ""


class LoginResponse(BaseModel):
    user_name: str = ""
    game_config: GenGamesConfigModel = GenGamesConfigModel()
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
    total: int = 0
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
    total: int = 0
    game_round: int = 0
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
    count: int = 1


class FetchMessagesResponse(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    messages: List[PlayerClientMessage] = []
    total: int = 0
    game_round: int = 0
    error: int = 0
    message: str = ""


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################


class RetrieveActorArchivesRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""


class RetrieveActorArchivesResponse(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    action_model: RetrieveActorArchivesModel = RetrieveActorArchivesModel()
    error: int = 0
    message: str = ""


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################


class RetrieveStageArchivesRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""


class RetrieveStageArchivesResponse(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    action_model: RetrieveStageArchivesActionModel = RetrieveStageArchivesActionModel()
    error: int = 0
    message: str = ""


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
