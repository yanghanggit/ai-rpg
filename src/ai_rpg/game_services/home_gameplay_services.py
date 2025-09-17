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
async def _validate_home_game_preconditions(
    user_name: str,
    game_server: GameServerInstance,
) -> WebTCGGame:
    """
    验证家园操作的前置条件，包括房间检查、游戏检查和游戏状态检查

    Args:
        user_name: 用户名
        game_server: 游戏服务器实例

    Returns:
        WebTCGGame: 验证通过的游戏实例

    Raises:
        HTTPException: 当验证失败时抛出相应的HTTP异常
    """
    # 是否有房间？！！
    room_manager = game_server.room_manager
    if not room_manager.has_room(user_name):
        logger.error(f"{user_name} has no room, please login first.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    # 是否有游戏？！！
    current_room = room_manager.get_room(user_name)
    assert current_room is not None
    if current_room.game is None:
        logger.error(f"{user_name} has no game, please login first.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有游戏，请先登录",
        )

    web_game = current_room.game
    assert web_game is not None
    assert isinstance(web_game, WebTCGGame)

    # 判断游戏状态，不是Home状态不可以推进。
    if web_game.current_game_state != TCGGameState.HOME:
        logger.error(f"{user_name} game state error = {web_game.current_game_state}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能在营地中使用",
        )

    return web_game


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
# async def _execute_web_game(web_game: WebTCGGame) -> None:
#     assert web_game.player.name != ""
#     web_game.player.clear_messages()
#     await web_game.run()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _handle_advancing_action(web_game: WebTCGGame) -> HomeGamePlayResponse:
    """
    处理推进游戏的动作

    Args:
        web_game: 游戏实例

    Returns:
        HomeGamePlayResponse: 包含客户端消息的响应
    """
    # 推进一次。
    web_game.player.clear_messages()
    await web_game.home_state_pipeline.process()

    # 返回消息
    return HomeGamePlayResponse(
        client_messages=web_game.player.client_messages,
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _handle_speak_action(
    web_game: WebTCGGame, target: str, content: str
) -> HomeGamePlayResponse:
    """
    处理说话动作

    Args:
        web_game: 游戏实例
        target: 说话目标
        content: 说话内容

    Returns:
        HomeGamePlayResponse: 包含客户端消息的响应
    """
    # player 添加说话的动作
    if web_game.activate_speak_action(target=target, content=content):
        # 清空消息。准备重新开始 + 测试推进一次游戏
        web_game.player.clear_messages()
        await web_game.player_home_state_pipeline.process()

        # 返回消息
        return HomeGamePlayResponse(
            client_messages=web_game.player.client_messages,
        )

    # 如果说话动作激活失败，返回空消息
    return HomeGamePlayResponse(
        client_messages=web_game.player.client_messages,
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_gameplay_router.post(
    path="/api/home/gameplay/v1/", response_model=HomeGamePlayResponse
)
async def home_gameplay(
    request_data: HomeGamePlayRequest,
    game_server: GameServerInstance,
) -> HomeGamePlayResponse:

    logger.info(f"/home/gameplay/v1/: {request_data.model_dump_json()}")
    try:
        # 验证前置条件并获取游戏实例
        web_game = await _validate_home_game_preconditions(
            request_data.user_name,
            game_server,
        )

        # 根据标记处理。
        match request_data.user_input.tag:

            case "/advancing":
                return await _handle_advancing_action(web_game)

            case "/speak":
                return await _handle_speak_action(
                    web_game,
                    target=request_data.user_input.data.get("target", ""),
                    content=request_data.user_input.data.get("content", ""),
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
    path="/api/home/trans_dungeon/v1/", response_model=HomeTransDungeonResponse
)
async def home_trans_dungeon(
    request_data: HomeTransDungeonRequest,
    game_server: GameServerInstance,
) -> HomeTransDungeonResponse:

    logger.info(f"/home/trans_dungeon/v1/: {request_data.model_dump_json()}")
    try:
        # 验证前置条件并获取游戏实例
        web_game = await _validate_home_game_preconditions(
            request_data.user_name,
            game_server,
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
