"""角色详情查询服务模块

本模块提供角色详情查询的 API 接口，主要功能包括：
- 批量查询指定角色的详细信息
- 支持多种游戏类型（SDG 和 TCG 游戏）的角色查询
- 返回角色实体的序列化数据，包含角色的所有属性和状态
- 验证用户房间和游戏实例的存在性

角色查询流程：
1. 验证请求参数（至少提供一个角色名称）
2. 验证用户房间是否存在
3. 根据游戏类型（SDG 或 TCG）获取对应的游戏实例
4. 在游戏世界中查找指定的角色实体
5. 序列化角色实体数据并返回

注意事项：
- 必须先创建房间并启动游戏才能查询角色信息
- 支持 SDG 游戏和 TCG 游戏两种类型
- 游戏名称必须与当前运行的游戏匹配
- 可以一次查询多个角色，提高查询效率
- 如果某个角色不存在，会跳过该角色继续查询其他角色
- 所有异常由 FastAPI 框架统一处理，确保客户端收到正确的 HTTP 状态码
"""

from typing import List, Set
from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from ..entitas import Entity
from .game_server_depends import GameServerInstance
from ..models import (
    EntitySerialization,
    ActorDetailsResponse,
)
from ..game.rpg_game import RPGGame

###################################################################################################################################################################
actor_details_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@actor_details_api_router.get(
    path="/api/actors/v1/{user_name}/{game_name}/details",
    response_model=ActorDetailsResponse,
)
async def get_actors_details(
    game_server: GameServerInstance,
    user_name: str,
    game_name: str,
    actor_names: List[str] = Query(..., alias="actors"),
) -> ActorDetailsResponse:
    """批量查询角色详情接口

    根据提供的角色名称列表，批量查询角色的详细信息。
    支持 SDG 和 TCG 两种游戏类型，返回角色实体的完整序列化数据。

    Args:
        game_server: 游戏服务器实例，管理所有用户房间和游戏会话
        user_name: 用户名，用于定位用户房间
        game_name: 游戏名称，用于匹配当前运行的游戏
        actor_names: 要查询的角色名称列表，通过查询参数 actors 传递

    Returns:
        ActorDetailsResponse: 角色详情响应，包含所有查询到的角色实体序列化数据列表

    Raises:
        HTTPException(400): 以下情况会返回 400 错误：
            - 未提供角色名称或角色名称列表为空
            - 游戏名称与当前运行的游戏不匹配
        HTTPException(404): 用户房间不存在，需要先调用 login 接口
        AssertionError: 当关键对象状态异常时抛出

    Note:
        - 必须先调用 /api/login/v1/ 创建房间
        - 必须先调用 /api/start/v1/ 或狼人杀启动接口启动游戏
        - 支持 SDG 游戏（_sdg_game）和 TCG 游戏（_tcg_game）
        - 可以一次查询多个角色，提高查询效率
        - 如果某个角色在游戏世界中不存在，会跳过该角色继续查询其他角色
        - 游戏名称必须与房间中当前运行的游戏名称完全匹配
        - 返回的实体序列化数据包含角色的所有组件和属性信息
        - 使用 Query 参数 actors 传递角色名称列表，例如：?actors=hero&actors=enemy
    """

    logger.info(
        f"/actors/v1/{user_name}/{game_name}/details: {user_name}, {game_name}, {actor_names}"
    )

    # 验证请求参数
    if len(actor_names) == 0 or actor_names[0] == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供至少一个角色名称",
        )

    # 检查房间是否存在
    if not game_server.has_room(user_name):
        logger.error(f"view_actor: {user_name} has no room")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有房间",
        )

    # 获取房间实例
    current_room = game_server.get_room(user_name)
    assert current_room is not None, "Current room should not be None"

    # 根据游戏类型获取游戏实例
    web_game: RPGGame | None = None

    if current_room._sdg_game is not None and game_name == current_room._sdg_game.name:
        # 获取 SDG 游戏
        web_game = current_room._sdg_game

    elif (
        current_room._tcg_game is not None and game_name == current_room._tcg_game.name
    ):
        # 获取 TCG 游戏
        web_game = current_room._tcg_game

    else:
        logger.error(f"get_session_messages: {user_name} game_name mismatch")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="游戏名称不匹配",
        )

    # 验证游戏实例
    assert web_game is not None, "WebGame should not be None"

    # 获取指定角色实体
    actor_entities: Set[Entity] = set()

    for actor_name in actor_names:
        # 获取角色实体
        actor_entity = web_game.get_entity_by_name(actor_name)
        if actor_entity is None:
            logger.error(f"view_actor: {user_name} actor {actor_name} not found.")
            continue

        # 添加到集合中
        actor_entities.add(actor_entity)

    # 序列化角色实体
    entities_serialization = web_game.serialize_entities(actor_entities)

    # 返回角色详情
    return ActorDetailsResponse(
        actor_entities_serialization=entities_serialization,
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
