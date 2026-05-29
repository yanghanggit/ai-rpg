"""游戏服务器 HTTP 客户端（TUI 客户端专用）"""

import json
from typing import Any, Dict, List, cast

import httpx

from ..models import (
    BlueprintListResponse,
    DungeonCombatDrawCardsRequest,
    DungeonCombatDrawCardsResponse,
    DungeonCombatInitRequest,
    DungeonCombatInitResponse,
    DungeonCombatPlayCardsRequest,
    DungeonCombatPlayCardsResponse,
    DungeonCombatResponse,
    DungeonCombatRetreatRequest,
    DungeonCombatRetreatResponse,
    DungeonExitRequest,
    DungeonExitResponse,
    DungeonListResponse,
    DungeonRoomResponse,
    DungeonStateResponse,
    EntitiesDetailsResponse,
    HomeAdvanceRequest,
    HomeAdvanceResponse,
    HomeEnterDungeonRequest,
    HomeEnterDungeonResponse,
    HomeGenerateDungeonRequest,
    HomeGenerateDungeonResponse,
    HomePlayerActionRequest,
    HomePlayerActionResponse,
    HomePlayerActionType,
    HomeRosterAddRequest,
    HomeRosterAddResponse,
    HomeRosterRemoveRequest,
    HomeRosterRemoveResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    NewGameRequest,
    NewGameResponse,
    SessionMessageResponse,
    StagesStateResponse,
    TaskRecord,
    TasksStatusResponse,
    TaskStatus,
)
from .config import server_config


class TaskFailedError(Exception):
    """后台任务执行失败时抛出。"""

    pass


async def fetch_server_info() -> Dict[str, Any]:
    """请求游戏服务器根路由，返回服务信息 JSON。"""
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(server_config.base_url + "/")
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())


async def login(user_name: str, game_name: str) -> str:
    """登录游戏服务器，返回服务器响应消息。"""
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.post(
            server_config.base_url + "/api/login/v1/",
            json=LoginRequest(user_name=user_name, game_name=game_name).model_dump(),
        )
        response.raise_for_status()
        return LoginResponse.model_validate(response.json()).message


async def new_game(user_name: str, game_name: str) -> NewGameResponse:
    """创建新游戏，返回服务器响应。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            server_config.base_url + "/api/game/new/v1/",
            json=NewGameRequest(user_name=user_name, game_name=game_name).model_dump(),
        )
        response.raise_for_status()
        return NewGameResponse.model_validate(response.json())


async def fetch_stages_state(user_name: str, game_name: str) -> StagesStateResponse:
    """查询场景状态，返回场景与角色的分布映射。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            server_config.base_url + f"/api/stages/v1/{user_name}/{game_name}/state",
        )
        response.raise_for_status()
        return StagesStateResponse.model_validate(response.json())


async def logout(user_name: str, game_name: str) -> str:
    """登出游戏服务器，返回服务器响应消息。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            server_config.base_url + "/api/logout/v1/",
            json=LogoutRequest(user_name=user_name, game_name=game_name).model_dump(),
        )
        response.raise_for_status()
        return LogoutResponse.model_validate(response.json()).message


async def fetch_blueprint_list() -> BlueprintListResponse:
    """获取可用蓝图列表。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            server_config.base_url + "/api/game/blueprint-list/v1/",
        )
        response.raise_for_status()
        return BlueprintListResponse.model_validate(response.json())


async def fetch_session_messages(
    user_name: str, game_name: str, last_sequence_id: int
) -> SessionMessageResponse:
    """增量获取玩家会话消息。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            server_config.base_url
            + f"/api/session_messages/v1/{user_name}/{game_name}/since",
            params={"last_sequence_id": last_sequence_id},
        )
        response.raise_for_status()
        return SessionMessageResponse.model_validate(response.json())


async def fetch_entities_details(
    user_name: str, game_name: str, entity_names: List[str]
) -> EntitiesDetailsResponse:
    """批量查询实体详情。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            server_config.base_url
            + f"/api/entities/v1/{user_name}/{game_name}/details",
            params={"entities": entity_names},
        )
        response.raise_for_status()
        return EntitiesDetailsResponse.model_validate(response.json())


async def fetch_dungeon_list() -> DungeonListResponse:
    """获取可用地下城列表。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            server_config.base_url + "/api/home/dungeon-list/v1/",
        )
        response.raise_for_status()
        return DungeonListResponse.model_validate(response.json())


async def fetch_tasks_status(task_ids: List[str]) -> TasksStatusResponse:
    """批量查询后台任务状态。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            server_config.base_url + "/api/tasks/v1/status",
            params={"task_ids": task_ids},
        )
        response.raise_for_status()
        return TasksStatusResponse.model_validate(response.json())


async def watch_task_until_done(task_id: str, timeout_seconds: int = 120) -> TaskRecord:
    """通过 SSE 等待后台任务完成，返回终态 TaskRecord。

    Args:
        task_id: 要监听的任务 ID
        timeout_seconds: 最大等待秒数（同时透传给服务端 SSE 生成器）

    Returns:
        TaskRecord: 状态为 COMPLETED 的任务记录

    Raises:
        TaskFailedError: 任务失败（status=FAILED 或服务端返回 error 字段）
        TimeoutError: 等待超时
    """
    url = server_config.base_url + f"/api/tasks/v1/watch/{task_id}"
    params = {"timeout_seconds": timeout_seconds}
    timeout = httpx.Timeout(
        connect=10.0,
        read=float(timeout_seconds + 15),
        write=10.0,
        pool=10.0,
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("GET", url, params=params) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if not payload:
                    continue
                data = json.loads(payload)
                record = TaskRecord.model_validate(data)
                if record.status == TaskStatus.FAILED:
                    raise TaskFailedError(record.error or "未知错误")
                if record.status == TaskStatus.COMPLETED:
                    return record
    raise TimeoutError(f"任务 {task_id} 等待超时")


async def home_advance(user_name: str, game_name: str) -> HomeAdvanceResponse:
    """触发家园推进流程，返回后台任务ID。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            server_config.base_url + "/api/home/advance/v1/",
            json=HomeAdvanceRequest(
                user_name=user_name,
                game_name=game_name,
                actors=[],
            ).model_dump(),
        )
        response.raise_for_status()
        return HomeAdvanceResponse.model_validate(response.json())


async def home_enter_dungeon(
    user_name: str, game_name: str, dungeon_name: str
) -> HomeEnterDungeonResponse:
    """传送玩家进入指定地下城（同步，无后台任务）。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            server_config.base_url + "/api/home/enter_dungeon/v1/",
            json=HomeEnterDungeonRequest(
                user_name=user_name,
                game_name=game_name,
                dungeon_name=dungeon_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return HomeEnterDungeonResponse.model_validate(response.json())


async def fetch_dungeon_state(user_name: str, game_name: str) -> DungeonStateResponse:
    """查询当前地下城完整状态。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            server_config.base_url + f"/api/dungeons/v1/{user_name}/{game_name}/state",
        )
        response.raise_for_status()
        return DungeonStateResponse.model_validate(response.json())


async def fetch_dungeon_room(user_name: str, game_name: str) -> DungeonRoomResponse:
    """查询当前地下城房间（含 stage + combat）。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            server_config.base_url + f"/api/dungeons/v1/{user_name}/{game_name}/room",
        )
        response.raise_for_status()
        return DungeonRoomResponse.model_validate(response.json())


async def fetch_dungeon_combat(user_name: str, game_name: str) -> DungeonCombatResponse:
    """查询当前地下城战斗状态。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            server_config.base_url + f"/api/dungeons/v1/{user_name}/{game_name}/combat",
        )
        response.raise_for_status()
        return DungeonCombatResponse.model_validate(response.json())


async def dungeon_exit(user_name: str, game_name: str) -> DungeonExitResponse:
    """退出地下城，返回家园。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            server_config.base_url + "/api/dungeon/exit/v1/",
            json=DungeonExitRequest(
                user_name=user_name,
                game_name=game_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return DungeonExitResponse.model_validate(response.json())


async def dungeon_combat_init(
    user_name: str, game_name: str
) -> DungeonCombatInitResponse:
    """触发战斗初始化，返回后台任务ID。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            server_config.base_url + "/api/dungeon/combat/init/v1/",
            json=DungeonCombatInitRequest(
                user_name=user_name,
                game_name=game_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return DungeonCombatInitResponse.model_validate(response.json())


async def dungeon_combat_retreat(
    user_name: str, game_name: str
) -> DungeonCombatRetreatResponse:
    """触发战斗撤退，返回后台任务ID。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            server_config.base_url + "/api/dungeon/combat/retreat/v1/",
            json=DungeonCombatRetreatRequest(
                user_name=user_name,
                game_name=game_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return DungeonCombatRetreatResponse.model_validate(response.json())


async def dungeon_combat_draw_cards(
    user_name: str, game_name: str
) -> DungeonCombatDrawCardsResponse:
    """为全体战斗角色激活抽牌动作，返回后台任务ID。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            server_config.base_url + "/api/dungeon/combat/draw_cards/v1/",
            json=DungeonCombatDrawCardsRequest(
                user_name=user_name,
                game_name=game_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return DungeonCombatDrawCardsResponse.model_validate(response.json())


async def dungeon_combat_play_cards(
    user_name: str,
    game_name: str,
    actor_name: str,
    card_name: str,
    targets: list[str],
) -> DungeonCombatPlayCardsResponse:
    """让指定角色打出指定卡牌，返回后台任务ID。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            server_config.base_url + "/api/dungeon/combat/play_cards/v1/",
            json=DungeonCombatPlayCardsRequest(
                user_name=user_name,
                game_name=game_name,
                actor_name=actor_name,
                card_name=card_name,
                targets=targets,
            ).model_dump(),
        )
        response.raise_for_status()
        return DungeonCombatPlayCardsResponse.model_validate(response.json())


# async def dungeon_combat_exhaust_card(
#     user_name: str,
#     game_name: str,
#     actor_name: str,
#     card_name: str,
# ) -> DungeonCombatDiscardCardsResponse:
#     """让指定角色弃掉指定手牌，返回后台任务ID。"""
#     async with httpx.AsyncClient(timeout=10) as client:
#         response = await client.post(
#             server_config.base_url + "/api/dungeon/combat/exhaust_card/v1/",
#             json=DungeonCombatDiscardCardsRequest(
#                 user_name=user_name,
#                 game_name=game_name,
#                 actor_name=actor_name,
#                 card_name=card_name,
#             ).model_dump(),
#         )
#         response.raise_for_status()
#         return DungeonCombatDiscardCardsResponse.model_validate(response.json())


async def home_generate_dungeon(
    user_name: str, game_name: str
) -> HomeGenerateDungeonResponse:
    """触发地下城生成流程，返回后台任务ID."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            server_config.base_url + "/api/home/generate_dungeon/v1/",
            json=HomeGenerateDungeonRequest(
                user_name=user_name,
                game_name=game_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return HomeGenerateDungeonResponse.model_validate(response.json())


async def home_player_action(
    user_name: str,
    game_name: str,
    action: HomePlayerActionType,
    arguments: Dict[str, str],
) -> HomePlayerActionResponse:
    """触发家园玩家动作（对话、场景切换等），返回后台任务ID。"""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            server_config.base_url + "/api/home/player_action/v1/",
            json=HomePlayerActionRequest(
                user_name=user_name,
                game_name=game_name,
                action=action,
                arguments=arguments,
            ).model_dump(),
        )
        response.raise_for_status()
        return HomePlayerActionResponse.model_validate(response.json())


async def home_roster_add(
    user_name: str, game_name: str, member_name: str
) -> HomeRosterAddResponse:
    """将成员加入远征队。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            server_config.base_url + "/api/home/roster/add/v1/",
            json=HomeRosterAddRequest(
                user_name=user_name,
                game_name=game_name,
                member_name=member_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return HomeRosterAddResponse.model_validate(response.json())


async def home_roster_remove(
    user_name: str, game_name: str, member_name: str
) -> HomeRosterRemoveResponse:
    """将成员从远征队移除。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            server_config.base_url + "/api/home/roster/remove/v1/",
            json=HomeRosterRemoveRequest(
                user_name=user_name,
                game_name=game_name,
                member_name=member_name,
            ).model_dump(),
        )
        response.raise_for_status()
        return HomeRosterRemoveResponse.model_validate(response.json())
