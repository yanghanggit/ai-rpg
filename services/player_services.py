from fastapi import APIRouter
from services.game_server_instance import GameServerInstance
from models.api_models import PlayerRequest, PlayerResponse
from loguru import logger
from player.player_command import PlayerCommand
from game.web_tcg_game import WebTCGGame
from game.tcg_game import TCGGameState


###################################################################################################################################################################
player_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@player_router.post(path="/player/v1/", response_model=PlayerResponse)
async def player(
    request_data: PlayerRequest,
    game_server: GameServerInstance,
) -> PlayerResponse:

    logger.debug(f"login: {request_data.model_dump_json()}")

    if request_data.user_input != "run-home":
        logger.error(
            f"login: {request_data.user_name} input error = {request_data.user_input}"
        )
        return PlayerResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            error=1000,
            message="目前只测试 run-home",
        )

    # 是否有房间？！！
    room_manager = game_server.room_manager
    if not room_manager.has_room(request_data.user_name):
        logger.error(
            f"login: {request_data.user_name} has no room, please login first."
        )
        return PlayerResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            error=1001,
            message="没有登录，请先登录",
        )

    # 是否有游戏？！！
    current_room = room_manager.get_room(request_data.user_name)
    assert current_room is not None
    if current_room._game is None:
        logger.error(
            f"login: {request_data.user_name} has no game, please login first."
        )
        return PlayerResponse(
            user_name=request_data.user_name,
            game_name=request_data.game_name,
            error=1002,
            message="没有游戏，请先登录",
        )

    # 测试推进一次游戏
    if current_room._game.current_game_state == TCGGameState.HOME:
        await _execute_web_game(current_room._game, request_data.user_input) # 执行一次！！！！！
    else:
        logger.error(f"{request_data.user_input} 只能在营地中使用")

    return PlayerResponse(
        user_name=request_data.user_name,
        game_name=request_data.game_name,
        error=0,
        message=request_data.model_dump_json(),
    )


################################################################################################################
################################################################################################################
################################################################################################################
async def _execute_web_game(web_game: WebTCGGame, usr_input: str) -> None:

    assert web_game.player.name != ""
    logger.debug(f"玩家输入: {web_game.player.name} = {usr_input}")

    # 执行一次！！！！！
    web_game.player.add_command(
        PlayerCommand(user=web_game.player.name, command=usr_input)
    )
    await web_game.a_execute()
