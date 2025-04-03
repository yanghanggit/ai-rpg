from typing import Optional
from fastapi import APIRouter
from services.game_server_instance import GameServerInstance
from models_v_0_0_1.api import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
)
from loguru import logger
from game.user_session_options import UserSessionOptions
from game.tcg_game_demo import (
    create_then_write_demo_world,
    actor_warrior,
    stage_dungeon_cave1,
    stage_dungeon_cave2,
)
import shutil
from models_v_0_0_1.world import Boot, World
from models_v_0_0_1.dungeon import Dungeon
from chaos_engineering.empty_engineering_system import EmptyChaosEngineeringSystem
from extended_systems.lang_serve_system import LangServeSystem
from game.web_tcg_game import WebTCGGame
from player.player_proxy import PlayerProxy

###################################################################################################################################################################
login_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@login_router.post(path="/login/v1/", response_model=LoginResponse)
async def login(
    request_data: LoginRequest,
    game_server: GameServerInstance,
) -> LoginResponse:

    logger.info(f"login/v1: {request_data.model_dump_json()}")

    room_manager = game_server.room_manager

    # TODO, 每次都创建新的，有旧的先删除。 ########################################
    if room_manager.has_room(request_data.user_name):
        pre_room = room_manager.get_room(request_data.user_name)
        assert pre_room is not None
        logger.info(
            f"login: {request_data.user_name} has room, remove it = {pre_room._user_name}"
        )
        room_manager.remove_room(pre_room)

    # 创建一个新的房间 ########################################
    new_room = room_manager.create_room(
        user_name=request_data.user_name,
    )
    logger.info(f"login: {request_data.user_name} create room = {new_room._user_name}")
    assert new_room._game is None

    # 准备创建一个新的游戏。########################################

    option = UserSessionOptions(
        user="yanghang",
        game="Game1",
        new_game=True,
        server_setup_config="gen_configs/start_llm_serves.json",
        langserve_localhost_urls=[],
    ).setup()

    web_game_session = setup_game_session(
        option=option,
    )

    if web_game_session is None:
        logger.error(f"创建游戏失败 = {option.game}")
        return LoginResponse(
            error=1000,
            message="创建游戏失败",
        )

    # 房间正常完成, 新的游戏也准备好了。。。。
    new_room._game = web_game_session
    player_entity = web_game_session.get_player_entity()
    assert player_entity is not None

    logger.info(
        f"login: {request_data.user_name} create game = {new_room._game.name}, player = {web_game_session.player._name}, actor = {player_entity._name}"
    )
    return LoginResponse(
        actor=player_entity._name,
        error=0,
        message=new_room._game.world.model_dump_json(),
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@login_router.post(path="/logout/v1/", response_model=LogoutResponse)
async def logout(
    request_data: LogoutRequest,
    game_server: GameServerInstance,
) -> LogoutResponse:

    logger.info(f"logout: {request_data.model_dump_json()}")

    # 先检查房间是否存在
    room_manager = game_server.room_manager
    if not room_manager.has_room(request_data.user_name):
        logger.error(f"logout: {request_data.user_name} not found")
        return LogoutResponse(
            error=1001,
            message="没有找到房间",
        )

    # 删除房间
    pre_room = room_manager.get_room(request_data.user_name)
    assert pre_room is not None
    if pre_room._game is not None:
        # 保存游戏的运行时数据
        logger.info(
            f"logout: {request_data.user_name} save game = {pre_room._game.name}"
        )
        pre_room._game.save()
        # 退出游戏
        logger.info(
            f"logout: {request_data.user_name} exit game = {pre_room._game.name}"
        )
        # 退出游戏
        pre_room._game.exit()

    else:
        logger.info(f"logout: {request_data.user_name} no game = {pre_room._user_name}")

    logger.info(f"logout: {request_data.user_name} remove room = {pre_room._user_name}")
    room_manager.remove_room(pre_room)
    return LogoutResponse(
        error=0,
        message=f"logout: {request_data.user_name} success",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
def setup_game_session(option: UserSessionOptions) -> Optional[WebTCGGame]:

    # 这里是临时的TODO
    demo_edit_boot = create_then_write_demo_world(
        option.game, option.gen_world_boot_file
    )
    assert demo_edit_boot is not None
    if demo_edit_boot is None:
        logger.error(f"创建游戏世界失败 = {option.game}")
        return None

    # 如果是新游戏，需要将game_resource_file_path这个文件拷贝一份到world_boot_file_path下
    if option.new_game:

        # 清除用户的运行时目录, 重新生成
        option.clear_runtime_dir()

        # 游戏资源可以被创建，则将game_resource_file_path这个文件拷贝一份到world_boot_file_path下
        shutil.copy(option.gen_world_boot_file, option.world_runtime_dir)

    # 创建runtime
    start_world = World()

    #
    if not option.world_runtime_file.exists():
        # 肯定是新游戏
        assert option.new_game
        # 如果runtime文件不存在，说明是第一次启动，直接从gen文件中读取.
        assert option.gen_world_boot_file.exists()

        # 假设有文件，直接读取
        world_boot_file_content = option.gen_world_boot_file.read_text(encoding="utf-8")

        # 重新生成boot
        world_boot = Boot.model_validate_json(world_boot_file_content)

        # 重新生成world
        start_world = World(boot=world_boot)

        # 运行时生成地下城系统。
        start_world.dungeon = Dungeon(
            name="哥布林与兽人",
            levels=[stage_dungeon_cave1, stage_dungeon_cave2],
        )

    else:

        # 如果runtime文件存在，说明是恢复游戏
        assert not option.new_game

        # runtime文件存在，需要做恢复
        world_runtime_file_content = option.world_runtime_file.read_text(
            encoding="utf-8"
        )

        # 重新生成world,直接反序列化。
        start_world = World.model_validate_json(world_runtime_file_content)

    ### 创建一些子系统。!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    ### 创建一些子系统。!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

    # 依赖注入，创建新的游戏
    terminal_game = WebTCGGame(
        name=option.game,
        player=PlayerProxy(name=option.user, actor=actor_warrior.name),
        world=start_world,
        world_path=option.world_runtime_file,
        langserve_system=LangServeSystem(
            f"{option.game}-langserve_system",
            localhost_urls=option.langserve_localhost_urls,
        ),
        chaos_engineering_system=EmptyChaosEngineeringSystem(),
    )

    # 启动游戏的判断，是第一次建立还是恢复？
    if len(terminal_game.world.entities_snapshot) == 0:
        assert option.new_game
        logger.warning(f"游戏中没有实体 = {option.game}, 说明是第一次创建游戏")

        # 直接构建ecs
        terminal_game.new_game().save()
    else:
        assert not option.new_game
        logger.warning(
            f"游戏中有实体 = {option.game}，需要通过数据恢复实体，是游戏回复的过程"
        )

        # 测试！回复ecs
        terminal_game.load_game().save()

    return terminal_game


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
