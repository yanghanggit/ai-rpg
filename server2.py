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
)
from typing import Dict, Any, Optional
import rpg_game.rpg_game_helper
from rpg_game.web_game import WebGame
from player.player_proxy import PlayerProxy

app = FastAPI()

server_state = GameStateWrapper(GameState.LOGOUT)


class SinglePlayerGameRoom:

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
        return player._ctrl_actor_name


game_room: Optional[SinglePlayerGameRoom] = None


###############################################################################################################################################
@app.post("/login/")
async def login(data: LoginData) -> Dict[str, Any]:
    global game_room
    assert game_room is None, "game_room is not None"

    if not server_state.can_transition(GameState.LOGIN):
        return LoginData(user_name=data.user_name, response=False).model_dump()

    logger.info(f"login: {data.user_name}")
    server_state.transition(GameState.LOGIN)

    game_room = SinglePlayerGameRoom(data.user_name)

    return LoginData(user_name=data.user_name, response=True).model_dump()


###############################################################################################################################################


@app.post("/create/")
async def create(data: CreateData) -> Dict[str, Any]:
    global game_room
    assert game_room is not None, "game_room is None"
    assert game_room._game is None, "game_room._game is not None"

    if not server_state.can_transition(GameState.CREATE):
        return CreateData(
            user_name=data.user_name, game_name=data.game_name, response=False
        ).model_dump()

    new_game = rpg_game.rpg_game_helper.create_web_rpg_game(data.game_name, "qwe")
    if new_game is None:
        logger.error(f"create_rpg_game 失败 = {data.game_name}")
        return CreateData(
            user_name=data.user_name, game_name=data.game_name, response=False
        ).model_dump()

    logger.info(f"create: {data.user_name}, {data.game_name}")
    server_state.transition(GameState.CREATE)

    game_room._game = new_game
    actor_names = new_game.get_player_controlled_actors()

    return CreateData(
        user_name=data.user_name,
        game_name=data.game_name,
        selectable_actor_names=actor_names,
        response=True,
    ).model_dump()


###############################################################################################################################################
@app.post("/join/")
async def join(data: JoinData) -> Dict[str, Any]:

    global game_room
    assert game_room is not None, "game_room is None"
    assert game_room._game is not None, "game_room._game is None"

    if not server_state.can_transition(GameState.JOIN):
        return JoinData(user_name=data.user_name, response=False).model_dump()

    logger.info(f"join: {data.user_name}, {data.game_name}, {data.ctrl_actor_name}")
    server_state.transition(GameState.JOIN)

    if data.ctrl_actor_name != "":

        player_proxy = PlayerProxy(data.user_name)
        game_room._game.add_player(player_proxy)

        rpg_game.rpg_game_helper.player_join(
            game_room._game, player_proxy, data.ctrl_actor_name
        )
    else:
        logger.info(
            "没有找到可以控制的角色，可能是game resource里没设置Player，此时就是观看。"
        )

    return JoinData(
        user_name=data.user_name,
        game_name=data.game_name,
        ctrl_actor_name=data.ctrl_actor_name,
        response=True,
    ).model_dump()


###############################################################################################################################################
@app.post("/start/")
async def start(data: StartData) -> Dict[str, Any]:

    global game_room
    assert game_room is not None, "game_room is None"
    assert game_room._game is not None, "game_room._game is None"

    if not server_state.can_transition(GameState.START):
        return StartData(user_name=data.user_name, response=False).model_dump()

    logger.info(f"start: {data.user_name}, {data.game_name}, {data.ctrl_actor_name}")
    server_state.transition(GameState.START)

    return StartData(
        user_name=data.user_name,
        game_name=data.game_name,
        ctrl_actor_name=data.ctrl_actor_name,
        response=True,
    ).model_dump()


###############################################################################################################################################
@app.post("/exit/")
async def exit(data: ExitData) -> Dict[str, Any]:

    global game_room
    assert game_room is not None, "game_room is None"
    assert game_room._game is not None, "game_room._game is None"

    if not server_state.can_transition(GameState.EXIT):
        return ExitData(user_name=data.user_name, response=False).model_dump()

    logger.info(f"exit: {data.user_name}")
    server_state.transition(GameState.EXIT)

    # 直接杀掉游戏
    game_room._game = None

    return ExitData(
        user_name=data.user_name, game_name=data.game_name, response=True
    ).model_dump()


###############################################################################################################################################

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=WS_CONFIG.Host.value, port=WS_CONFIG.Port.value)
