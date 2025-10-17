from typing import Dict, List, final
from pydantic import BaseModel
from .client_message import ClientMessage


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
    client_messages: List[ClientMessage]


@final
class WerewolfGameStateResponse(BaseModel):
    message: str
