from typing import List, List
from pydantic import BaseModel
from enum import StrEnum
from my_models.event_models import BaseAgentEvent
from my_models.file_models import ActorArchiveFileModel, StageArchiveFileModel


class PlayerClientMessageTag(StrEnum):
    SYSTEM = "SYSTEM"
    ACTOR = "ACTOR"
    STAGE = "STAGE"
    KICKOFF = "KICKOFF"
    TIP = "TIP"


class PlayerClientMessage(BaseModel):
    tag: str
    sender: str
    index: int = 0
    agent_event: BaseAgentEvent  # 要根部的类，其实只需要它的序列化能力，其余的不要，所以不要出现具体类型的调用！


class PlayerProxyModel(BaseModel):
    name: str = ""
    client_messages: List[PlayerClientMessage] = []
    cache_kickoff_messages: List[PlayerClientMessage] = []
    over: bool = False
    actor_name: str = ""


class WatchActionModel(BaseModel):
    content: str = ""


class CheckActionModel(BaseModel):
    content: str = ""


class GetActorArchivesActionModel(BaseModel):
    message: str = ""
    archives: List[ActorArchiveFileModel] = []


class GetStageArchivesActionModel(BaseModel):
    message: str = ""
    archives: List[StageArchiveFileModel] = []
