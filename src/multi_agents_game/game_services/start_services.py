from fastapi import APIRouter, HTTPException, status
from ..game_services.game_server import GameServerInstance
from ..models import StartRequest, StartResponse, Boot, World
from ..game.options import WebUserSessionOptions
from loguru import logger
from ..game.tcg_game_demo import (
    create_demo_dungeon2,
)
from ..chaos_engineering.empty_engineering_system import EmptyChaosEngineeringSystem
from ..chat_services.chat_system import ChatSystem
from typing import Optional
from ..game.web_tcg_game import WebTCGGame
from ..player.player_proxy import PlayerProxy
from ..config.server_config import chat_server_localhost_urls

###################################################################################################################################################################
start_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@start_router.post(path="/start/v1/", response_model=StartResponse)
async def start(
    request_data: StartRequest,
    game_server: GameServerInstance,
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
        web_user_session_options = WebUserSessionOptions(
            user=request_data.user_name,
            game=request_data.game_name,
            actor=request_data.actor_name,
        )

        if room.game is None:
            # 如果没有游戏对象，就‘创建/复位’一个游戏。
            active_game_session = setup_web_game_session(
                web_user_session_options=web_user_session_options,
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
    web_user_session_options: WebUserSessionOptions,
) -> Optional[WebTCGGame]:

    # 创建runtime
    start_world = World()

    if not web_user_session_options.world_runtime_file.exists():

        # 如果runtime文件不存在，说明是第一次启动，直接从gen文件中读取.
        assert web_user_session_options.gen_world_boot_file.exists()

        # 假设有文件，直接读取
        world_boot_file_content = (
            web_user_session_options.gen_world_boot_file.read_text(encoding="utf-8")
        )

        # 重新生成boot
        world_boot = Boot.model_validate_json(world_boot_file_content)

        # 重新生成world
        start_world = World(boot=world_boot)

        # 运行时生成地下城系统。
        start_world.dungeon = create_demo_dungeon2()

    else:

        # runtime文件存在，需要做恢复
        world_runtime_file_content = (
            web_user_session_options.world_runtime_file.read_text(encoding="utf-8")
        )

        # 重新生成world,直接反序列化。
        start_world = World.model_validate_json(world_runtime_file_content)

    # 依赖注入，创建新的游戏
    web_game = WebTCGGame(
        name=web_user_session_options.game,
        player=PlayerProxy(
            name=web_user_session_options.user, actor=web_user_session_options.actor
        ),
        world=start_world,
        world_path=web_user_session_options.world_runtime_file,
        chat_system=ChatSystem(
            name=f"{web_user_session_options.game}-chatsystem",
            username=web_user_session_options.user,
            localhost_urls=chat_server_localhost_urls(),
        ),
        chaos_engineering_system=EmptyChaosEngineeringSystem(),
    )

    # 启动游戏的判断，是第一次建立还是恢复？
    if len(web_game.world.entities_snapshot) == 0:
        logger.warning(
            f"游戏中没有实体 = {web_user_session_options.game}, 说明是第一次创建游戏"
        )

        # 直接构建ecs
        web_game.new_game().save()
    else:
        logger.warning(
            f"游戏中有实体 = {web_user_session_options.game}，需要通过数据恢复实体，是游戏回复的过程"
        )

        # 测试！回复ecs
        web_game.load_game().save()

    # 出现了错误。
    player_entity = web_game.get_player_entity()
    assert player_entity is not None
    if player_entity is None:
        logger.error(f"没有找到玩家实体 = {web_user_session_options.actor}")
        return None

    return web_game


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
