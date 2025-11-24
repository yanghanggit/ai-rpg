from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.tcg_game import TCGGame
from .game_server_depends import GameServerInstance
from ..game.game_server import GameServer
from .home_actions import activate_speak_action, activate_stage_transition
from .dungeon_stage_transition import (
    initialize_dungeon_first_entry,
)
from ..models import (
    HomeGamePlayRequest,
    HomeGamePlayResponse,
    HomeTransDungeonRequest,
    HomeTransDungeonResponse,
)

###################################################################################################################################################################
home_gameplay_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _validate_player_at_home(
    user_name: str,
    game_server: GameServer,
) -> TCGGame:
    """
    验证玩家是否在家园状态，包括房间存在性、TCG游戏实例和玩家当前位置检查

    Args:
        user_name: 用户名
        game_server: 游戏服务器实例

    Returns:
        TCGGame: 验证通过的 TCG 游戏实例

    Raises:
        HTTPException(404): 房间不存在或游戏实例不存在
        HTTPException(400): 玩家当前不在家园状态
        AssertionError: 房间实例状态异常
    """

    # 检查房间是否存在
    if not game_server.has_room(user_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    # 获取房间实例并检查游戏是否存在
    current_room = game_server.get_room(user_name)
    assert current_room is not None, "_validate_player_at_home: room instance is None"
    if current_room._tcg_game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有游戏，请先登录",
        )

    # 判断游戏状态，不是Home状态不可以推进。
    if not current_room._tcg_game.is_player_at_home:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前不在家园状态，不能进行家园操作",
        )

    # 返回游戏实例
    return current_room._tcg_game


###################################################################################################################################################################
###################################################################################################################################################################


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_gameplay_api_router.post(
    path="/api/home/gameplay/v1/", response_model=HomeGamePlayResponse
)
async def home_gameplay(
    payload: HomeGamePlayRequest,
    game_server: GameServerInstance,
) -> HomeGamePlayResponse:

    logger.info(f"/home/gameplay/v1/: {payload.model_dump_json()}")
    try:
        # 验证前置条件并获取游戏实例
        web_game = await _validate_player_at_home(
            payload.user_name,
            game_server,
        )

        # 根据标记处理。
        match payload.user_input.tag:

            case "/advancing":
                # 推进一次游戏
                await web_game.npc_home_pipeline.process()
                return HomeGamePlayResponse(client_messages=[])

            case "/speak":
                # 激活说话动作
                if activate_speak_action(
                    web_game,
                    target=payload.user_input.data.get("target", ""),
                    content=payload.user_input.data.get("content", ""),
                ):
                    await web_game.player_home_pipeline.process()
                return HomeGamePlayResponse(client_messages=[])

            case "/trans_home":
                # 激活场景转换动作
                if activate_stage_transition(
                    web_game, stage_name=payload.user_input.data.get("stage_name", "")
                ):
                    await web_game.player_home_pipeline.process()
                return HomeGamePlayResponse(client_messages=[])

            case _:
                logger.error(f"未知的请求类型 = {payload.user_input.tag}, 不能处理！")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"未知的请求类型 = {payload.user_input.tag}, 不能处理！",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"home/gameplay/v1: {payload.user_name} failed, error: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@home_gameplay_api_router.post(
    path="/api/home/trans_dungeon/v1/", response_model=HomeTransDungeonResponse
)
async def home_trans_dungeon(
    payload: HomeTransDungeonRequest,
    game_server: GameServerInstance,
) -> HomeTransDungeonResponse:

    logger.info(f"/home/trans_dungeon/v1/: {payload.model_dump_json()}")
    try:
        # 验证前置条件并获取游戏实例
        web_game = await _validate_player_at_home(
            payload.user_name,
            game_server,
        )

        # 判断地下城是否存在
        if len(web_game.current_dungeon.stages) == 0:
            logger.warning(
                "没有地下城可以传送, 全部地下城已经结束。！！！！已经全部被清空！！！！或者不存在！！！！"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="没有地下城可以传送, 全部地下城已经结束。！！！！已经全部被清空！！！！或者不存在！！！！",
            )

        # 传送地下城执行。
        # if not web_game.launch_dungeon():
        if not initialize_dungeon_first_entry(web_game):
            logger.error("第一次地下城传送失败!!!!")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="第一次地下城传送失败!!!!",
            )
        #
        return HomeTransDungeonResponse(
            message=payload.model_dump_json(),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"home/trans_dungeon/v1: {payload.user_name} failed, error: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
