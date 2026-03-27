"""游戏服务器 HTTP 客户端（TUI 客户端专用）"""

from typing import Any, Dict, cast

import httpx

from ..models import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    NewGameRequest,
    NewGameResponse,
    StagesStateResponse,
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
