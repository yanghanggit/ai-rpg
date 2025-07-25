from typing import Dict, List, final
from pydantic import BaseModel
from .client_message import ClientMessage

# from .registry import register_base_model_class
from .dungeon import Dungeon
from .snapshot import EntitySnapshot
from .world import AgentShortTermMemory


################################################################################################################
################################################################################################################
################################################################################################################


@final
# @register_base_model_class
class URLConfigurationResponse(BaseModel):
    api_version: str = ""
    endpoints: Dict[str, str] = {}
    deprecated: bool = False
    notice: str = ""


################################################################################################################
################################################################################################################
################################################################################################################


@final
# @register_base_model_class
class LoginRequest(BaseModel):
    user_name: str
    game_name: str


@final
# @register_base_model_class
class LoginResponse(BaseModel):
    message: str


################################################################################################################
################################################################################################################
################################################################################################################


@final
# @register_base_model_class
class LogoutRequest(BaseModel):
    user_name: str
    game_name: str


@final
# @register_base_model_class
class LogoutResponse(BaseModel):
    message: str


################################################################################################################
################################################################################################################
################################################################################################################


@final
# @register_base_model_class
class StartRequest(BaseModel):
    user_name: str
    game_name: str
    actor_name: str


@final
# @register_base_model_class
class StartResponse(BaseModel):
    message: str


################################################################################################################
################################################################################################################
################################################################################################################


@final
# @register_base_model_class
class HomeTransDungeonRequest(BaseModel):
    user_name: str
    game_name: str


@final
# @register_base_model_class
class HomeTransDungeonResponse(BaseModel):
    message: str


################################################################################################################
################################################################################################################
################################################################################################################
@final
# @register_base_model_class
class DungeonTransHomeRequest(BaseModel):
    user_name: str
    game_name: str


@final
# @register_base_model_class
class DungeonTransHomeResponse(BaseModel):
    message: str


################################################################################################################
################################################################################################################
################################################################################################################


@final
# @register_base_model_class
class HomeGamePlayUserInput(BaseModel):
    tag: str
    data: Dict[str, str]


@final
# @register_base_model_class
class HomeGamePlayRequest(BaseModel):
    user_name: str
    game_name: str
    user_input: HomeGamePlayUserInput


@final
# @register_base_model_class
class HomeGamePlayResponse(BaseModel):
    client_messages: List[ClientMessage]


################################################################################################################
################################################################################################################
################################################################################################################


@final
# @register_base_model_class
class DungeonGamePlayUserInput(BaseModel):
    tag: str
    data: Dict[str, str]


@final
# @register_base_model_class
class DungeonGamePlayRequest(BaseModel):
    user_name: str
    game_name: str
    user_input: DungeonGamePlayUserInput


@final
# @register_base_model_class
class DungeonGamePlayResponse(BaseModel):
    client_messages: List[ClientMessage]


################################################################################################################
################################################################################################################
################################################################################################################


@final
# @register_base_model_class
class ViewDungeonResponse(BaseModel):
    mapping: Dict[str, List[str]]
    dungeon: Dungeon


################################################################################################################
################################################################################################################
################################################################################################################


@final
# @register_base_model_class
class ViewHomeResponse(BaseModel):
    mapping: Dict[str, List[str]]


################################################################################################################
################################################################################################################
################################################################################################################


@final
# @register_base_model_class
class ViewActorResponse(BaseModel):
    actor_snapshots: List[EntitySnapshot]
    agent_short_term_memories: List[AgentShortTermMemory]


################################################################################################################
################################################################################################################
################################################################################################################
