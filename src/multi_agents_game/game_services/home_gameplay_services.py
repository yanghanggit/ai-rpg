from fastapi import APIRouter, HTTPException, status
from loguru import logger

from ..game.tcg_game import TCGGameState
from ..game.web_tcg_game import WebTCGGame
from ..game_services.game_server import GameServerInstance
from ..models import (
    HomeGamePlayRequest,
    HomeGamePlayResponse,
    HomeTransDungeonRequest,
    HomeTransDungeonResponse,
)

###################################################################################################################################################################
home_gameplay_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _execute_web_game(web_game: WebTCGGame) -> None:
    assert web_game.player.name != ""
    web_game.player.archive_and_clear_messages()
    await web_game.run()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_gameplay_router.post(
    path="/home/gameplay/v1/", response_model=HomeGamePlayResponse
)
async def home_gameplay(
    request_data: HomeGamePlayRequest,
    game_server: GameServerInstance,
) -> HomeGamePlayResponse:

    logger.info(f"/home/gameplay/v1/: {request_data.model_dump_json()}")
    try:
        # 是否有房间？！！
        room_manager = game_server.room_manager
        if not room_manager.has_room(request_data.user_name):
            logger.error(
                f"home/gameplay/v1: {request_data.user_name} has no room, please login first."
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"home/gameplay/v1: {request_data.user_name} has no room, please login first.",
            )

        # 是否有游戏？！！
        current_room = room_manager.get_room(request_data.user_name)
        assert current_room is not None
        if current_room.game is None:
            logger.error(
                f"home/gameplay/v1: {request_data.user_name} has no game, please login first."
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"home/gameplay/v1: {request_data.user_name} has no game, please login first.",
            )

        web_game = current_room.game
        assert web_game is not None
        assert isinstance(web_game, WebTCGGame)

        # 判断游戏状态，不是Home状态不可以推进。
        if web_game.current_game_state != TCGGameState.HOME:
            logger.error(
                f"home/gameplay/v1: {request_data.user_name} game state error = {web_game.current_game_state}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"home/gameplay/v1: {request_data.user_name} game state error = {web_game.current_game_state}, 只能在营地中使用",
            )

        # 根据标记处理。
        match request_data.user_input.tag:

            case "/advancing":
                # 推进一次。
                await _execute_web_game(web_game)

                # 返回消息
                return HomeGamePlayResponse(
                    client_messages=web_game.player.client_messages,
                )

            case "/speak":

                # player 添加说话的动作
                if web_game.activate_speak_action(
                    target=request_data.user_input.data.get("target", ""),
                    content=request_data.user_input.data.get("content", ""),
                ):

                    # 清空消息。准备重新开始 + 测试推进一次游戏
                    await _execute_web_game(web_game)

                    # 返回消息
                    return HomeGamePlayResponse(
                        client_messages=web_game.player.client_messages,
                    )

            case _:
                logger.error(
                    f"未知的请求类型 = {request_data.user_input.tag}, 不能处理！"
                )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"未知的请求类型 = {request_data.user_input.tag}, 不能处理！",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"home/gameplay/v1: {request_data.user_name} failed, error: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_gameplay_router.post(
    path="/home/trans_dungeon/v1/", response_model=HomeTransDungeonResponse
)
async def home_trans_dungeon(
    request_data: HomeTransDungeonRequest,
    game_server: GameServerInstance,
) -> HomeTransDungeonResponse:

    logger.info(f"/home/trans_dungeon/v1/: {request_data.model_dump_json()}")
    try:
        # 是否有房间？！！
        room_manager = game_server.room_manager
        if not room_manager.has_room(request_data.user_name):
            logger.error(
                f"home_trans_dungeon: {request_data.user_name} has no room, please login first."
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有登录，请先登录",
            )

        # 是否有游戏？！！
        current_room = room_manager.get_room(request_data.user_name)
        assert current_room is not None
        if current_room.game is None:
            logger.error(
                f"home_trans_dungeon: {request_data.user_name} has no game, please login first."
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有游戏，请先登录",
            )

        web_game = current_room.game
        assert web_game is not None
        assert isinstance(web_game, WebTCGGame)

        # 判断游戏状态，不是Home状态不可以推进。
        if web_game.current_game_state != TCGGameState.HOME:
            logger.error(
                f"home_trans_dungeon: {request_data.user_name} game state error = {web_game.current_game_state}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="trans_dungeon只能在营地中使用",
            )

        # 判断地下城是否存在
        if len(web_game.current_dungeon.levels) == 0:
            logger.warning(
                "没有地下城可以传送, 全部地下城已经结束。！！！！已经全部被清空！！！！或者不存在！！！！"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有地下城可以传送, 全部地下城已经结束。！！！！已经全部被清空！！！！或者不存在！！！！",
            )

        # 传送地下城执行。
        if not web_game.launch_dungeon():
            logger.error("第一次地下城传送失败!!!!")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="第一次地下城传送失败!!!!",
            )
        #
        return HomeTransDungeonResponse(
            message=request_data.model_dump_json(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"home/trans_dungeon/v1: {request_data.user_name} failed, error: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
