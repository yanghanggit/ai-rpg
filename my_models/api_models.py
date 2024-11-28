from pydantic import BaseModel, Field
from typing import List, Optional
from my_models.entity_models import GameModel
from my_models.config_models import APIEndpointsConfigModel, GlobalConfigModel
from my_models.player_models import (
    SurveyStageModel,
    StatusInventoryCheckModel,
    RetrieveActorArchivesModel,
    RetrieveStageArchivesActionModel,
    PlayerClientMessage,
)


###############################################################################################################################################
class APIEndpointsConfigRequest(BaseModel):
    content: str = ""


class APIEndpointsConfigResponse(BaseModel):
    content: str = ""
    api_endpoints: APIEndpointsConfigModel = Field(
        default_factory=APIEndpointsConfigModel
    )
    error: int = 0
    message: str = ""


###############################################################################################################################################
class LoginRequest(BaseModel):
    user_name: str = ""


class LoginResponse(BaseModel):
    user_name: str = ""
    global_config: GlobalConfigModel = Field(default_factory=GlobalConfigModel)
    error: int = 0
    message: str = ""


###############################################################################################################################################
class CreateRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""


class CreateResponse(BaseModel):
    user_name: str = ""
    game_name: str = ""
    selectable_actors: List[str] = []
    game_model: Optional[GameModel] = Field(default_factory=lambda: None)
    error: int = 0
    message: str = ""


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
class ExecuteRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    user_input: List[str] = []


class ExecuteResponse(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    turn_player_actor: str = ""
    total: int = 0
    game_round: int = 0
    error: int = 0
    message: str = ""


###############################################################################################################################################
class SurveyStageRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""


class SurveyStageResponse(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    action_model: SurveyStageModel = Field(default_factory=SurveyStageModel)
    error: int = 0
    message: str = ""


###############################################################################################################################################
class StatusInventoryCheckRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""


class StatusInventoryCheckResponse(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    action_model: StatusInventoryCheckModel = Field(
        default_factory=StatusInventoryCheckModel
    )
    error: int = 0
    message: str = ""


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
class RetrieveActorArchivesRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""


class RetrieveActorArchivesResponse(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    action_model: RetrieveActorArchivesModel = Field(
        default_factory=RetrieveActorArchivesModel
    )
    error: int = 0
    message: str = ""


###############################################################################################################################################
class RetrieveStageArchivesRequest(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""


class RetrieveStageArchivesResponse(BaseModel):
    user_name: str = ""
    game_name: str = ""
    actor_name: str = ""
    action_model: RetrieveStageArchivesActionModel = Field(
        default_factory=RetrieveStageArchivesActionModel
    )
    error: int = 0
    message: str = ""


###############################################################################################################################################
