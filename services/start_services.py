from fastapi import APIRouter
from services.game_server_instance import GameServerInstance
from models_v_0_0_1 import StartRequest, StartResponse, Boot, World
from game.startup_options import UserSessionOptions, ChatSystemOptions
from loguru import logger
from game.tcg_game_demo import (
    create_demo_dungeon2,
)
from chaos_engineering.empty_engineering_system import EmptyChaosEngineeringSystem
from llm_serves.chat_system import ChatSystem
from typing import Optional
from game.web_tcg_game import WebTCGGame
from player.player_proxy import PlayerProxy


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

    logger.info(f"start/v1: {request_data.model_dump_json()}")

    # 如果没有房间，就创建一个
    room_manager = game_server.room_manager
    if not room_manager.has_room(request_data.user_name):
        logger.error(f"start/v1: {request_data.user_name} not found, create room")
        return StartResponse(
            error=1000,
            message="房间不存在，请先登录",
        )

    # 如果有房间，就获取房间。
    room = room_manager.get_room(request_data.user_name)
    assert room is not None

    # 转化成复杂参数
    user_session_options = UserSessionOptions(
        user=request_data.user_name,
        game=request_data.game_name,
        new_game=True,
        actor=request_data.actor_name,
    )

    # 创建ChatSystemOptions
    chat_system_setup_options = ChatSystemOptions(
        user=user_session_options.user,
        game=user_session_options.game,
        server_setup_config="gen_configs/start_llm_serves.json",
    )

    if room._game is None:
        # 如果没有游戏对象，就‘创建/复位’一个游戏。
        active_game_session = setup_web_game_session(
            user_session_options=user_session_options,
            chat_system_setup_options=chat_system_setup_options,
        )

        if active_game_session is None:
            logger.error(f"创建游戏失败 = {user_session_options.game}")
            return StartResponse(
                error=1000,
                message="创建游戏失败",
            )

        room._game = active_game_session
    else:
        # 是继续玩
        logger.info(f"start/v1: {request_data.user_name} has room, is running!")

    assert room._game is not None
    return StartResponse(
        error=0,
        message=f"启动游戏成功！",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
def setup_web_game_session(
    user_session_options: UserSessionOptions,
    chat_system_setup_options: ChatSystemOptions,
) -> Optional[WebTCGGame]:

    # 创建runtime
    start_world = World()

    if not user_session_options.world_runtime_file.exists():

        # 如果runtime文件不存在，说明是第一次启动，直接从gen文件中读取.
        assert user_session_options.gen_world_boot_file.exists()

        # 假设有文件，直接读取
        world_boot_file_content = user_session_options.gen_world_boot_file.read_text(
            encoding="utf-8"
        )

        # 重新生成boot
        world_boot = Boot.model_validate_json(world_boot_file_content)

        # 重新生成world
        start_world = World(boot=world_boot)

        # 运行时生成地下城系统。
        start_world.dungeon = create_demo_dungeon2(name="兽人巢穴")

    else:

        # runtime文件存在，需要做恢复
        world_runtime_file_content = user_session_options.world_runtime_file.read_text(
            encoding="utf-8"
        )

        # 重新生成world,直接反序列化。
        start_world = World.model_validate_json(world_runtime_file_content)

    # 依赖注入，创建新的游戏
    web_game = WebTCGGame(
        name=user_session_options.game,
        player=PlayerProxy(
            name=user_session_options.user, actor=user_session_options.actor
        ),
        world=start_world,
        world_path=user_session_options.world_runtime_file,
        chat_system=ChatSystem(
            name=f"{chat_system_setup_options.game}-chatsystem",
            user_name=chat_system_setup_options.user,
            localhost_urls=chat_system_setup_options.localhost_urls,
        ),
        chaos_engineering_system=EmptyChaosEngineeringSystem(),
    )

    # 启动游戏的判断，是第一次建立还是恢复？
    if len(web_game.world.entities_snapshot) == 0:
        logger.warning(
            f"游戏中没有实体 = {user_session_options.game}, 说明是第一次创建游戏"
        )

        # 直接构建ecs
        web_game.new_game().save()
    else:
        logger.warning(
            f"游戏中有实体 = {user_session_options.game}，需要通过数据恢复实体，是游戏回复的过程"
        )

        # 测试！回复ecs
        web_game.load_game().save()

    # 出现了错误。
    player_entity = web_game.get_player_entity()
    assert player_entity is not None
    if player_entity is None:
        logger.error(f"没有找到玩家实体 = {user_session_options.actor}")
        return None

    return web_game


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
