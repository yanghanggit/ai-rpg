"""游戏服务器 HTTP 客户端（TUI 客户端专用）"""

from typing import Any, Dict, cast

import httpx

GAME_SERVER_BASE_URL = "http://192.168.192.102:8000"


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
            json={"user_name": user_name, "game_name": game_name},
        )
        response.raise_for_status()
        data = cast(Dict[str, Any], response.json())
        return str(data.get("message", "登录成功"))


async def new_game(user_name: str, game_name: str) -> Dict[str, Any]:
    """创建新游戏，返回服务器响应 JSON。"""
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            GAME_SERVER_BASE_URL + "/api/game/new/v1/",
            json={"user_name": user_name, "game_name": game_name},
        )
        response.raise_for_status()
        return cast(Dict[str, Any], response.json())
