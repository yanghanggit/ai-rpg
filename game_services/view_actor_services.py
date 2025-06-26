from entitas import Matcher  # type: ignore
from typing import List
from fastapi import APIRouter, Query, HTTPException, status
from game_services.game_server import GameServerInstance
from models_v_0_0_1 import (
    ViewActorResponse,
    EntitySnapshot,
    ActorComponent,
    AgentShortTermMemory,
)
from loguru import logger

###################################################################################################################################################################
view_actor_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@view_actor_router.get(
    path="/view-actor/v1/{user_name}/{game_name}", response_model=ViewActorResponse
)
async def view_actor(
    game_server: GameServerInstance,
    user_name: str,
    game_name: str,
    actor_names: List[str] = Query(..., alias="actors"),
) -> ViewActorResponse:

    logger.info(f"/view-actor/v1/: {user_name}, {game_name}, {actor_names}")
    try:

        # 是否有房间？！！
        room_manager = game_server.room_manager
        if not room_manager.has_room(user_name):
            logger.error(f"view_actor: {user_name} has no room")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有房间",
            )

        # 是否有游戏？！！
        current_room = room_manager.get_room(user_name)
        assert current_room is not None
        if current_room.game is None:
            logger.error(f"view_actor: {user_name} has no game")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有游戏",
            )

        # 获取游戏
        web_game = current_room.game

        # 获取快照
        snapshots: List[EntitySnapshot] = []
        agent_short_term_memories: List[AgentShortTermMemory] = []

        if len(actor_names) == 0 or actor_names[0] == "":
            # 没有指定角色，获取所有角色
            actor_entities = web_game.get_group(
                Matcher(
                    all_of=[ActorComponent],
                )
            ).entities

            actor_names = [actor_entity._name for actor_entity in actor_entities]

        for actor_name in actor_names:

            actor_entity = web_game.get_entity_by_name(actor_name)
            if actor_entity is None:
                logger.error(f"view_actor: {user_name} actor {actor_name} not found.")
                continue

            # 获取快照
            snapshot = web_game.create_entity_snapshot(actor_entity)
            snapshots.append(snapshot)

            # 获取短期记忆
            agent_short_term_memory = web_game.get_agent_short_term_memory(actor_entity)
            agent_short_term_memories.append(agent_short_term_memory)

        # 返回。
        return ViewActorResponse(
            actor_snapshots=snapshots,
            agent_short_term_memories=agent_short_term_memories,
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
