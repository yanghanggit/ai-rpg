import datetime
from fastapi import APIRouter
from loguru import logger
from models.api_models import (
    LoginRequest,
    LoginResponse,
    CreateRequest,
    CreateResponse,
    JoinRequest,
    JoinResponse,
    StartRequest,
    StartResponse,
    ExitRequest,
    ExitResponse,
    ExecuteRequest,
    ExecuteResponse,
    FetchMessagesRequest,
    FetchMessagesResponse,
)
from typing import Optional
import game.rpg_game_utils
from player.player_proxy import PlayerProxy
import game.rpg_game_config
import shutil
from models.player_models import PlayerProxyModel
from models.config_models import (
    GlobalConfigModel,
    GameConfigModel,
)
from services.game_state_manager import GameState
from services.game_server_instance import GameServerInstance

game_process_api_router = APIRouter()


###############################################################################################################################################
def _match_game_with_players(
    game_name: str, game_manager_model: GlobalConfigModel
) -> Optional[GameConfigModel]:
    for game_config in game_manager_model.game_configs:
        if game_config.game_name != game_name:
            continue
        if len(game_config.players) == 0:
            continue
        return game_config

    return None


###############################################################################################################################################
@game_process_api_router.post(path="/login/", response_model=LoginResponse)
async def login(
    request_data: LoginRequest, game_server: GameServerInstance
) -> LoginResponse:

    logger.info(f"login: {request_data.user_name}")

    room_manager = game_server.room_manager

    # 已经有房间不能登录，因为一个用户只能有一个房间
    if room_manager.has_room(request_data.user_name):
        return LoginResponse(
            user_name=request_data.user_name,
            error=100,
            message=f"has_room = {request_data.user_name}",
        )

    try:
        # 读取游戏配置
        game_manager_config_file_path = (
            game.rpg_game_config.ROOT_GEN_GAMES_DIR / "config.json"
        )
        assert game_manager_config_file_path.exists()

        room_manager.global_config = GlobalConfigModel.model_validate_json(
            game_manager_config_file_path.read_text(encoding="utf-8")
        )

    except Exception as e:
        logger.error(e)
        return LoginResponse(
            user_name=request_data.user_name,
            error=101,
            message=f"has_room = {request_data.user_name}",
        )

    # 创建一个新的房间
    new_room = room_manager.create_room(request_data.user_name)
    assert new_room.state == GameState.UNLOGGED

    # 切换状态到登录成功
    new_room.state_controller.transition(GameState.LOGGED_IN)
    logger.info(f"login success, user_name = {request_data.user_name}")

    # 返回游戏列表
    return LoginResponse(
        user_name=request_data.user_name,
        global_config=room_manager.global_config,
    )


###############################################################################################################################################
@game_process_api_router.post(path="/create/", response_model=CreateResponse)
async def create(
    request_data: CreateRequest, game_server: GameServerInstance
) -> CreateResponse:
    logger.info(f"create: {request_data.user_name}, {request_data.game_name}")

    room_manager = game_server.room_manager

    # 没有房间不能创建游戏
    if not room_manager.has_room(request_data.user_name):
        return CreateResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            error=100,
            message=f"not has_room = {request_data.user_name}",
        )

    user_room = room_manager.get_room(request_data.user_name)
    assert user_room is not None

    # 不能转化到创建一个新游戏的状态！可能已经被创建了。
    if not user_room.state_controller.can_transition(GameState.GAME_CREATED):
        return CreateResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            error=101,
            message=f"not user_room.state.can_transition(GameState.GAME_CREATED), current state = {user_room.state}",
        )

    if (
        _match_game_with_players(request_data.game_name, room_manager.global_config)
        is None
    ):
        # 不是一个可以选择的游戏！里面没有玩家可以操纵的角色
        return CreateResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            error=102,
            message=f"game_name not in GAME_LIST = {request_data.game_name}",
        )

    # 准备这个app的运行时路径，用于存放游戏的运行时数据
    game_runtime_dir = (
        game.rpg_game_config.GAMES_RUNTIME_DIR
        / request_data.user_name
        / request_data.game_name
    )
    if game_runtime_dir.exists():
        shutil.rmtree(game_runtime_dir)

    game_runtime_dir.mkdir(parents=True, exist_ok=True)
    assert game_runtime_dir.exists()

    # 创建log
    log_start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_dir = (
        game.rpg_game_config.LOGS_DIR / request_data.user_name / request_data.game_name
    )
    logger.add(log_dir / f"{log_start_time}.log", level="DEBUG")

    # 游戏启动资源路径
    game_resource_file_path = (
        game.rpg_game_config.ROOT_GEN_GAMES_DIR / f"{request_data.game_name}.json"
    )

    if not game_resource_file_path.exists():
        # 如果找不到游戏资源文件就退出
        return CreateResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            error=103,
            message=f"game_resource_file_path not exists = {game_resource_file_path}",
        )

    # 创建游戏资源
    game_resource = game.rpg_game_utils.create_game_resource(
        game_resource_file_path,
        game_runtime_dir,
        game.rpg_game_config.CHECK_GAME_RESOURCE_VERSION,
    )
    if game_resource is None:
        return CreateResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            error=104,
            message=f"game_resource is None",
        )

    # 游戏资源可以被创建，则将game_resource_file_path这个文件拷贝一份到root_runtime_dir下
    shutil.copy(
        game_resource_file_path, game_runtime_dir / game_resource_file_path.name
    )

    # 创建游戏
    web_rpg_game = game.rpg_game_utils.create_web_rpg_game(game_resource)
    if web_rpg_game is None or web_rpg_game._game_resource is None:
        logger.error(f"create_rpg_game 失败 = {request_data.game_name}")
        return CreateResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            error=105,
            message=f"create_rpg_game 失败 = {request_data.game_name}",
        )

    # 检查是否有可以控制的角色, 没有就不让玩, 因为是客户端进来的。没有可以控制的觉得暂时就不允许玩。
    player_actors = game.rpg_game_utils.list_player_actors(web_rpg_game)
    if len(player_actors) == 0:
        logger.warning(f"create_rpg_game 没有可以控制的角色 = {request_data.game_name}")
        return CreateResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            error=106,
            message=f"create_rpg_game 没有可以控制的角色 = {request_data.game_name}",
        )

    logger.info(f"create: {request_data.user_name}, {request_data.game_name}")

    # 切换状态到游戏创建完成。
    user_room._game = web_rpg_game
    user_room.state_controller.transition(GameState.GAME_CREATED)

    # 返回可以选择的角色，以及游戏模型
    return CreateResponse(
        user_name=request_data.user_name,
        game_name=request_data.game_name,
        selectable_actors=player_actors,
        game_model=web_rpg_game._game_resource._model,
    )


###############################################################################################################################################
@game_process_api_router.post(path="/join/", response_model=JoinResponse)
async def join(
    request_data: JoinRequest, game_server: GameServerInstance
) -> JoinResponse:
    logger.info(
        f"join: {request_data.user_name}, {request_data.game_name}, {request_data.actor_name}"
    )

    room_manager = game_server.room_manager

    if not room_manager.has_room(request_data.user_name):
        return JoinResponse(user_name=request_data.user_name, error=100, message="")

    user_room = room_manager.get_room(request_data.user_name)
    assert user_room is not None

    # 不能转化到游戏加入完成的状态！
    if (
        not user_room.state_controller.can_transition(GameState.GAME_JOINED)
        or user_room.game is None
    ):
        return JoinResponse(user_name=request_data.user_name, error=101, message="")

    # 没有角色不能加入游戏
    if request_data.actor_name == "":
        return JoinResponse(user_name=request_data.user_name, error=102, message="")

    logger.info(
        f"join: {request_data.user_name}, {request_data.game_name}, {request_data.actor_name}"
    )

    # 切换状态到游戏加入完成
    user_room.state_controller.transition(GameState.GAME_JOINED)
    player_proxy = PlayerProxy(PlayerProxyModel(player_name=request_data.user_name))
    user_room.game.add_player(player_proxy)

    # 加入游戏
    game.rpg_game_utils.play_new_game(
        user_room.game, player_proxy, request_data.actor_name
    )

    # 返回加入游戏的信息
    return JoinResponse(
        user_name=request_data.user_name,
        game_name=request_data.game_name,
        actor_name=request_data.actor_name,
    )


###############################################################################################################################################
@game_process_api_router.post(path="/start/", response_model=StartResponse)
async def start(
    request_data: StartRequest, game_server: GameServerInstance
) -> StartResponse:
    logger.info(
        f"start: {request_data.user_name}, {request_data.game_name}, {request_data.actor_name}"
    )

    room_manager = game_server.room_manager

    if not room_manager.has_room(request_data.user_name):
        return StartResponse(user_name=request_data.user_name, error=100, message="")

    user_room = room_manager.get_room(request_data.user_name)
    assert user_room is not None

    # 不能切换状态到游戏开始
    if (
        not user_room.state_controller.can_transition(GameState.PLAYING)
        or user_room.game is None
    ):
        return StartResponse(user_name=request_data.user_name, error=101, message="")

    logger.info(
        f"start: {request_data.user_name}, {request_data.game_name}, {request_data.actor_name}"
    )

    # 切换状态到游戏开始
    user_room.state_controller.transition(GameState.PLAYING)
    player_proxy = user_room.get_player()
    assert player_proxy is not None
    if player_proxy is None:
        return StartResponse(user_name=request_data.user_name, error=102, message="")

    # 返回开始游戏的信息
    return StartResponse(
        user_name=request_data.user_name,
        game_name=request_data.game_name,
        actor_name=request_data.actor_name,
        total=len(player_proxy.client_messages),
    )


###############################################################################################################################################
@game_process_api_router.post(path="/execute/", response_model=ExecuteResponse)
async def execute(
    request_data: ExecuteRequest, game_server: GameServerInstance
) -> ExecuteResponse:
    logger.info(
        f"execute: {request_data.user_name}, {request_data.game_name}, {request_data.user_input}"
    )

    room_manager = game_server.room_manager

    if not room_manager.has_room(request_data.user_name):
        return ExecuteResponse(user_name=request_data.user_name, error=100, message="")

    user_room = room_manager.get_room(request_data.user_name)
    assert user_room is not None

    if user_room.game is None:
        return ExecuteResponse(user_name=request_data.user_name, error=101, message="")

    # 状态不对不能运行
    if user_room.state != GameState.PLAYING:
        return ExecuteResponse(
            user_name=request_data.user_name,
            error=102,
            message=f"server_state.state != GameState.PLAYING, current state = {user_room.state}",
        )

    # 不能切换状态到游戏退出
    if user_room.game._will_exit:
        return ExecuteResponse(
            user_name=request_data.user_name,
            error=103,
            message="game_room._game._will_exit",
        )

    #  没有游戏角色不能推动游戏，这里规定必须要有客户端和角色才能推动游戏
    player_proxy = user_room.get_player()
    if player_proxy is None:
        return ExecuteResponse(
            user_name=request_data.user_name, error=104, message="player_proxy is None"
        )

    # 人物死亡了，不能推动游戏
    if player_proxy.is_player_dead:
        return ExecuteResponse(
            user_name=request_data.user_name, error=105, message="player_proxy.over"
        )

    # 如果有输入命令，就要加
    for usr_input in request_data.user_input:
        assert (
            usr_input != "/survey_stage_action" and usr_input != "/ssa"
        ), "不应该有这个命令"
        assert (
            usr_input != "/status_inventory_check_action" and usr_input != "/sica"
        ), "不应该有这个命令"
        assert (
            usr_input != "/retrieve_actor_archives" and usr_input != "/raa"
        ), "不应该有这个命令"
        assert (
            usr_input != "/retrieve_stage_archives" and usr_input != "/rsa"
        ), "不应该有这个命令"

        game.rpg_game_utils.add_command(user_room.game, player_proxy, usr_input)

    if not user_room.game._will_exit:
        await user_room.game.a_execute()

    turn_player_actors = game.rpg_game_utils.list_planning_player_actors(user_room.game)

    # 返回执行游戏的信息
    return ExecuteResponse(
        user_name=request_data.user_name,
        game_name=request_data.game_name,
        actor_name=user_room.get_player_actor_name(),
        turn_player_actor=turn_player_actors[0] if len(turn_player_actors) > 0 else "",
        total=len(player_proxy.client_messages),
        game_round=user_room.game.current_round,
    )


###############################################################################################################################################
@game_process_api_router.post(
    path="/fetch_messages/", response_model=FetchMessagesResponse
)
async def fetch_messages(
    request_data: FetchMessagesRequest, game_server: GameServerInstance
) -> FetchMessagesResponse:

    room_manager = game_server.room_manager

    # 不能获取消息
    if request_data.index < 0 or request_data.count <= 0:
        return FetchMessagesResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=100,
            message=f"request_data.index = {request_data.index}, request_data.count = {request_data.count}",
        )

    # 没有房间不能获取消息
    if not room_manager.has_room(request_data.user_name):
        return FetchMessagesResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=101,
            message="not has_room",
        )

    user_room = room_manager.get_room(request_data.user_name)
    assert user_room is not None

    if user_room.game is None:
        return FetchMessagesResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=102,
            message=f"game_room._game is None, request_data.index = {request_data.index}, request_data.count = {request_data.count}",
        )

    # 没有客户端就不能看
    player_proxy = user_room.get_player()
    if player_proxy is None:
        return FetchMessagesResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=103,
            message="player_proxy is None",
        )

    #
    fetch_messages = player_proxy.fetch_client_messages(
        request_data.index, request_data.count
    )

    # 临时输出一下。
    logger.warning(
        f"fetch_messages, player = {player_proxy.player_name}, count = {len(fetch_messages)}"
    )
    for fetch_message in fetch_messages:
        json_str = fetch_message.model_dump_json()
        logger.warning(json_str)

    return FetchMessagesResponse(
        user_name=request_data.user_name,
        game_name=request_data.game_name,
        actor_name=request_data.actor_name,
        messages=fetch_messages,
        total=len(player_proxy.client_messages),
        game_round=user_room.game.current_round,
    )


###############################################################################################################################################
@game_process_api_router.post(path="/exit/", response_model=ExitResponse)
async def exit(
    request_data: ExitRequest, game_server: GameServerInstance
) -> ExitResponse:

    room_manager = game_server.room_manager

    if not room_manager.has_room(request_data.user_name):
        return ExitResponse(user_name=request_data.user_name, error=100, message="")

    user_room = room_manager.get_room(request_data.user_name)
    assert user_room is not None

    # 不能切换状态到游戏退出
    if (
        not user_room.state_controller.can_transition(GameState.REQUESTING_EXIT)
        or user_room.game is None
    ):
        return ExitResponse(user_name=request_data.user_name, error=101, message="")

    logger.info(f"exit: {request_data.user_name}")

    # 切换状态到游戏退出
    user_room.state_controller.transition(GameState.REQUESTING_EXIT)

    # 当前的游戏杀掉
    user_room.game._will_exit = True
    game.rpg_game_utils.save_game(
        rpg_game=user_room.game,
        archive_dir=game.rpg_game_config.GAMES_ARCHIVE_DIR / request_data.user_name,
    )
    user_room.game.exit()

    # 退出游戏
    room_manager.remove_room(user_room)

    # 返回退出游戏的信息
    return ExitResponse(
        user_name=request_data.user_name, game_name=request_data.game_name
    )


###############################################################################################################################################
