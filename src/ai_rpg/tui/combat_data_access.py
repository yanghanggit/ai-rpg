"""战斗房间相关 Screen 共用的数据获取入口。

统一封装「session is None → mock 固定数据」/「否则 → 真实 fetch_* 调用」的分支判断，
避免每个 Screen 重复实现同一套判断逻辑。所有函数返回的类型与真实服务端响应完全一致
（DungeonRoomResponse / StagesStateResponse / EntitiesDetailsResponse），
调用方无需关心数据来源。
"""

from typing import List, Tuple

from ..models import (
    DungeonRoomResponse,
    DungeonStateResponse,
    EntitiesDetailsResponse,
    StagesStateResponse,
)
from .app import GameClient
from .mock_data import (
    MOCK_ACTOR_NAME,
    MOCK_GAME_NAME,
    MOCK_USER_NAME,
    build_mock_dungeon_room_response,
    build_mock_dungeon_state_response,
    build_mock_entities_details_response,
    build_mock_stages_state_response,
)
from .server_client import (
    fetch_dungeon_room,
    fetch_dungeon_state,
    fetch_entities_details,
    fetch_stages_state,
)


###############################################################################################################################################
def is_mock_mode(game_client: GameClient) -> bool:
    """`--dev-screen combat-room` 跳过登录时 session 为 None，此时走固定 mock 数据。"""
    return game_client.session is None


###############################################################################################################################################
def resolve_identity(game_client: GameClient) -> Tuple[str, str, str]:
    """返回 (user_name, game_name, actor_name)；mock 模式下使用固定身份。"""
    if is_mock_mode(game_client):
        return MOCK_USER_NAME, MOCK_GAME_NAME, MOCK_ACTOR_NAME
    session = game_client.session
    assert session is not None
    return session.user_name, session.game_name, session.actor_name


###############################################################################################################################################
async def get_dungeon_room(game_client: GameClient) -> DungeonRoomResponse:
    """获取当前地下城房间（战斗房间）。"""
    if is_mock_mode(game_client):
        return build_mock_dungeon_room_response()
    user_name, game_name, _ = resolve_identity(game_client)
    return await fetch_dungeon_room(user_name, game_name)


###############################################################################################################################################
async def get_dungeon_state(game_client: GameClient) -> DungeonStateResponse:
    """获取当前地下城完整状态（含 rooms 列表与 current_room_index，用于判断是否存在下一关）。"""
    if is_mock_mode(game_client):
        return build_mock_dungeon_state_response()
    user_name, game_name, _ = resolve_identity(game_client)
    return await fetch_dungeon_state(user_name, game_name)


###############################################################################################################################################
async def get_stages_state(game_client: GameClient) -> StagesStateResponse:
    """获取场景 → 角色分布映射。"""
    if is_mock_mode(game_client):
        return build_mock_stages_state_response()
    user_name, game_name, _ = resolve_identity(game_client)
    return await fetch_stages_state(user_name, game_name)


###############################################################################################################################################
async def get_entities_details(
    game_client: GameClient, entity_names: List[str]
) -> EntitiesDetailsResponse:
    """批量获取实体详情。"""
    if is_mock_mode(game_client):
        return build_mock_entities_details_response(entity_names)
    user_name, game_name, _ = resolve_identity(game_client)
    return await fetch_entities_details(user_name, game_name, entity_names)
