from datetime import datetime
from enum import StrEnum, unique
from typing import Dict, List, final

from pydantic import BaseModel

from .blueprint import Blueprint
from .dungeon import AnyDungeonRoom, Dungeon
from .player_session import PlayerSession
from .serialization import EntitySerialization
from .session_message import SessionMessage
from .task import TaskStatusView


@final
class LoginRequest(BaseModel):
    user_name: str
    game_name: str


@final
class LoginResponse(BaseModel):
    message: str


################################################################################################################
################################################################################################################
################################################################################################################


@final
class LogoutRequest(BaseModel):
    user_name: str
    game_name: str


@final
class LogoutResponse(BaseModel):
    message: str


################################################################################################################
################################################################################################################
################################################################################################################


@final
class NewGameRequest(BaseModel):
    user_name: str
    game_name: str


@final
class NewGameResponse(BaseModel):
    blueprint: Blueprint
    player_session: PlayerSession


################################################################################################################
################################################################################################################
################################################################################################################


@final
class HomeAdvanceRequest(BaseModel):
    user_name: str
    game_name: str
    actors: List[str] = []


@final
class HomeAdvanceResponse(BaseModel):
    job_id: int
    message: str


################################################################################################################
################################################################################################################
################################################################################################################


@final
class HomeEnterDungeonRequest(BaseModel):
    user_name: str
    game_name: str
    dungeon_name: str


@final
class HomeEnterDungeonResponse(BaseModel):
    message: str


################################################################################################################
################################################################################################################
################################################################################################################
@final
class HomeGenerateDungeonRequest(BaseModel):
    user_name: str
    game_name: str


@final
class HomeGenerateDungeonResponse(BaseModel):
    job_id: int
    message: str


################################################################################################################
################################################################################################################
################################################################################################################
@final
class HomeRosterAddRequest(BaseModel):
    user_name: str
    game_name: str
    member_name: str


@final
class HomeRosterAddResponse(BaseModel):
    message: str


################################################################################################################
################################################################################################################
################################################################################################################
@final
class HomeRosterRemoveRequest(BaseModel):
    user_name: str
    game_name: str
    member_name: str


@final
class HomeRosterRemoveResponse(BaseModel):
    message: str


################################################################################################################
################################################################################################################
################################################################################################################
@final
class HomeItemMoveToInventoryRequest(BaseModel):
    user_name: str
    game_name: str
    item_names: List[str]


@final
class HomeItemMoveToInventoryResponse(BaseModel):
    message: str


################################################################################################################
################################################################################################################
################################################################################################################
@final
class HomeItemMoveToStorageRequest(BaseModel):
    user_name: str
    game_name: str
    item_names: List[str]


@final
class HomeItemMoveToStorageResponse(BaseModel):
    message: str


################################################################################################################
################################################################################################################
################################################################################################################
@final
class HomeWearCostumeRequest(BaseModel):
    user_name: str
    game_name: str
    item_name: str
    target_name: str


@final
class HomeWearCostumeResponse(BaseModel):
    job_id: int
    message: str


################################################################################################################
################################################################################################################
################################################################################################################
@final
class HomeRemoveCostumeRequest(BaseModel):
    user_name: str
    game_name: str
    target_name: str


@final
class HomeRemoveCostumeResponse(BaseModel):
    job_id: int
    message: str


################################################################################################################
################################################################################################################
################################################################################################################
@final
class HomeCraftItemRequest(BaseModel):
    user_name: str
    game_name: str
    materials: List[str]


@final
class HomeCraftItemResponse(BaseModel):
    job_id: int
    message: str


################################################################################################################
################################################################################################################
################################################################################################################
@final
class DungeonExitRequest(BaseModel):
    user_name: str
    game_name: str


@final
class DungeonExitResponse(BaseModel):
    job_id: int
    message: str


################################################################################################################
@final
class DungeonCombatCollectLootRequest(BaseModel):
    user_name: str
    game_name: str


@final
class DungeonCombatCollectLootResponse(BaseModel):
    message: str


################################################################################################################
################################################################################################################
################################################################################################################


@final
@unique
class HomePlayerActionType(StrEnum):
    SPEAK = "/speak"
    SWITCH_STAGE = "/switch_stage"


@final
class HomePlayerActionRequest(BaseModel):
    user_name: str
    game_name: str
    action: HomePlayerActionType
    arguments: Dict[str, str]


@final
class HomePlayerActionResponse(BaseModel):
    job_id: int
    message: str


################################################################################################################
################################################################################################################
################################################################################################################


@final
class DungeonCombatRetreatRequest(BaseModel):
    user_name: str
    game_name: str


@final
class DungeonCombatRetreatResponse(BaseModel):
    job_id: int
    message: str


################################################################################################################
################################################################################################################
################################################################################################################


@final
class DungeonAdvanceStageRequest(BaseModel):
    user_name: str
    game_name: str


@final
class DungeonAdvanceStageResponse(BaseModel):
    message: str


################################################################################################################
################################################################################################################
################################################################################################################


@final
class DungeonCombatInitRequest(BaseModel):
    user_name: str
    game_name: str


@final
class DungeonCombatInitResponse(BaseModel):
    job_id: int
    message: str


################################################################################################################
################################################################################################################
################################################################################################################


@final
class DungeonCombatPlayCardsRequest(BaseModel):
    user_name: str
    game_name: str
    actor_name: str
    card_name: str
    targets: List[str] = []


@final
class DungeonCombatPlayCardsResponse(BaseModel):
    job_id: int
    message: str


@final
class DungeonCombatPassTurnRequest(BaseModel):
    user_name: str
    game_name: str
    actor_name: str


@final
class DungeonCombatPassTurnResponse(BaseModel):
    job_id: int
    message: str


@final
class DungeonCombatUseConsumableItemRequest(BaseModel):
    user_name: str
    game_name: str
    item_name: str
    targets: List[str] = []


@final
class DungeonCombatUseConsumableItemResponse(BaseModel):
    job_id: int
    message: str


@final
class DungeonCombatEquipGearItemRequest(BaseModel):
    user_name: str
    game_name: str
    item_name: str


@final
class DungeonCombatEquipGearItemResponse(BaseModel):
    job_id: int
    message: str


################################################################################################################
################################################################################################################
################################################################################################################


@final
class DungeonOpeningInitRequest(BaseModel):
    user_name: str
    game_name: str


@final
class DungeonOpeningInitResponse(BaseModel):
    job_id: int
    message: str


@final
class DungeonOpeningGenerateCardPoolRequest(BaseModel):
    user_name: str
    game_name: str


@final
class DungeonOpeningGenerateCardPoolResponse(BaseModel):
    job_id: int
    message: str


@final
class DungeonOpeningPickCardFromPoolRequest(BaseModel):
    user_name: str
    game_name: str
    actor_name: str
    card_name: str


@final
class DungeonOpeningPickCardFromPoolResponse(BaseModel):
    job_id: int
    message: str


################################################################################################################
################################################################################################################
################################################################################################################


@final
class DungeonCombatDrawCardsRequest(BaseModel):
    user_name: str
    game_name: str


@final
class DungeonCombatDrawCardsResponse(BaseModel):
    job_id: int
    message: str


################################################################################################################
################################################################################################################
################################################################################################################


@final
class DungeonStateResponse(BaseModel):
    dungeon: Dungeon


################################################################################################################
################################################################################################################
################################################################################################################


@final
class DungeonRoomResponse(BaseModel):
    room: AnyDungeonRoom


################################################################################################################
################################################################################################################
################################################################################################################


@final
class StagesStateResponse(BaseModel):
    mapping: Dict[str, List[str]]


################################################################################################################
################################################################################################################
################################################################################################################


@final
class EntitiesDetailsResponse(BaseModel):
    entities: List[EntitySerialization]


################################################################################################################
################################################################################################################
################################################################################################################


@final
class SessionMessageResponse(BaseModel):
    session_messages: List[SessionMessage]


################################################################################################################
################################################################################################################
################################################################################################################


@final
class TasksStatusResponse(BaseModel):
    tasks: List[TaskStatusView]


@final
class ApiRouteInfo(BaseModel):
    """已注册路由的摘要信息（根路由自描述用）"""

    path: str
    name: str
    methods: List[str]
    tags: List[str]


@final
class ServerInfoResponse(BaseModel):
    """根路由响应：服务自描述信息

    有了这个 response_model，OpenAPI 才能生成具体字段，前端无需再手写收窄层。
    """

    service: str
    base_url: str
    description: str
    status: str
    timestamp: datetime
    version: str
    routes: List[ApiRouteInfo]


################################################################################################################
################################################################################################################
################################################################################################################


@final
class BlueprintListResponse(BaseModel):
    blueprints: List[Blueprint]


################################################################################################################
################################################################################################################
################################################################################################################


@final
class DungeonListResponse(BaseModel):
    dungeons: List[Dungeon]


################################################################################################################
################################################################################################################
################################################################################################################
@final
class CompactContextRequest(BaseModel):
    user_name: str
    game_name: str
    target_name: str


@final
class CompactContextResponse(BaseModel):
    job_id: int
    message: str
