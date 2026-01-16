"""实体详情查询服务模块

提供实体详情查询的 API 接口，支持批量查询指定实体的序列化数据。
"""

from typing import List, Set
from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from ..entitas import Entity
from .game_server_dependencies import CurrentGameServer
from ..models import (
    EntitiesDetailsResponse,
)

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
    game_server: CurrentGameServer,
    user_name: str,
    game_name: str,
    entity_names: List[str] = Query(..., alias="entities"),
) -> EntitiesDetailsResponse:
    """批量查询实体详情接口

    根据实体名称列表批量查询实体的序列化数据。

    Args:
        game_server: 游戏服务器实例
        user_name: 用户名
        game_name: 游戏名称
        entity_names: 要查询的实体名称列表

    Returns:
        EntitiesDetailsResponse: 包含实体序列化数据的响应

    Raises:
        HTTPException(400): 实体名称列表为空或游戏名称不匹配
        HTTPException(404): 用户房间不存在
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
    rpg_game = current_room._tcg_game
    assert rpg_game is not None, "RPG game should not be None"
    if rpg_game is None:
        logger.error(f"get_session_messages: {user_name} has no RPG game")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有RPG游戏",
        )

    # 验证游戏名称匹配
    if rpg_game.name != game_name:
        logger.error(f"get_entities_details: {user_name} game_name mismatch")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="游戏名称不匹配",
        )

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
