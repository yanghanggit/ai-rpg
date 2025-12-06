"""API 根路由服务模块

本模块提供 API 服务的根路由接口，主要功能包括：
- 返回 API 服务的基本信息（服务名称、描述、状态、版本等）
- 提供所有可用的 API 端点列表和完整的访问 URL
- 作为客户端发现和访问 API 服务的入口点

主要端点分类：
- RPG 游戏相关：登录、登出、开始游戏、主城玩法、副本玩法等
- 狼人杀游戏相关：游戏开始、游戏玩法、游戏状态等
- 通用服务：会话消息、实体详情、场景状态等

注意事项：
- 这是客户端访问 API 服务的第一个接口，用于服务发现
- 所有端点 URL 都会根据请求的 base_url 动态生成
- 返回的端点列表应与实际部署的 API 路由保持同步
"""

from fastapi import APIRouter, Request
from loguru import logger
from ..models import (
    RootResponse,
)
from datetime import datetime

################################################################################################################
root_api_router = APIRouter()


################################################################################################################
################################################################################################################
################################################################################################################
@root_api_router.get(path="/", response_model=RootResponse)
async def root(
    request: Request,
) -> RootResponse:
    """API 根路由接口

    提供 API 服务的基本信息和所有可用端点的完整列表。
    客户端可以通过此接口发现和访问所有可用的 API 服务。

    Args:
        request: FastAPI 请求对象，用于获取服务的 base_url

    Returns:
        RootResponse: API 根响应对象，包含以下信息：
            - service: 服务名称
            - description: 服务描述
            - status: 服务健康状态
            - timestamp: 当前时间戳
            - version: API 版本号
            - endpoints: 所有可用的 API 端点及其完整 URL

    Note:
        - 端点 URL 会根据请求的 base_url 动态生成
        - 返回的端点列表包括 RPG 游戏、狼人杀游戏和通用服务三大类
        - 此接口通常用于 API 文档生成和客户端服务发现
    """

    base_url = str(request.base_url)
    logger.info(f"获取API路由 RootResponse: {base_url}")

    return RootResponse(
        service="AI RPG TCG Game Server",
        description="AI RPG TCG Game Server API Root Endpoint",
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="0.0.1",
        endpoints={
            # rpg 专用
            "login": base_url + "api/login/v1/",
            "logout": base_url + "api/logout/v1/",
            "start": base_url + "api/start/v1/",
            "home_gameplay": base_url + "api/home/gameplay/v1/",
            "home_trans_dungeon": base_url + "api/home/trans_dungeon/v1/",
            "dungeon_gameplay": base_url + "api/dungeon/gameplay/v1/",
            "dungeon_trans_home": base_url + "api/dungeon/trans_home/v1/",
            "dungeon_state": base_url + "api/dungeons/v1/",
            # 狼人杀专用
            "werewolf_game_start": base_url + "api/werewolf/start/v1/",
            "werewolf_gameplay": base_url + "api/werewolf/gameplay/v1/",
            "werewolf_game_state": base_url + "api/werewolf/state/v1/",
            # 通用的服务。
            "session_messages": base_url + "api/session_messages/v1/",
            "entity_details": base_url + "api/entities/v1/",
            "stages_state": base_url + "api/stages/v1/",
        },
        api_docs={
            # 需要路径参数的端点完整路径说明
            "session_messages": base_url
            + "api/session_messages/v1/{user_name}/{game_name}/since?last_sequence_id=0",
            "entity_details": base_url
            + "api/entities/v1/{user_name}/{game_name}/details?entities=entity1&entities=entity2",
            "stages_state": base_url + "api/stages/v1/{user_name}/{game_name}/state",
            "dungeon_state": base_url + "api/dungeons/v1/{user_name}/{game_name}/state",
            "werewolf_game_state": base_url
            + "api/werewolf/state/v1/{user_name}/{game_name}/state",
        },
    )
