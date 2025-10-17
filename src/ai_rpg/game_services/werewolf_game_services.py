from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger
from ..game_services.game_server import GameServerInstance
from ..models import (
    WerewolfGameStartRequest,
    WerewolfGameStartResponse,
    WerewolfGamePlayRequest,
    WerewolfGamePlayResponse,
    WerewolfGameStateResponse,
    World,
    WerewolfGameActorDetailsResponse,
    EntitySerialization,
)
from ..demo.werewolf_game_world import create_demo_sd_game_boot
from ..game_services.game_server import GameServerInstance
from ..game.player_client import PlayerClient
from ..game.tcg_game import TCGGame
from ..settings import (
    initialize_server_settings_instance,
)
from ..chat_services import ChatClient
from ..game.config import GLOBAL_SD_GAME_NAME
from typing import List, Set
from ..entitas import Entity

###################################################################################################################################################################
werewolf_game_api_router = APIRouter()


###################################################################################################################################################################
@werewolf_game_api_router.post(
    path="/api/werewolf/start/v1/", response_model=WerewolfGameStartResponse
)
async def start_werewolf_game(
    request_data: WerewolfGameStartRequest,
    game_server: GameServerInstance,
) -> WerewolfGameStartResponse:

    logger.info(f"Starting werewolf game: {request_data.model_dump_json()}")

    # 先检查房间是否存在，存在就删除旧房间
    if game_server.has_room(request_data.user_name):

        logger.debug(f"start/v1: {request_data.user_name} room exists, removing it")

        pre_room = game_server.get_room(request_data.user_name)
        assert pre_room is not None

        game_server.remove_room(pre_room)

    assert not game_server.has_room(
        request_data.user_name
    ), "Room should have been removed."

    # 然后创建一个新的房间
    new_room = game_server.create_room(
        user_name=request_data.user_name,
    )
    logger.info(
        f"start/v1: {request_data.user_name} create room = {new_room._username}"
    )
    assert new_room._game is None

    # 创建boot数据
    assert GLOBAL_SD_GAME_NAME == request_data.game_name, "目前只支持 SD 游戏"
    world_boot = create_demo_sd_game_boot(request_data.game_name)
    assert world_boot is not None, "WorldBoot 创建失败"

    # 创建游戏实例
    new_room._game = terminal_game = TCGGame(
        name=request_data.game_name,
        player_client=PlayerClient(
            name=request_data.user_name, actor="角色.主持人"  # 写死先！
        ),
        world=World(boot=world_boot),
    )

    # 创建服务器相关的连接信息。
    server_settings = initialize_server_settings_instance(Path("server_settings.json"))
    ChatClient.initialize_url_config(server_settings)

    # 新游戏！
    terminal_game.new_game().save()

    # 测试一下玩家控制角色，如果没有就是错误。
    assert terminal_game.get_player_entity() is not None, "玩家实体不存在"

    # 初始化!
    await terminal_game.initialize()

    # 在这里添加启动游戏的逻辑
    return WerewolfGameStartResponse(
        message=terminal_game.world.model_dump_json(indent=2)
    )


###################################################################################################################################################################


werewolf_game_api_router.post(
    path="/api/werewolf/gameplay/v1/", response_model=WerewolfGamePlayResponse
)


async def play_werewolf_game(
    request_data: WerewolfGamePlayRequest,
    game_server: GameServerInstance,
) -> WerewolfGamePlayResponse:
    logger.info(f"Playing werewolf game: {request_data.model_dump_json()}")
    # 在这里添加游戏玩法的逻辑
    return WerewolfGamePlayResponse(client_messages=[])


###################################################################################################################################################################


@werewolf_game_api_router.get(
    path="/api/werewolf/state/v1/{user_name}/{game_name}/state",
    response_model=WerewolfGameStateResponse,
)
async def get_werewolf_game_state(
    game_server: GameServerInstance,
    user_name: str,
    game_name: str,
) -> WerewolfGameStateResponse:
    logger.info(f"Getting werewolf game state for user: {user_name}, game: {game_name}")
    # 在这里添加获取游戏状态的逻辑
    return WerewolfGameStateResponse(
        message="Werewolf game state retrieved successfully."
    )


###################################################################################################################################################################


@werewolf_game_api_router.get(
    path="/api/werewolf/actors/v1/{user_name}/{game_name}/details",
    response_model=WerewolfGameActorDetailsResponse,
)
async def get_werewolf_actors_details(
    game_server: GameServerInstance,
    user_name: str,
    game_name: str,
    actor_names: List[str] = Query(..., alias="actors"),
) -> WerewolfGameActorDetailsResponse:

    logger.info(
        f"/werewolf/actors/v1/{user_name}/{game_name}/details: {user_name}, {game_name}, {actor_names}"
    )

    try:

        # 是否有房间？！！
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

        # 获取所有角色实体
        entities_serialization: List[EntitySerialization] = []

        # 获取指定角色实体
        actor_entities: Set[Entity] = set()

        for actor_name in actor_names:
            # 获取角色实体
            actor_entity = current_room._game.get_entity_by_name(actor_name)
            if actor_entity is None:
                logger.error(f"view_actor: {user_name} actor {actor_name} not found.")
                continue

            # 添加到集合中
            actor_entities.add(actor_entity)

        # 序列化角色实体
        entities_serialization = current_room._game.serialize_entities(actor_entities)

        # 返回!
        return WerewolfGameActorDetailsResponse(
            actor_entities_serialization=entities_serialization,
            agent_short_term_memories=[],  # 太长了，先注释掉
        )
    except Exception as e:
        logger.error(f"get_actors_details: {user_name} error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"服务器错误: {str(e)}",
        )


###################################################################################################################################################################
