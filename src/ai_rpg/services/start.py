from typing import Optional
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.player_session import PlayerSession
from ..game.tcg_game import TCGGame
from ..game.game_data_service import get_user_world_data, get_game_boot_data
from ..models import StartRequest, StartResponse, World
from .game_server_depends import GameServerInstance
from ..demo.stage_dungeon4 import (
    create_demo_dungeon4,
)

###################################################################################################################################################################
start_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@start_api_router.post(path="/api/start/v1/", response_model=StartResponse)
async def start(
    payload: StartRequest,
    game_server: GameServerInstance,
) -> StartResponse:

    logger.info(f"/start/v1/: {payload.model_dump_json()}")

    try:

        # 如果没有房间，就创建一个
        # room_manager = game_server.room_manager
        if not game_server.has_room(payload.user_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"start/v1: {payload.user_name} not found, create room",
            )

        # 如果有房间，就获取房间。
        room = game_server.get_room(payload.user_name)
        assert room is not None

        if room._tcg_game is None:

            # 创建玩家客户端
            room._player_session = PlayerSession(
                name=payload.user_name,
                actor=payload.actor_name,
                game=payload.game_name,
            )
            assert room._player_session is not None, "房间玩家客户端实例不存在"

            # 创建游戏
            room._tcg_game = setup_web_game_session(
                user=payload.user_name,
                game=payload.game_name,
                actor=payload.actor_name,
                player_session=room._player_session,
            )

            assert room._tcg_game is not None, "Web game setup failed"
            if room._tcg_game is None:
                logger.error(f"创建游戏失败 = {payload.game_name}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"start/v1: {payload.user_name} failed to create game",
                )

            assert room._tcg_game is not None, "房间游戏实例不存在"
            assert room._player_session is not None, "房间玩家客户端实例不存在"

            # 初始化游戏
            logger.info(f"start/v1: {payload.user_name} init game!")
            await room._tcg_game.initialize()

        else:
            assert False, "游戏已经在进行中，无法重新启动! 尚未实现！"

        assert room._tcg_game is not None
        return StartResponse(
            message=f"启动游戏成功！",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"start/v1: {payload.user_name} failed, error: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
def setup_web_game_session(
    user: str,
    game: str,
    actor: str,
    player_session: PlayerSession,
) -> Optional[TCGGame]:

    world_exists = get_user_world_data(user, game)
    if world_exists is None:

        # 如果没有world数据，就创建一个新的world
        world_boot = get_game_boot_data(game)
        assert world_boot is not None, "world_boot is None"

        # 重新生成world
        world_exists = World(boot=world_boot)

        # 测试：如果是demo游戏，就创建demo地下城
        world_exists.dungeon = create_demo_dungeon4()

    else:
        assert False, "尚未实现从数据库加载world的逻辑"

    # 依赖注入，创建新的游戏
    assert world_exists is not None, "World data must exist to create a game"
    web_game = TCGGame(
        name=game,
        player_session=player_session,
        world=world_exists,
    )

    # 启动游戏的判断，是第一次建立还是恢复？
    if len(web_game.world.entities_serialization) == 0:
        logger.info(f"游戏中没有实体 = {game}, 说明是第一次创建游戏")

        # 直接构建ecs
        web_game.new_game().save()
    else:
        logger.info(f"游戏中有实体 = {game}，需要通过数据恢复实体，是游戏回复的过程")

        # 测试！回复ecs
        web_game.load_game().save()

    # 出现了错误。
    player_entity = web_game.get_player_entity()
    # assert player_entity is not None
    if player_entity is None:
        logger.error(f"没有找到玩家实体 = {actor}")
        return None

    return web_game


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
