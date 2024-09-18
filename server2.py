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
from typing import Dict, Any

app = FastAPI()

server_state = GameStateWrapper(GameState.LOGOUT)


###############################################################################################################################################
@app.post("/login/")
async def login(data: LoginData) -> Dict[str, Any]:

    if not server_state.can_transition(GameState.LOGIN):
        return LoginData(username=data.username, response=False).model_dump()

    logger.info(f"login: {data.username}")
    server_state.transition(GameState.LOGIN)
    return LoginData(username=data.username, response=True).model_dump()


###############################################################################################################################################


@app.post("/create/")
async def create(data: CreateData) -> Dict[str, Any]:

    if not server_state.can_transition(GameState.CREATE):
        return CreateData(username=data.username, response=False).model_dump()

    logger.info(f"create: {data.username}, {data.game_name}")
    server_state.transition(GameState.CREATE)
    return CreateData(
        username=data.username, game_name=data.game_name, response=True
    ).model_dump()


###############################################################################################################################################
@app.post("/join/")
async def join(data: JoinData) -> Dict[str, Any]:

    if not server_state.can_transition(GameState.JOIN):
        return JoinData(username=data.username, response=False).model_dump()

    logger.info(f"join: {data.username}, {data.game_name}, {data.actor_name}")
    server_state.transition(GameState.JOIN)
    return JoinData(
        username=data.username,
        game_name=data.game_name,
        actor_name=data.actor_name,
        response=True,
    ).model_dump()


###############################################################################################################################################
@app.post("/start/")
async def start(data: StartData) -> Dict[str, Any]:

    if not server_state.can_transition(GameState.START):
        return StartData(username=data.username, response=False).model_dump()

    logger.info(f"start: {data.username}, {data.game_name}")
    server_state.transition(GameState.START)
    return StartData(
        username=data.username, game_name=data.game_name, response=True
    ).model_dump()


###############################################################################################################################################
@app.post("/exit/")
async def exit(data: ExitData) -> Dict[str, Any]:

    if not server_state.can_transition(GameState.EXIT):
        return ExitData(username=data.username, response=False).model_dump()

    logger.info(f"exit: {data.username}")
    server_state.transition(GameState.EXIT)
    return ExitData(
        username=data.username, game_name=data.game_name, response=True
    ).model_dump()


###############################################################################################################################################

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=WS_CONFIG.Host.value, port=WS_CONFIG.Port.value)
