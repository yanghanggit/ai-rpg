from typing import List
from fastapi import APIRouter
from services.game_server_instance import GameServerInstance
from models_v_0_0_1 import (
    ViewActorRequest,
    ViewActorResponse,
    EntitySnapshot,
)
from loguru import logger


###################################################################################################################################################################
view_actor_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@view_actor_router.post(path="/view-actor/v1/", response_model=ViewActorResponse)
async def view_actor(
    request_data: ViewActorRequest,
    game_server: GameServerInstance,
) -> ViewActorResponse:

    logger.info(f"/view-actor/v1/: {request_data.model_dump_json()}")

    # 是否有房间？！！
    room_manager = game_server.room_manager
    if not room_manager.has_room(request_data.user_name):
        logger.error(
            f"view_actor: {request_data.user_name} has no room, please login first."
        )
        return ViewActorResponse(
            error=1001,
            message="没有登录，请先登录",
        )

    # 是否有游戏？！！
    current_room = room_manager.get_room(request_data.user_name)
    assert current_room is not None
    if current_room._game is None:
        logger.error(
            f"view_actor: {request_data.user_name} has no game, please login first."
        )
        return ViewActorResponse(
            error=1002,
            message="没有游戏，请先登录",
        )

    # 判断游戏是否开始
    if not current_room._game.is_game_started:
        logger.error(
            f"view_actor: {request_data.user_name} game not started, please start it first."
        )
        return ViewActorResponse(
            error=1003,
            message="游戏没有开始，请先开始游戏",
        )

    # 获取快照
    snapshots: List[EntitySnapshot] = []
    for actor_name in request_data.actors:

        actor_entity = current_room._game.get_entity_by_name(actor_name)
        if actor_entity is None:
            logger.error(
                f"view_actor: {request_data.user_name} actor {actor_name} not found."
            )
            continue
        snapshot = current_room._game.create_entity_snapshot(actor_entity)
        snapshots.append(snapshot)

    # 返回。
    return ViewActorResponse(
        error=0,
        message=f"{'\n'.join([snapshot.model_dump_json() for snapshot in snapshots])}",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
