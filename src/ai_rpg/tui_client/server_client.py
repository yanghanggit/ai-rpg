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
