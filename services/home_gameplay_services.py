from fastapi import APIRouter
from services.game_server_instance import GameServerInstance
from models.api_models import HomeRunRequest, HomeRunResponse
from loguru import logger
from game.web_tcg_game import WebTCGGame
from game.tcg_game import TCGGameState


###################################################################################################################################################################
home_gameplay_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_gameplay_router.post(path="/home/run/v1/", response_model=HomeRunResponse)
async def home_run(
    request_data: HomeRunRequest,
    game_server: GameServerInstance,
) -> HomeRunResponse:

    logger.info(f"home_run: {request_data.model_dump_json()}")

    # 是否有房间？！！
    room_manager = game_server.room_manager
    if not room_manager.has_room(request_data.user_name):
        logger.error(
            f"home_run: {request_data.user_name} has no room, please login first."
        )
        return HomeRunResponse(
            error=1001,
            message="没有登录，请先登录",
        )

    # 是否有游戏？！！
    current_room = room_manager.get_room(request_data.user_name)
    assert current_room is not None
    if current_room._game is None:
        logger.error(
            f"home_run: {request_data.user_name} has no game, please login first."
        )
        return HomeRunResponse(
            error=1002,
            message="没有游戏，请先登录",
        )

    # 判断游戏是否开始
    if not current_room._game.start:
        logger.error(
            f"home_run: {request_data.user_name} game not started, please start it first."
        )
        return HomeRunResponse(
            error=1003,
            message="游戏没有开始，请先开始游戏",
        )

    # 判断游戏状态，不是Home状态不可以推进。
    if current_room._game.current_game_state != TCGGameState.HOME:
        logger.error(
            f"home_run: {request_data.user_name} game state error = {current_room._game.current_game_state}"
        )
        return HomeRunResponse(
            error=1004,
            message=f"{request_data.user_input} 只能在营地中使用",
        )

    # 清空消息。准备重新开始
    current_room._game.player.clear_client_messages()

    # 测试推进一次游戏
    await _execute_web_game(current_room._game, request_data.user_input)

    return HomeRunResponse(
        client_messages=current_room._game.player.client_messages,
        error=0,
        message=request_data.model_dump_json(),
    )


################################################################################################################
################################################################################################################
################################################################################################################
async def _execute_web_game(web_game: WebTCGGame, usr_input: str) -> None:
    assert web_game.player.name != ""
    await web_game.a_execute()
