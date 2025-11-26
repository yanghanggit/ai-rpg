"""实体详情查询服务模块

本模块提供实体详情查询的 API 接口，主要功能包括：
- 批量查询指定实体的详细信息
- 支持多种游戏类型（SDG 和 TCG 游戏）的实体查询
- 返回实体的序列化数据，包含实体的所有属性和状态
- 验证用户房间和游戏实例的存在性

实体查询流程：
1. 验证请求参数（至少提供一个实体名称）
2. 验证用户房间是否存在
3. 根据游戏类型（SDG 或 TCG）获取对应的游戏实例
4. 在游戏世界中查找指定的实体
5. 序列化实体数据并返回

注意事项：
- 必须先创建房间并启动游戏才能查询实体信息
- 支持 SDG 游戏和 TCG 游戏两种类型
- 游戏名称必须与当前运行的游戏匹配
- 可以一次查询多个实体（包括 World、Stage、Actor 等任何类型），提高查询效率
- 如果某个实体不存在，会跳过该实体继续查询其他实体
- 所有异常由 FastAPI 框架统一处理，确保客户端收到正确的 HTTP 状态码
"""

from typing import List, Set
from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from ..entitas import Entity
from .game_server_depends import GameServerInstance
from ..models import (
    EntitiesDetailsResponse,
)
from ..game.rpg_game import RPGGame

###################################################################################################################################################################
entity_details_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@entity_details_api_router.get(
    path="/api/entities/v1/{user_name}/{game_name}/details",
    response_model=EntitiesDetailsResponse,
)
async def get_entities_details(
    game_server: GameServerInstance,
    user_name: str,
    game_name: str,
    entity_names: List[str] = Query(..., alias="entities"),
) -> EntitiesDetailsResponse:
    """批量查询实体详情接口

    根据提供的实体名称列表，批量查询实体的详细信息。
    支持 SDG 和 TCG 两种游戏类型，返回实体的完整序列化数据。
    可以查询任何类型的实体（World、Stage、Actor 等）。

    Args:
        game_server: 游戏服务器实例，管理所有用户房间和游戏会话
        user_name: 用户名，用于定位用户房间
        game_name: 游戏名称，用于匹配当前运行的游戏
        entity_names: 要查询的实体名称列表，通过查询参数 entities 传递

    Returns:
        EntitiesDetailsResponse: 实体详情响应，包含所有查询到的实体序列化数据列表

    Raises:
        HTTPException(400): 以下情况会返回 400 错误：
            - 未提供实体名称或实体名称列表为空
            - 游戏名称与当前运行的游戏不匹配
        HTTPException(404): 用户房间不存在，需要先调用 login 接口
        AssertionError: 当关键对象状态异常时抛出

    Note:
        - 必须先调用 /api/login/v1/ 创建房间
        - 必须先调用 /api/start/v1/ 或狼人杀启动接口启动游戏
        - 支持 SDG 游戏（_sdg_game）和 TCG 游戏（_tcg_game）
        - 可以一次查询多个实体（World、Stage、Actor 等），提高查询效率
        - 如果某个实体在游戏世界中不存在，会跳过该实体继续查询其他实体
        - 游戏名称必须与房间中当前运行的游戏名称完全匹配
        - 返回的实体序列化数据包含实体的所有组件和属性信息
        - 使用 Query 参数 entities 传递实体名称列表，例如：?entities=world&entities=stage&entities=hero
    """

    logger.info(
        f"/entities/v1/{user_name}/{game_name}/details: {user_name}, {game_name}, {entity_names}"
    )

    # 验证请求参数
    if len(entity_names) == 0 or entity_names[0] == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请提供至少一个实体名称",
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
    rpg_game: RPGGame | None = None

    if current_room._sdg_game is not None and game_name == current_room._sdg_game.name:
        # 获取 SDG 游戏
        rpg_game = current_room._sdg_game

    elif (
        current_room._tcg_game is not None and game_name == current_room._tcg_game.name
    ):
        # 获取 TCG 游戏
        rpg_game = current_room._tcg_game

    else:
        logger.error(f"get_session_messages: {user_name} game_name mismatch")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="游戏名称不匹配",
        )

    # 验证游戏实例
    assert rpg_game is not None, "WebGame should not be None"

    # 获取指定实体
    entities: Set[Entity] = set()

    for entity_name in entity_names:
        # 获取实体（可以是任何类型：World、Stage、Actor 等）
        entity = rpg_game.get_entity_by_name(entity_name)
        if entity is None:
            logger.error(
                f"get_entities_details: {user_name} entity {entity_name} not found."
            )
            continue

        # 添加到集合中
        entities.add(entity)

    # 序列化实体
    entities_serialization = rpg_game.serialize_entities(entities)

    # 返回实体详情
    return EntitiesDetailsResponse(
        entities_serialization=entities_serialization,
    )
