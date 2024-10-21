from fastapi import FastAPI
from loguru import logger
from ws_config import (
    WS_CONFIG,
    GameState,
    GameStateWrapper,
    LoginData,
    CreateData,
    JoinData,
    StartData,
    ExitData,
    ExecuteData,
    WatchData,
    CheckData,
)
from typing import Dict, Any, Optional, List
import rpg_game.rpg_game_helper
from rpg_game.web_game import WebGame
from player.player_proxy import PlayerProxy, PlayerProxyModel
from rpg_game.rpg_game_config import RPGGameConfig
from pathlib import Path
import shutil

fastapi_app = FastAPI()

server_state = GameStateWrapper(GameState.UNLOGGED)


class GameRoom:

    def __init__(self, user_name: str) -> None:
        self._user_name = user_name
        self._game: Optional[WebGame] = None

    def get_player(self) -> Optional[PlayerProxy]:
        if self._game is None:
            return None
        return self._game.get_player(self._user_name)

    def get_player_ctrl_actor_name(self) -> str:
        player = self.get_player()
        if player is None:
            return ""
        return player.ctrl_actor_name


game_room: Optional[GameRoom] = None


###############################################################################################################################################
@fastapi_app.post("/login/")
async def login(data: LoginData) -> Dict[str, Any]:

    global game_room
    assert game_room is None, "game_room is not None"

    if not server_state.can_transition(GameState.LOGGED_IN):
        return LoginData(user_name=data.user_name, response=False).model_dump()

    logger.info(f"login: {data.user_name}")

    # 切换状态到登陆完成并创建一个房间
    server_state.transition(GameState.LOGGED_IN)
    game_room = GameRoom(data.user_name)

    return LoginData(user_name=data.user_name, response=True).model_dump()


###############################################################################################################################################


@fastapi_app.post("/create/")
async def create(data: CreateData) -> Dict[str, Any]:

    global game_room
    assert game_room is not None, "game_room is None"
    assert game_room._game is None, "game_room._game is not None"

    if not server_state.can_transition(GameState.GAME_CREATED):
        return CreateData(
            user_name=data.user_name, game_name=data.game_name, response=False
        ).model_dump()

    # app 运行时路径
    game_runtime_dir = Path(f"{RPGGameConfig.GAME_SAMPLE_RUNTIME_DIR}/{data.game_name}")
    if game_runtime_dir.exists():
        # todo
        logger.warning(f"删除文件夹：{game_runtime_dir}, 这是为了测试，后续得改！！！")
        shutil.rmtree(game_runtime_dir)

    game_runtime_dir.mkdir(parents=True, exist_ok=True)
    assert game_runtime_dir.exists()

    # 游戏启动资源路径
    game_resource_file_path = (
        Path(f"{RPGGameConfig.GAME_SAMPLE_RUNTIME_DIR}") / f"{data.game_name}.json"
    )

    if not game_resource_file_path.exists():
        return CreateData(
            user_name=data.user_name, game_name=data.game_name, response=False
        ).model_dump()

    # 创建游戏资源
    game_resource = rpg_game.rpg_game_helper.create_game_resource(
        game_resource_file_path,
        game_runtime_dir,
        RPGGameConfig.CHECK_GAME_RESOURCE_VERSION,
    )
    if game_resource is None:
        return CreateData(
            user_name=data.user_name, game_name=data.game_name, response=False
        ).model_dump()

    # 游戏资源可以被创建，则将game_resource_file_path这个文件拷贝一份到root_runtime_dir下
    shutil.copy(
        game_resource_file_path, game_runtime_dir / game_resource_file_path.name
    )

    # 创建游戏
    new_game = rpg_game.rpg_game_helper.create_web_rpg_game(game_resource)
    if new_game is None or new_game._game_resource is None:
        logger.error(f"create_rpg_game 失败 = {data.game_name}")
        return CreateData(
            user_name=data.user_name, game_name=data.game_name, response=False
        ).model_dump()

    # 检查是否有可以控制的角色, 没有就不让玩。
    ctrl_actors = rpg_game.rpg_game_helper.get_player_ctrl_actor_names(new_game)
    if len(ctrl_actors) == 0:
        logger.warning(f"create_rpg_game 没有可以控制的角色 = {data.game_name}")
        return CreateData(
            user_name=data.user_name, game_name=data.game_name, response=False
        ).model_dump()

    logger.info(f"create: {data.user_name}, {data.game_name}")

    # 切换状态到游戏创建完成
    server_state.transition(GameState.GAME_CREATED)
    game_room._game = new_game
    assert new_game._game_resource is not None, "new_game._game_resource is None"

    return CreateData(
        user_name=data.user_name,
        game_name=data.game_name,
        selectable_actor_names=ctrl_actors,
        response=True,
        game_model=new_game._game_resource._model,
    ).model_dump()


###############################################################################################################################################
@fastapi_app.post("/join/")
async def join(data: JoinData) -> Dict[str, Any]:

    global game_room
    assert game_room is not None, "game_room is None"
    assert game_room._game is not None, "game_room._game is None"

    if not server_state.can_transition(GameState.GAME_JOINED):
        return JoinData(user_name=data.user_name, response=False).model_dump()

    if data.ctrl_actor_name == "":
        return JoinData(user_name=data.user_name, response=False).model_dump()

    logger.info(f"join: {data.user_name}, {data.game_name}, {data.ctrl_actor_name}")

    # 切换状态到游戏加入完成
    server_state.transition(GameState.GAME_JOINED)
    player_proxy = PlayerProxy(PlayerProxyModel(name=data.user_name))
    game_room._game.add_player(player_proxy)

    # 加入游戏
    rpg_game.rpg_game_helper.player_play_new_game(
        game_room._game, player_proxy, data.ctrl_actor_name
    )

    return JoinData(
        user_name=data.user_name,
        game_name=data.game_name,
        ctrl_actor_name=data.ctrl_actor_name,
        response=True,
    ).model_dump()


###############################################################################################################################################
@fastapi_app.post("/start/")
async def start(data: StartData) -> Dict[str, Any]:

    global game_room
    assert game_room is not None, "game_room is None"
    assert game_room._game is not None, "game_room._game is None"

    if not server_state.can_transition(GameState.PLAYING):
        return StartData(user_name=data.user_name, response=False).model_dump()

    logger.info(f"start: {data.user_name}, {data.game_name}, {data.ctrl_actor_name}")

    # 切换状态到游戏开始
    server_state.transition(GameState.PLAYING)

    return StartData(
        user_name=data.user_name,
        game_name=data.game_name,
        ctrl_actor_name=data.ctrl_actor_name,
        response=True,
    ).model_dump()


###############################################################################################################################################
@fastapi_app.post("/exit/")
async def exit(data: ExitData) -> Dict[str, Any]:

    global game_room
    assert game_room is not None, "game_room is None"
    assert game_room._game is not None, "game_room._game is None"

    if not server_state.can_transition(GameState.REQUESTING_EXIT):
        return ExitData(user_name=data.user_name, response=False).model_dump()

    logger.info(f"exit: {data.user_name}")

    # 切换状态到游戏退出
    server_state.transition(GameState.REQUESTING_EXIT)
    # 当前的游戏杀掉
    assert game_room._game is not None, "game_room._game is None"
    if game_room._game is not None:
        game_room._game._will_exit = True
        rpg_game.rpg_game_helper.save_game(
            game_room._game, RPGGameConfig.GAME_ARCHIVE_DIR
        )
        game_room._game.exit()
        game_room._game = None

    return ExitData(
        user_name=data.user_name, game_name=data.game_name, response=True
    ).model_dump()


###############################################################################################################################################
@fastapi_app.post("/execute/")
async def execute(data: ExecuteData) -> Dict[str, Any]:

    global game_room
    assert game_room is not None, "game_room is None"
    assert game_room._game is not None, "game_room._game is None"

    if game_room._game._will_exit:
        return ExecuteData(
            user_name=data.user_name, response=False, error="game_room._game._will_exit"
        ).model_dump()

    player_proxy = game_room.get_player()
    if player_proxy is None:
        return ExecuteData(
            user_name=data.user_name,
            response=False,
            error="game_room.get_player() is None",
        ).model_dump()

    if player_proxy.over:
        return ExecuteData(
            user_name=data.user_name, response=False, error="player_proxy._over"
        ).model_dump()

    # 如果有输入命令，就要加
    for usr_input in data.user_input:
        assert usr_input != "/watch" and usr_input != "/w", "不应该有这个命令"
        assert usr_input != "/check" and usr_input != "/c", "不应该有这个命令"
        rpg_game.rpg_game_helper.add_player_command(
            game_room._game, player_proxy, usr_input
        )

    # 运行一个回合
    send_client_messages: List[str] = []

    # 核心循环
    while True:

        if game_room._game._will_exit:
            break

        # 运行一个回合
        await game_room._game.a_execute()

        # 如果死了就退出。
        if player_proxy.over:
            game_room._game._will_exit = True
            break

        # 允许玩家输入的时候，才放松消息。
        if rpg_game.rpg_game_helper.is_player_turn(game_room._game, player_proxy):
            send_client_messages = player_proxy.send_client_messages(
                WS_CONFIG.SEND_MESSAGES_COUNT
            )
            break

    return ExecuteData(
        user_name=data.user_name,
        response=True,
        game_name=data.game_name,
        ctrl_actor_name=game_room.get_player_ctrl_actor_name(),
        messages=send_client_messages,
    ).model_dump()


###############################################################################################################################################
@fastapi_app.post("/watch/")
async def watch(data: WatchData) -> Dict[str, Any]:

    global game_room
    assert game_room is not None, "game_room is None"
    assert game_room._game is not None, "game_room._game is None"

    player_proxy = game_room.get_player()
    if player_proxy is None:
        return WatchData(
            user_name=data.user_name,
            game_name=data.game_name,
            ctrl_actor_name=data.ctrl_actor_name,
            response=False,
        ).model_dump()

    gen_message = rpg_game.rpg_game_helper.gen_player_watch_message(
        game_room._game, player_proxy
    )

    return WatchData(
        user_name=data.user_name,
        game_name=data.game_name,
        ctrl_actor_name=data.ctrl_actor_name,
        message=gen_message,
        response=True,
    ).model_dump()


###############################################################################################################################################
@fastapi_app.post("/check/")
async def check(data: CheckData) -> Dict[str, Any]:

    global game_room
    assert game_room is not None, "game_room is None"
    assert game_room._game is not None, "game_room._game is None"

    player_proxy = game_room.get_player()
    if player_proxy is None:
        return CheckData(
            user_name=data.user_name,
            game_name=data.game_name,
            ctrl_actor_name=data.ctrl_actor_name,
            response=False,
        ).model_dump()

    gen_message = rpg_game.rpg_game_helper.gen_player_check_message(
        game_room._game, player_proxy
    )

    return CheckData(
        user_name=data.user_name,
        game_name=data.game_name,
        ctrl_actor_name=data.ctrl_actor_name,
        message=gen_message,
        response=True,
    ).model_dump()


###############################################################################################################################################

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(fastapi_app, host=WS_CONFIG.LOCAL_HOST, port=WS_CONFIG.PORT)
