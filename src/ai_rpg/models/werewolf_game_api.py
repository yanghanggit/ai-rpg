from typing import Dict, List, final
from pydantic import BaseModel
from .session_message import SessionMessage
from ..models import EntitySerialization


@final
class WerewolfGameStartRequest(BaseModel):
    user_name: str
    game_name: str


@final
class WerewolfGameStartResponse(BaseModel):
    message: str


@final
class WerewolfGamePlayRequest(BaseModel):
    user_name: str
    game_name: str
    data: Dict[str, str]


@final
class WerewolfGamePlayResponse(BaseModel):
    session_messages: List[SessionMessage]


@final
class WerewolfGameStateResponse(BaseModel):
    mapping: Dict[str, List[str]]
    game_time: int


@final
class WerewolfGameActorDetailsResponse(BaseModel):
    actor_entities_serialization: List[EntitySerialization]
