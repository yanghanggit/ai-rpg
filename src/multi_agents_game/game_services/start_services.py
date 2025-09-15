from typing import Optional
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..chat_services.manager import ChatClientManager
from ..demo.stage_dungeon4 import (
    create_demo_dungeon4,
)
from ..game.player_client import PlayerClient
from ..game.web_tcg_game import WebTCGGame, WebGameUserOptions
from ..game_services.game_server import GameServerInstance
from ..models import StartRequest, StartResponse, World
from ..settings.server_settings import ServerSettingsInstance

###################################################################################################################################################################
start_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@start_router.post(path="/api/start/v1/", response_model=StartResponse)
async def start(
    request_data: StartRequest,
    game_server: GameServerInstance,
    server_settings: ServerSettingsInstance,
) -> StartResponse:

    logger.info(f"/start/v1/: {request_data.model_dump_json()}")

    try:

        # 如果没有房间，就创建一个
        room_manager = game_server.room_manager
        if not room_manager.has_room(request_data.user_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"start/v1: {request_data.user_name} not found, create room",
            )

        # 如果有房间，就获取房间。
        room = room_manager.get_room(request_data.user_name)
        assert room is not None

        # 转化成复杂参数
        web_user_session_options = WebGameUserOptions(
            user=request_data.user_name,
            game=request_data.game_name,
            actor=request_data.actor_name,
        )

        if room.game is None:
            # 如果没有游戏对象，就‘创建/复位’一个游戏。
            active_game_session = setup_web_game_session(
                web_game_user_options=web_user_session_options,
                server_settings=server_settings,
            )

            if active_game_session is None:
                logger.error(f"创建游戏失败 = {web_user_session_options.game}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"start/v1: {request_data.user_name} failed to create game",
                )

            room.game = active_game_session
        else:
            # 是继续玩
            logger.info(f"start/v1: {request_data.user_name} has room, is running!")

        assert room.game is not None
        return StartResponse(
            message=f"启动游戏成功！",
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"start/v1: {request_data.user_name} failed, error: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
def setup_web_game_session(
    web_game_user_options: WebGameUserOptions,
    server_settings: ServerSettingsInstance,
) -> Optional[WebTCGGame]:

    world_exists = web_game_user_options.world_data
    if world_exists is None:

        # 如果没有world数据，就创建一个新的world
        world_boot = web_game_user_options.world_boot_data
        assert world_boot is not None, "world_boot is None"

        # 重新生成world
        world_exists = World(boot=world_boot)

        # 运行时生成地下城系统。
        world_exists.dungeon = create_demo_dungeon4()

    else:
        pass

    # 依赖注入，创建新的游戏
    assert world_exists is not None, "World data must exist to create a game"
    web_game = WebTCGGame(
        name=web_game_user_options.game,
        player=PlayerClient(
            name=web_game_user_options.user, actor=web_game_user_options.actor
        ),
        world=world_exists,
        chat_system=ChatClientManager(
            # name=f"{web_game_user_options.game}-chatsystem",
            azure_openai_chat_server_localhost_urls=server_settings.azure_openai_chat_server_localhost_urls,
            deepseek_chat_server_localhost_urls=server_settings.deepseek_chat_server_localhost_urls,
        ),
    )

    # 启动游戏的判断，是第一次建立还是恢复？
    if len(web_game.world.entities_snapshot) == 0:
        logger.warning(
            f"游戏中没有实体 = {web_game_user_options.game}, 说明是第一次创建游戏"
        )

        # 直接构建ecs
        web_game.new_game().save()
    else:
        logger.warning(
            f"游戏中有实体 = {web_game_user_options.game}，需要通过数据恢复实体，是游戏回复的过程"
        )

        # 测试！回复ecs
        web_game.load_game().save()

    # 出现了错误。
    player_entity = web_game.get_player_entity()
    assert player_entity is not None
    if player_entity is None:
        logger.error(f"没有找到玩家实体 = {web_game_user_options.actor}")
        return None

    return web_game


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
