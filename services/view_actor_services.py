from entitas import Matcher  # type: ignore
from typing import List
from fastapi import APIRouter, Query
from game.web_tcg_game import WebTCGGame
from services.game_server_instance import GameServerInstance
from models_v_0_0_1 import (
    ViewActorResponse,
    EntitySnapshot,
    ActorComponent,
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
    actors: List[str] = Query(..., alias="actors"),
) -> ViewActorResponse:

    logger.info(f"/view-actor/v1/: {user_name}, {game_name}, {actors}")

    # 是否有房间？！！
    room_manager = game_server.room_manager
    if not room_manager.has_room(user_name):
        logger.error(f"view_actor: {user_name} has no room, please login first.")
        return ViewActorResponse(
            error=1001,
            message="没有登录，请先登录",
        )

    # 是否有游戏？！！
    current_room = room_manager.get_room(user_name)
    assert current_room is not None
    if current_room._game is None:
        logger.error(f"view_actor: {user_name} has no game, please login first.")
        return ViewActorResponse(
            error=1002,
            message="没有游戏，请先登录",
        )

    web_game = current_room._game
    assert web_game.name == game_name
    assert web_game is not None
    assert isinstance(web_game, WebTCGGame)

    # 获取快照
    snapshots: List[EntitySnapshot] = []
    if len(actors) == 0 or actors[0] == "":
        # 没有指定角色，获取所有角色
        actor_entities = web_game.get_group(
            Matcher(
                all_of=[ActorComponent],
            )
        ).entities

        actors = [actor_entity._name for actor_entity in actor_entities]

    for actor_name in actors:

        actor_entity = web_game.get_entity_by_name(actor_name)
        if actor_entity is None:
            logger.error(f"view_actor: {user_name} actor {actor_name} not found.")
            continue
        snapshot = web_game.create_entity_snapshot(actor_entity)
        snapshots.append(snapshot)

    # 返回。
    return ViewActorResponse(
        actor_snapshots=snapshots,
        error=0,
        message=f"{'\n'.join([snapshot.model_dump_json() for snapshot in snapshots])}",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
