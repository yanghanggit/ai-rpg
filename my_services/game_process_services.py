from fastapi import APIRouter
from loguru import logger
from ws_config import (
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
from typing import Dict, Any, Optional
import rpg_game.rpg_game_helper
from player.player_proxy import PlayerProxy
import rpg_game.rpg_game_config as rpg_game_config
import shutil
from my_models.player_models import PlayerProxyModel
from my_models.config_models import (
    GenGamesConfigModel,
    OneGameConfigModel,
)
from my_services.game_state_manager import GameState
from my_services.room_manager import (
    Room,
    RoomManagerInstance,
)

game_process_api_router = APIRouter()


###############################################################################################################################################
@game_process_api_router.post("/login/")
async def login(request_data: LoginRequest) -> Dict[str, Any]:
    logger.info(f"login: {request_data.user_name}")

    # 不能切换状态，到登陆完成
    if not RoomManagerInstance._state.can_transition(GameState.LOGGED_IN):
        return LoginResponse(
            user_name=request_data.user_name,
            error=1,
            message=f"not server_state.can_transition(GameState.LOGGED_IN), current state = {RoomManagerInstance._state.state}",
        ).model_dump()

    logger.info(f"login success, user_name = {request_data.user_name}")

    # 切换状态到登陆完成并创建一个房间
    RoomManagerInstance._state.transition(GameState.LOGGED_IN)
    RoomManagerInstance._room = Room(request_data.user_name)

    # 读config.json
    config_file_config = rpg_game_config.ROOT_GEN_GAMES_DIR / f"config.json"
    assert config_file_config.exists()
    read_config_content = config_file_config.read_text(encoding="utf-8")
    RoomManagerInstance._game_config = GenGamesConfigModel.model_validate_json(
        read_config_content
    )

    # 返回游戏列表
    return LoginResponse(
        user_name=request_data.user_name,
        game_config=RoomManagerInstance._game_config,
    ).model_dump()


###############################################################################################################################################
def _match_create_enabled_config(
    game_name: str, game_config: GenGamesConfigModel
) -> Optional[OneGameConfigModel]:

    for one_game_config in game_config.game_configs:
        if one_game_config.game_name != game_name:
            continue

        if len(one_game_config.players) == 0:
            continue

        return one_game_config

    return None


###############################################################################################################################################
@game_process_api_router.post("/create/")
async def create(request_data: CreateRequest) -> Dict[str, Any]:
    logger.info(f"create: {request_data.user_name}, {request_data.game_name}")

    # 不能转化到创建一个新游戏的状态！
    if (
        not RoomManagerInstance._state.can_transition(GameState.GAME_CREATED)
        or RoomManagerInstance._room is None
    ):
        return CreateResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            error=1,
            message=f"not server_state.can_transition(GameState.GAME_CREATED), current state = {RoomManagerInstance._state.state}",
        ).model_dump()

    # 不是一个可以选择的游戏！
    if (
        _match_create_enabled_config(
            request_data.game_name, RoomManagerInstance._game_config
        )
        is None
    ):
        return CreateResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            error=2,
            message=f"game_name not in GAME_LIST = {request_data.game_name}",
        ).model_dump()

    # 准备这个app的运行时路径
    game_runtime_dir = rpg_game_config.GAMES_RUNTIME_DIR / request_data.game_name
    if game_runtime_dir.exists():
        # logger.warning(f"删除文件夹：{game_runtime_dir}, 这是为了测试，后续得改！！！")
        shutil.rmtree(game_runtime_dir)

    game_runtime_dir.mkdir(parents=True, exist_ok=True)
    assert game_runtime_dir.exists()

    # 游戏启动资源路径
    game_resource_file_path = (
        rpg_game_config.ROOT_GEN_GAMES_DIR / f"{request_data.game_name}.json"
    )

    if not game_resource_file_path.exists():
        return CreateResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            error=3,
            message=f"game_resource_file_path not exists = {game_resource_file_path}",
        ).model_dump()

    # 创建游戏资源
    game_resource = rpg_game.rpg_game_helper.create_game_resource(
        game_resource_file_path,
        game_runtime_dir,
        rpg_game_config.CHECK_GAME_RESOURCE_VERSION,
    )
    if game_resource is None:
        return CreateResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            error=4,
            message=f"game_resource is None",
        ).model_dump()

    # 游戏资源可以被创建，则将game_resource_file_path这个文件拷贝一份到root_runtime_dir下
    shutil.copy(
        game_resource_file_path, game_runtime_dir / game_resource_file_path.name
    )

    # 创建游戏
    new_game = rpg_game.rpg_game_helper.create_web_rpg_game(game_resource)
    if new_game is None or new_game._game_resource is None:
        logger.error(f"create_rpg_game 失败 = {request_data.game_name}")
        return CreateResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            error=6,
            message=f"create_rpg_game 失败 = {request_data.game_name}",
        ).model_dump()

    # 检查是否有可以控制的角色, 没有就不让玩, 因为是客户端进来的。没有可以控制的觉得暂时就不允许玩。
    ctrl_actors = rpg_game.rpg_game_helper.get_player_actor_names(new_game)
    if len(ctrl_actors) == 0:
        logger.warning(f"create_rpg_game 没有可以控制的角色 = {request_data.game_name}")
        return CreateResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            error=5,
            message=f"create_rpg_game 没有可以控制的角色 = {request_data.game_name}",
        ).model_dump()

    logger.info(f"create: {request_data.user_name}, {request_data.game_name}")

    # 切换状态到游戏创建完成
    RoomManagerInstance._state.transition(GameState.GAME_CREATED)
    RoomManagerInstance._room._game = new_game

    # 返回可以选择的角色，以及游戏模型
    return CreateResponse(
        user_name=request_data.user_name,
        game_name=request_data.game_name,
        selectable_actors=ctrl_actors,
        game_model=new_game._game_resource._model,
    ).model_dump()


###############################################################################################################################################
@game_process_api_router.post("/join/")
async def join(request_data: JoinRequest) -> Dict[str, Any]:
    logger.info(
        f"join: {request_data.user_name}, {request_data.game_name}, {request_data.actor_name}"
    )

    if (
        not RoomManagerInstance._state.can_transition(GameState.GAME_JOINED)
        or RoomManagerInstance._room is None
        or RoomManagerInstance._room._game is None
    ):
        return JoinResponse(
            user_name=request_data.user_name, error=1, message=""
        ).model_dump()

    if request_data.actor_name == "":
        return JoinResponse(
            user_name=request_data.user_name, error=2, message=""
        ).model_dump()

    logger.info(
        f"join: {request_data.user_name}, {request_data.game_name}, {request_data.actor_name}"
    )

    # 切换状态到游戏加入完成
    RoomManagerInstance._state.transition(GameState.GAME_JOINED)
    player_proxy = PlayerProxy(PlayerProxyModel(name=request_data.user_name))
    RoomManagerInstance._room._game.add_player(player_proxy)

    # 加入游戏
    rpg_game.rpg_game_helper.player_play_new_game(
        RoomManagerInstance._room._game, player_proxy, request_data.actor_name
    )

    # 返回加入游戏的信息
    return JoinResponse(
        user_name=request_data.user_name,
        game_name=request_data.game_name,
        actor_name=request_data.actor_name,
    ).model_dump()


###############################################################################################################################################
@game_process_api_router.post("/start/")
async def start(request_data: StartRequest) -> Dict[str, Any]:
    logger.info(
        f"start: {request_data.user_name}, {request_data.game_name}, {request_data.actor_name}"
    )

    # 不能切换状态到游戏开始
    if (
        not RoomManagerInstance._state.can_transition(GameState.PLAYING)
        or RoomManagerInstance._room is None
        or RoomManagerInstance._room._game is None
    ):
        return StartResponse(
            user_name=request_data.user_name, error=1, message=""
        ).model_dump()

    logger.info(
        f"start: {request_data.user_name}, {request_data.game_name}, {request_data.actor_name}"
    )

    # 切换状态到游戏开始
    RoomManagerInstance._state.transition(GameState.PLAYING)

    player_proxy = RoomManagerInstance._room.get_player()
    if player_proxy is None:
        return StartResponse(
            user_name=request_data.user_name, error=2, message=""
        ).model_dump()

    # 返回开始游戏的信息
    return StartResponse(
        user_name=request_data.user_name,
        game_name=request_data.game_name,
        actor_name=request_data.actor_name,
        total=len(player_proxy.model.client_messages),
    ).model_dump()


###############################################################################################################################################
@game_process_api_router.post("/execute/")
async def execute(request_data: ExecuteRequest) -> Dict[str, Any]:
    logger.info(
        f"execute: {request_data.user_name}, {request_data.game_name}, {request_data.user_input}"
    )

    # 数据不对不能运行
    if RoomManagerInstance._room is None or RoomManagerInstance._room._game is None:
        return ExecuteResponse(
            user_name=request_data.user_name,
            error=100,
            message="game_room._game is None",
        ).model_dump()

    # 状态不对不能运行
    if RoomManagerInstance._state.state != GameState.PLAYING:
        return ExecuteResponse(
            user_name=request_data.user_name,
            error=101,
            message=f"server_state.state != GameState.PLAYING, current state = {RoomManagerInstance._state.state}",
        ).model_dump()

    # 不能切换状态到游戏退出
    if RoomManagerInstance._room._game._will_exit:
        return ExecuteResponse(
            user_name=request_data.user_name,
            error=1,
            message="game_room._game._will_exit",
        ).model_dump()

    #  没有游戏角色不能推动游戏，这里规定必须要有客户端和角色才能推动游戏
    player_proxy = RoomManagerInstance._room.get_player()
    if player_proxy is None:
        return ExecuteResponse(
            user_name=request_data.user_name, error=2, message="player_proxy is None"
        ).model_dump()

    # 人物死亡了，不能推动游戏
    if player_proxy.over:
        return ExecuteResponse(
            user_name=request_data.user_name, error=3, message="player_proxy.over"
        ).model_dump()

    # 如果有输入命令，就要加
    for usr_input in request_data.user_input:
        assert usr_input != "/watch" and usr_input != "/w", "不应该有这个命令"
        assert usr_input != "/check" and usr_input != "/c", "不应该有这个命令"
        assert (
            usr_input != "/retrieve_actor_archives" and usr_input != "/raa"
        ), "不应该有这个命令"
        assert (
            usr_input != "/retrieve_stage_archives" and usr_input != "/rsa"
        ), "不应该有这个命令"

        rpg_game.rpg_game_helper.add_player_command(
            RoomManagerInstance._room._game, player_proxy, usr_input
        )

    if not RoomManagerInstance._room._game._will_exit:
        await RoomManagerInstance._room._game.a_execute()

    if player_proxy.over:
        RoomManagerInstance._room._game._will_exit = True

    # 返回执行游戏的信息
    return ExecuteResponse(
        user_name=request_data.user_name,
        game_name=request_data.game_name,
        actor_name=RoomManagerInstance._room.get_player_actor_name(),
        player_input_enable=rpg_game.rpg_game_helper.is_player_turn(
            RoomManagerInstance._room._game, player_proxy
        ),
        total=len(player_proxy.model.client_messages),
        game_round=RoomManagerInstance._room._game.current_round,
    ).model_dump()


###############################################################################################################################################
@game_process_api_router.post("/fetch_messages/")
async def fetch_messages(request_data: FetchMessagesRequest) -> Dict[str, Any]:

    if (
        RoomManagerInstance._room is None
        or RoomManagerInstance._room._game is None
        or request_data.index < 0
        or request_data.count <= 0
    ):
        return FetchMessagesResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=100,
            message=f"game_room._game is None, request_data.index = {request_data.index}, request_data.count = {request_data.count}",
        ).model_dump()

    # 没有客户端就不能看
    player_proxy = RoomManagerInstance._room.get_player()
    if player_proxy is None:
        return FetchMessagesResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            actor_name=request_data.actor_name,
            error=1,
            message="player_proxy is None",
        ).model_dump()

    #
    fetch_messages = player_proxy.fetch_client_messages(
        request_data.index, request_data.count
    )

    # 临时输出一下。
    logger.warning(
        f"fetch_messages, player = {player_proxy.name}, count = {len(fetch_messages)}"
    )
    for fetch_message in fetch_messages:
        json_str = fetch_message.model_dump_json()
        logger.warning(json_str)

    return FetchMessagesResponse(
        user_name=request_data.user_name,
        game_name=request_data.game_name,
        actor_name=request_data.actor_name,
        messages=fetch_messages,
        total=len(player_proxy.model.client_messages),
        game_round=RoomManagerInstance._room._game.current_round,
    ).model_dump()


###############################################################################################################################################
@game_process_api_router.post("/exit/")
async def exit(request_data: ExitRequest) -> Dict[str, Any]:

    # 不能切换状态到游戏退出
    if (
        not RoomManagerInstance._state.can_transition(GameState.REQUESTING_EXIT)
        or RoomManagerInstance._room is None
        or RoomManagerInstance._room._game is None
    ):
        return ExitResponse(
            user_name=request_data.user_name, error=1, message=""
        ).model_dump()

    logger.info(f"exit: {request_data.user_name}")

    # 切换状态到游戏退出
    RoomManagerInstance._state.transition(GameState.REQUESTING_EXIT)

    # 当前的游戏杀掉
    RoomManagerInstance._room._game._will_exit = True
    rpg_game.rpg_game_helper.save_game(
        RoomManagerInstance._room._game, rpg_game_config.GAMES_ARCHIVE_DIR
    )
    RoomManagerInstance._room._game.exit()

    # 清空这2个变量
    RoomManagerInstance._room = None
    assert RoomManagerInstance._state.can_transition(GameState.UNLOGGED)
    RoomManagerInstance._state.transition(GameState.UNLOGGED)

    # 返回退出游戏的信息
    return ExitResponse(
        user_name=request_data.user_name, game_name=request_data.game_name
    ).model_dump()


###############################################################################################################################################
