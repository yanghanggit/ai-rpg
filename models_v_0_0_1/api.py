from typing import List, final
from pydantic import BaseModel
from .client_message import ClientMessage
from .registry import register_base_model_class


################################################################################################################
################################################################################################################
################################################################################################################
@final
@register_base_model_class
class APIEndpointConfigurationRequest(BaseModel):
    pass


@final
@register_base_model_class
class APIEndpointConfiguration(BaseModel):
    TEST_URL: str = ""
    LOGIN_URL: str = ""
    LOGOUT_URL: str = ""
    START_URL: str = ""
    HOME_RUN_URL: str = ""
    HOME_TRANS_DUNGEON_URL: str = ""
    DUNGEON_RUN_URL: str = ""
    DUNGEON_DRAW_CARDS_URL: str = ""


@final
@register_base_model_class
class APIEndpointConfigurationResponse(BaseModel):
    content: str = ""
    api_endpoints: APIEndpointConfiguration = APIEndpointConfiguration()
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


@final
@register_base_model_class
class LoginRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""


@final
@register_base_model_class
class LoginResponse(BaseModel):
    actor: str = ""
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


@final
@register_base_model_class
class LogoutRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""


@final
@register_base_model_class
class LogoutResponse(BaseModel):
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


@final
@register_base_model_class
class StartRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""


@final
@register_base_model_class
class StartResponse(BaseModel):
    client_messages: List[ClientMessage] = []
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


@final
@register_base_model_class
class HomeRunRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    user_input: str = ""


@final
@register_base_model_class
class HomeRunResponse(BaseModel):
    client_messages: List[ClientMessage] = []
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


@final
@register_base_model_class
class HomeTransDungeonRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""


@final
@register_base_model_class
class HomeTransDungeonResponse(BaseModel):
    client_messages: List[ClientMessage] = []
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


@final
@register_base_model_class
class DungeonRunRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    user_input: str = ""


@final
@register_base_model_class
class DungeonRunResponse(BaseModel):
    client_messages: List[ClientMessage] = []
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


@final
@register_base_model_class
class DungeonDrawCardsRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    user_input: str = ""


@final
@register_base_model_class
class DungeonDrawCardsResponse(BaseModel):
    client_messages: List[ClientMessage] = []
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################
