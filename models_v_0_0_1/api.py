from typing import Dict, List, final
from pydantic import BaseModel
from .client_message import ClientMessage
from .registry import register_base_model_class
from .dungeon import Dungeon
from .snapshot import EntitySnapshot


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
    HOME_GAMEPLAY_URL: str = ""
    HOME_TRANS_DUNGEON_URL: str = ""
    DUNGEON_GAMEPLAY_URL: str = ""
    DUNGEON_TRANS_HOME_URL: str = ""
    VIEW_HOME_URL: str = ""
    VIEW_DUNGEON_URL: str = ""
    VIEW_ACTOR_URL: str = ""


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
    actor_name: str = ""


@final
@register_base_model_class
class LoginResponse(BaseModel):
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
class HomeTransDungeonRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""


@final
@register_base_model_class
class HomeTransDungeonResponse(BaseModel):
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################
@final
@register_base_model_class
class DungeonTransHomeRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""


@final
@register_base_model_class
class DungeonTransHomeResponse(BaseModel):
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


@final
@register_base_model_class
class HomeGamePlayRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    user_input: str = ""


@final
@register_base_model_class
class HomeGamePlayResponse(BaseModel):
    client_messages: List[ClientMessage] = []
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


@final
@register_base_model_class
class DungeonGamePlayUserInput(BaseModel):
    tag: str = ""


@final
@register_base_model_class
class DungeonGamePlayRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    user_input: DungeonGamePlayUserInput = DungeonGamePlayUserInput()


@final
@register_base_model_class
class DungeonGamePlayResponse(BaseModel):
    client_messages: List[ClientMessage] = []
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


@final
@register_base_model_class
class ViewDungeonRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""


@final
@register_base_model_class
class ViewDungeonResponse(BaseModel):
    mapping: Dict[str, List[str]] = {}
    dungeon: Dungeon = Dungeon(name="")
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


@final
@register_base_model_class
class ViewHomeRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""


@final
@register_base_model_class
class ViewHomeResponse(BaseModel):
    mapping: Dict[str, List[str]] = {}
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


@final
@register_base_model_class
class ViewActorRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actors: List[str] = []


@final
@register_base_model_class
class ViewActorResponse(BaseModel):
    actor_snapshots: List[EntitySnapshot] = []
    error: int = 0
    message: str = ""


################################################################################################################
################################################################################################################
################################################################################################################
