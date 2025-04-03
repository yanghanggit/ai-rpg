from fastapi import APIRouter
from services.game_server_instance import GameServerInstance
from models_v_0_0_1 import (
    DungeonRunRequest,
    DungeonRunResponse,
    DungeonDrawCardsRequest,
    DungeonDrawCardsResponse,
)
from loguru import logger
from game.web_tcg_game import WebTCGGame
from game.tcg_game import TCGGameState
from tcg_game_systems.draw_cards_utils import DrawCardsUtils

###################################################################################################################################################################
dungeon_gameplay_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _execute_web_game(web_game: WebTCGGame, usr_input: str) -> None:
    assert web_game.player.name != ""
    await web_game.a_execute()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_gameplay_router.post(
    path="/dungeon/run/v1/", response_model=DungeonRunResponse
)
async def dungeon_run(
    request_data: DungeonRunRequest,
    game_server: GameServerInstance,
) -> DungeonRunResponse:

    logger.info(f"/dungeon/run/v1/: {request_data.model_dump_json()}")

    # 是否有房间？！！
    room_manager = game_server.room_manager
    if not room_manager.has_room(request_data.user_name):
        logger.error(
            f"dungeon_run: {request_data.user_name} has no room, please login first."
        )
        return DungeonRunResponse(
            error=1001,
            message="没有登录，请先登录",
        )

    # 是否有游戏？！！
    current_room = room_manager.get_room(request_data.user_name)
    assert current_room is not None
    if current_room._game is None:
        logger.error(
            f"dungeon_run: {request_data.user_name} has no game, please login first."
        )
        return DungeonRunResponse(
            error=1002,
            message="没有游戏，请先登录",
        )

    # 判断游戏是否开始
    if not current_room._game.is_game_started:
        logger.error(
            f"dungeon_run: {request_data.user_name} game not started, please start it first."
        )
        return DungeonRunResponse(
            error=1003,
            message="游戏没有开始，请先开始游戏",
        )

    # 判断游戏状态，不是DUNGEON状态不可以推进。
    if current_room._game.current_game_state != TCGGameState.DUNGEON:
        logger.error(
            f"dungeon_run: {request_data.user_name} game state error = {current_room._game.current_game_state}"
        )
        return DungeonRunResponse(
            error=1004,
            message=f"{request_data.user_input} 只能在地下城状态下使用",
        )

    # 判断是否有战斗
    if len(current_room._game.current_engagement.combats) == 0:
        logger.error(f"没有战斗可以进行！！！！")
        return DungeonRunResponse(
            error=1005,
            message="没有战斗可以进行",
        )

    # 清空消息。准备重新开始
    current_room._game.player.clear_client_messages()
    # 测试推进一次游戏
    await _execute_web_game(current_room._game, request_data.user_input)
    # 返回！
    return DungeonRunResponse(
        client_messages=current_room._game.player.client_messages,
        error=0,
        message="",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_gameplay_router.post(
    path="/dungeon/draw_cards/v1/", response_model=DungeonDrawCardsResponse
)
async def dungeon_draw_cards(
    request_data: DungeonDrawCardsRequest,
    game_server: GameServerInstance,
) -> DungeonDrawCardsResponse:

    logger.info(f"/dungeon/draw_cards/v1/: {request_data.model_dump_json()}")

    room_manager = game_server.room_manager
    if not room_manager.has_room(request_data.user_name):
        logger.error(
            f"dungeon_draw_cards: {request_data.user_name} has no room, please login first."
        )
        return DungeonDrawCardsResponse(
            error=1001,
            message="没有登录，请先登录",
        )

    # 是否有游戏？！！
    current_room = room_manager.get_room(request_data.user_name)
    assert current_room is not None
    if current_room._game is None:
        logger.error(
            f"dungeon_draw_cards: {request_data.user_name} has no game, please login first."
        )
        return DungeonDrawCardsResponse(
            error=1002,
            message="没有游戏，请先登录",
        )

    # 判断游戏是否开始
    if not current_room._game.is_game_started:
        logger.error(
            f"dungeon_draw_cards: {request_data.user_name} game not started, please start it first."
        )
        return DungeonDrawCardsResponse(
            error=1003,
            message="游戏没有开始，请先开始游戏",
        )

    # 判断游戏状态，不是DUNGEON状态不可以推进。
    if current_room._game.current_game_state != TCGGameState.DUNGEON:
        logger.error(
            f"dungeon_draw_cards: {request_data.user_name} game state error = {current_room._game.current_game_state}"
        )
        return DungeonDrawCardsResponse(
            error=1004,
            message=f"{request_data.user_input} 只能在地下城状态下使用",
        )

    if not current_room._game.current_engagement.is_on_going_phase:
        logger.error(f"战斗不是进行中状态！！！！")
        return DungeonDrawCardsResponse(
            error=1005,
            message="没有战斗可以进行",
        )

    player_stage_entity = current_room._game.get_player_entity()
    assert player_stage_entity is not None

    current_room._game.player.clear_client_messages()
    draw_card_utils = DrawCardsUtils(
        current_room._game,
        current_room._game.retrieve_actors_on_stage(player_stage_entity),
    )
    await draw_card_utils.draw_cards()

    return DungeonDrawCardsResponse(
        client_messages=current_room._game.player.client_messages,
        error=0,
        message="",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
