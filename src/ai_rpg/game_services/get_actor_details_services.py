from typing import List, Set
from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from ..entitas import Entity
from .game_server import GameServerInstance
from ..models import (
    EntitySerialization,
    ActorDetailsResponse,
)

###################################################################################################################################################################
get_actor_details_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@get_actor_details_api_router.get(
    path="/api/actors/v1/{user_name}/{game_name}/details",
    response_model=ActorDetailsResponse,
)
async def get_actors_details(
    game_server: GameServerInstance,
    user_name: str,
    game_name: str,
    actor_names: List[str] = Query(..., alias="actors"),
) -> ActorDetailsResponse:

    logger.info(
        f"/actors/v1/{user_name}/{game_name}/details: {user_name}, {game_name}, {actor_names}"
    )
    try:

        # 是否有房间？！！
        # room_manager = game_server.room_manager
        if not game_server.has_room(user_name):
            logger.error(f"view_actor: {user_name} has no room")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有房间",
            )

        # 是否有游戏？！！
        current_room = game_server.get_room(user_name)
        assert current_room is not None
        if current_room._game is None:
            logger.error(f"view_actor: {user_name} has no game")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有游戏",
            )

        if len(actor_names) == 0 or actor_names[0] == "":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请提供至少一个角色名称",
            )

        # 获取游戏
        web_game = current_room._game

        # 获取所有角色实体
        entities_serialization: List[EntitySerialization] = []

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

        # 返回!
        return ActorDetailsResponse(
            actor_entities_serialization=entities_serialization,
            agent_short_term_memories=[],  # 太长了，先注释掉
        )
    except Exception as e:
        logger.error(f"view_actor: {user_name} error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器错误: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
