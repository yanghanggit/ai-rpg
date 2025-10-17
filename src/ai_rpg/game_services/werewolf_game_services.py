from fastapi import APIRouter
from fastapi import APIRouter
from loguru import logger
from ..game_services.game_server import GameServerInstance
from ..models import (
    WerewolfGameStartRequest,
    WerewolfGameStartResponse,
    WerewolfGamePlayRequest,
    WerewolfGamePlayResponse,
    WerewolfGameStateResponse,
)

###################################################################################################################################################################
werewolf_game_api_router = APIRouter()
###################################################################################################################################################################


###################################################################################################################################################################
@werewolf_game_api_router.post(
    path="/api/werewolf/start/v1/", response_model=WerewolfGameStartResponse
)
async def start_werewolf_game(
    request_data: WerewolfGameStartRequest,
    game_server: GameServerInstance,
) -> WerewolfGameStartResponse:
    logger.info(f"Starting werewolf game: {request_data.model_dump_json()}")
    # 在这里添加启动游戏的逻辑
    return WerewolfGameStartResponse(message="Werewolf game started successfully.")


###################################################################################################################################################################


werewolf_game_api_router.post(
    path="/api/werewolf/gameplay/v1/", response_model=WerewolfGamePlayResponse
)


async def play_werewolf_game(
    request_data: WerewolfGamePlayRequest,
    game_server: GameServerInstance,
) -> WerewolfGamePlayResponse:
    logger.info(f"Playing werewolf game: {request_data.model_dump_json()}")
    # 在这里添加游戏玩法的逻辑
    return WerewolfGamePlayResponse(client_messages=[])


###################################################################################################################################################################


@werewolf_game_api_router.get(
    path="/api/werewolf/state/v1/{user_name}/{game_name}/state",
    response_model=WerewolfGameStateResponse,
)
async def get_werewolf_game_state(
    game_server: GameServerInstance,
    user_name: str,
    game_name: str,
) -> WerewolfGameStateResponse:
    logger.info(f"Getting werewolf game state for user: {user_name}, game: {game_name}")
    # 在这里添加获取游戏状态的逻辑
    return WerewolfGameStateResponse(
        message="Werewolf game state retrieved successfully."
    )


###################################################################################################################################################################
