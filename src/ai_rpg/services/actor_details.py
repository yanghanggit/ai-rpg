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

    logger.info(
        f"/actors/v1/{user_name}/{game_name}/details: {user_name}, {game_name}, {actor_names}"
    )
    try:

        if len(actor_names) == 0 or actor_names[0] == "":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="请提供至少一个角色名称",
            )

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
        assert current_room is not None, "Current room should not be None"

        # 获取游戏实例
        web_game: RPGGame | None = None

        # 获取增量消息
        if (
            current_room._sdg_game is not None
            and game_name == current_room._sdg_game.name
        ):
            # 获取游戏
            web_game = current_room._sdg_game

        elif (
            current_room._tcg_game is not None
            and game_name == current_room._tcg_game.name
        ):
            # 获取游戏
            web_game = current_room._tcg_game

        else:
            logger.error(f"get_session_messages: {user_name} game_name mismatch")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="游戏名称不匹配",
            )

        # 获取所有角色实体
        assert web_game is not None, "WebGame should not be None"

        # 所有角色的实体序列化
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
        )

    except HTTPException:
        # 直接向上传播 HTTPException，不要重新包装
        raise
    except Exception as e:
        logger.error(f"view_actor: {user_name} error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器错误: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
