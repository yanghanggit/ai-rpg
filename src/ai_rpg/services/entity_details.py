"""实体详情查询服务模块"""

from typing import List, Set, Type
from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from ..entitas import Component, Entity, Matcher
from .game_server_dependencies import CurrentGameServer
from ..models import (
    COMPONENT_TYPES,
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
    """

    logger.info(
        f"/entities/v1/{user_name}/{game_name}/details: {user_name}, {game_name}, {entity_names}"
    )

    # 验证请求参数
    if len(entity_names) == 0 or entity_names[0].strip() == "":
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
    rpg_game = current_room._dbg_game
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
    serialize_entities = rpg_game.serialize_entities(entities)

    # 返回实体详情
    return EntitiesDetailsResponse(
        entities=serialize_entities,
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
def _resolve_component_types(component_names: List[str]) -> List[Type[Component]]:
    """将组件名称列表解析为组件类型列表。

    遇到未注册的组件名称时，抛出 400 错误。
    """
    component_types: List[Type[Component]] = []
    invalid_names: List[str] = []

    for name in component_names:
        comp_type = COMPONENT_TYPES.get(name)
        if comp_type is None:
            invalid_names.append(name)
            continue
        component_types.append(comp_type)

    if invalid_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"非法组件名: {', '.join(invalid_names)}",
        )

    return component_types


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@entity_details_api_router.get(
    path="/api/entities/v1/{user_name}/{game_name}/group",
    response_model=EntitiesDetailsResponse,
)
async def get_entities_group(
    game_server: CurrentGameServer,
    user_name: str,
    game_name: str,
    all_of: List[str] = Query(default=[], alias="all_of"),
    any_of: List[str] = Query(default=[], alias="any_of"),
    none_of: List[str] = Query(default=[], alias="none_of"),
) -> EntitiesDetailsResponse:
    """按组件条件分组查询实体接口

    根据 all_of / any_of / none_of 三组组件条件构造 Matcher，
    调用 get_group 返回匹配实体的序列化数据。
    """

    logger.info(
        f"/entities/v1/{user_name}/{game_name}/group: all_of={all_of}, any_of={any_of}, none_of={none_of}"
    )

    # 清洗请求参数：去除空白项
    all_of = [name.strip() for name in all_of if name.strip()]
    any_of = [name.strip() for name in any_of if name.strip()]
    none_of = [name.strip() for name in none_of if name.strip()]

    # 三组条件全空则拒绝请求
    if not all_of and not any_of and not none_of:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少提供一个组件条件",
        )

    # 检查房间是否存在
    if not game_server.has_room(user_name):
        logger.error(f"get_entities_group: {user_name} has no room")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有房间",
        )

    # 获取房间实例
    current_room = game_server.get_room(user_name)
    assert current_room is not None, "Current room should not be None"

    # 根据游戏类型获取游戏实例
    rpg_game = current_room._dbg_game
    assert rpg_game is not None, "RPG game should not be None"
    if rpg_game is None:
        logger.error(f"get_entities_group: {user_name} has no RPG game")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有RPG游戏",
        )

    # 验证游戏名称匹配
    if rpg_game.name != game_name:
        logger.error(f"get_entities_group: {user_name} game_name mismatch")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="游戏名称不匹配",
        )

    # 将组件名称解析为组件类型
    all_of_types = _resolve_component_types(all_of)
    any_of_types = _resolve_component_types(any_of)
    none_of_types = _resolve_component_types(none_of)

    # 构造 Matcher 并获取匹配实体分组
    matcher = Matcher(
        all_of=all_of_types or None,
        any_of=any_of_types or None,
        none_of=none_of_types or None,
    )
    group = rpg_game.get_group(matcher)

    # 序列化匹配到的实体
    serialize_entities = rpg_game.serialize_entities(group.entities)

    # 返回分组查询结果
    return EntitiesDetailsResponse(
        entities=serialize_entities,
    )
