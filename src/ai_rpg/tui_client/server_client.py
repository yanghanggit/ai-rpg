"""游戏服务器 HTTP 客户端（TUI 客户端专用）"""

from typing import Any, Dict, List, cast

import httpx

from ..models import (
    BlueprintListResponse,
    DungeonListResponse,
    EntitiesDetailsResponse,
    HomeAdvanceRequest,
    HomeAdvanceResponse,
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    NewGameRequest,
    NewGameResponse,
    SessionMessageResponse,
    StagesStateResponse,
    TasksStatusResponse,
)
from .config import GAME_SERVER_BASE_URL


async def fetch_server_info() -> Dict[str, Any]:
    """请求游戏服务器根路由，返回服务信息 JSON。"""
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(GAME_SERVER_BASE_URL + "/")
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())


async def login(user_name: str, game_name: str) -> str:
    """登录游戏服务器，返回服务器响应消息。"""
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.post(
            GAME_SERVER_BASE_URL + "/api/login/v1/",
            json=LoginRequest(user_name=user_name, game_name=game_name).model_dump(),
        )
        response.raise_for_status()
        return LoginResponse.model_validate(response.json()).message


async def new_game(user_name: str, game_name: str) -> NewGameResponse:
    """创建新游戏，返回服务器响应。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            GAME_SERVER_BASE_URL + "/api/game/new/v1/",
            json=NewGameRequest(user_name=user_name, game_name=game_name).model_dump(),
        )
        response.raise_for_status()
        return NewGameResponse.model_validate(response.json())


async def fetch_stages_state(user_name: str, game_name: str) -> StagesStateResponse:
    """查询场景状态，返回场景与角色的分布映射。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            GAME_SERVER_BASE_URL + f"/api/stages/v1/{user_name}/{game_name}/state",
        )
        response.raise_for_status()
        return StagesStateResponse.model_validate(response.json())


async def logout(user_name: str, game_name: str) -> str:
    """登出游戏服务器，返回服务器响应消息。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            GAME_SERVER_BASE_URL + "/api/logout/v1/",
            json=LogoutRequest(user_name=user_name, game_name=game_name).model_dump(),
        )
        response.raise_for_status()
        return LogoutResponse.model_validate(response.json()).message


async def fetch_blueprint_list() -> BlueprintListResponse:
    """获取可用蓝图列表。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            GAME_SERVER_BASE_URL + "/api/game/blueprint-list/v1/",
        )
        response.raise_for_status()
        return BlueprintListResponse.model_validate(response.json())


async def fetch_session_messages(
    user_name: str, game_name: str, last_sequence_id: int
) -> SessionMessageResponse:
    """增量获取玩家会话消息。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            GAME_SERVER_BASE_URL
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
            GAME_SERVER_BASE_URL + f"/api/entities/v1/{user_name}/{game_name}/details",
            params={"entities": entity_names},
        )
        response.raise_for_status()
        return EntitiesDetailsResponse.model_validate(response.json())


async def fetch_dungeon_list() -> DungeonListResponse:
    """获取可用地下城列表。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            GAME_SERVER_BASE_URL + "/api/home/dungeon-list/v1/",
        )
        response.raise_for_status()
        return DungeonListResponse.model_validate(response.json())


async def fetch_tasks_status(task_ids: List[str]) -> TasksStatusResponse:
    """批量查询后台任务状态。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            GAME_SERVER_BASE_URL + "/api/tasks/v1/status",
            params={"task_ids": task_ids},
        )
        response.raise_for_status()
        return TasksStatusResponse.model_validate(response.json())


async def home_advance(user_name: str, game_name: str) -> HomeAdvanceResponse:
    """触发家园推进流程，返回后台任务ID。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            GAME_SERVER_BASE_URL + "/api/home/advance/v1/",
            json=HomeAdvanceRequest(
                user_name=user_name,
                game_name=game_name,
                actors=[],
            ).model_dump(),
        )
        response.raise_for_status()
        return HomeAdvanceResponse.model_validate(response.json())
