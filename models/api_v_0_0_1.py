from typing import Final, List
from pydantic import BaseModel
from models.client_message_v_0_0_1 import ClientMessage

# 注意，不允许动！
SCHEMA_VERSION: Final[str] = "0.0.1"


################################################################################################################
################################################################################################################
################################################################################################################
class APIEndpointConfigurationRequest(BaseModel):
    pass


class APIEndpointConfiguration(BaseModel):
    TEST_URL: str = ""
    LOGIN_URL: str = ""
    LOGOUT_URL: str = ""
    START_URL: str = ""
    HOME_RUN_URL: str = ""
    HOME_TRANS_DUNGEON_URL: str = ""
    DUNGEON_RUN_URL: str = ""
    DUNGEON_DRAW_CARDS_URL: str = ""


class APIEndpointConfigurationResponse(BaseModel):
    content: str = ""
    api_endpoints: APIEndpointConfiguration = APIEndpointConfiguration()
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


class LoginRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""


class LoginResponse(BaseModel):
    actor: str = ""
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


class LogoutRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""


class LogoutResponse(BaseModel):
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


class StartRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""


class StartResponse(BaseModel):
    client_messages: List[ClientMessage] = []
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


class HomeRunRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    user_input: str = ""


class HomeRunResponse(BaseModel):
    client_messages: List[ClientMessage] = []
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


class HomeTransDungeonRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""


class HomeTransDungeonResponse(BaseModel):
    client_messages: List[ClientMessage] = []
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


class DungeonRunRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    user_input: str = ""


class DungeonRunResponse(BaseModel):
    client_messages: List[ClientMessage] = []
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


class DungeonDrawCardsRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    user_input: str = ""


class DungeonDrawCardsResponse(BaseModel):
    client_messages: List[ClientMessage] = []
    error: int = 0
    message: str = ""
