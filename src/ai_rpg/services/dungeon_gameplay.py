from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.tcg_game import TCGGame
from .game_server_depends import GameServerInstance
from ..models import (
    DungeonGamePlayRequest,
    DungeonGamePlayResponse,
    DungeonTransHomeRequest,
    DungeonTransHomeResponse,
)
from .dungeon_stage_transition import (
    advance_to_next_stage,
    complete_dungeon_and_return_home,
)
from .dungeon_actions import (
    activate_actor_card_draws,
    activate_random_play_cards,
)
from ..game.game_server import GameServer

###################################################################################################################################################################
dungeon_gameplay_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
def _validate_dungeon_prerequisites(
    user_name: str,
    game_server: GameServer,
) -> TCGGame:
    """
    验证地下城操作的所有前置条件
    
    执行一系列验证以确保玩家可以进行地下城操作：
    1. 验证玩家已登录（房间存在）
    2. 验证游戏实例存在
    3. 验证玩家当前在地下城状态
    4. 验证存在可进行的战斗

    Args:
        user_name: 用户名，用于标识玩家
        game_server: 游戏服务器实例

    Returns:
        TCGGame: 验证通过的游戏实例

    Raises:
        HTTPException(404): 玩家未登录、游戏不存在或没有战斗
        HTTPException(400): 玩家不在地下城状态
        AssertionError: 服务器内部状态异常
    """
    
    # 1. 验证房间存在（玩家已登录）
    if not game_server.has_room(user_name):
        logger.error(f"地下城操作失败: 玩家 {user_name} 未登录")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    # 2. 验证游戏实例存在
    current_room = game_server.get_room(user_name)
    assert current_room is not None, f"_validate_dungeon_prerequisites: room is None for {user_name}"
    
    if current_room._tcg_game is None:
        logger.error(f"地下城操作失败: 玩家 {user_name} 没有游戏实例")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="游戏实例不存在，请重新登录",
        )

    # 3. 获取并验证游戏实例类型
    tcg_game = current_room._tcg_game
    assert isinstance(tcg_game, TCGGame), f"_validate_dungeon_prerequisites: invalid game type for {user_name}"

    # 4. 验证玩家在地下城状态
    if not tcg_game.is_player_in_dungeon:
        logger.error(f"地下城操作失败: 玩家 {user_name} 不在地下城状态")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能在地下城状态下使用",
        )

    # 5. 验证存在可进行的战斗
    if len(tcg_game.current_combat_sequence.combats) == 0:
        logger.error(f"地下城操作失败: 玩家 {user_name} 没有可进行的战斗")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有战斗可以进行",
        )

    return tcg_game


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _handle_dungeon_combat_kick_off(
    web_game: TCGGame,
) -> DungeonGamePlayResponse:
    """处理地下城战斗开始"""
    if not web_game.current_combat_sequence.is_starting:
        logger.error(f"not web_game.current_engagement.is_kickoff_phase")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="not web_game.current_engagement.is_kickoff_phase",
        )

    # 推进一次游戏, 即可转换ONGOING状态。
    # web_game.player_session.session_messages.clear()
    await web_game.combat_pipeline.process()
    # 返回！
    return DungeonGamePlayResponse(client_messages=[])


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _handle_draw_cards(web_game: TCGGame) -> DungeonGamePlayResponse:
    """处理抽卡操作"""
    if not web_game.current_combat_sequence.is_ongoing:
        logger.error(f"not web_game.current_engagement.is_on_going_phase")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="not web_game.current_engagement.is_on_going_phase",
        )

    # 推进一次游戏, 即可抽牌。
    # web_game.draw_cards_action()
    activate_actor_card_draws(web_game)
    # web_game.player_session.session_messages.clear()
    await web_game.combat_pipeline.process()

    # 返回！
    return DungeonGamePlayResponse(
        client_messages=[],
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _handle_play_cards(
    web_game: TCGGame, request_data: DungeonGamePlayRequest
) -> DungeonGamePlayResponse:
    """处理出牌操作"""
    if not web_game.current_combat_sequence.is_ongoing:
        logger.error(f"not web_game.current_engagement.is_on_going_phase")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="not web_game.current_engagement.is_on_going_phase",
        )

    logger.debug(f"玩家输入 = {request_data.user_input.tag}, 准备行动......")
    # if web_game.play_cards_action():
    if activate_random_play_cards(web_game):
        # 执行一次！！！！！
        # web_game.player_session.session_messages.clear()
        await web_game.combat_pipeline.process()

    # 返回！
    return DungeonGamePlayResponse(
        client_messages=[],
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _handle_advance_next_dungeon(web_game: TCGGame) -> DungeonGamePlayResponse:
    """处理前进下一个地下城"""
    if not web_game.current_combat_sequence.is_waiting:
        logger.error(f"not web_game.current_engagement.is_post_wait_phase")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="not web_game.current_engagement.is_post_wait_phase",
        )

    if web_game.current_combat_sequence.hero_won:
        next_level = web_game.current_dungeon.peek_next_stage()
        if next_level is None:
            logger.info("没有下一关，你胜利了，应该返回营地！！！！")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="没有下一关，你胜利了，应该返回营地！！！！",
            )
        else:
            # web_game.next_dungeon()
            advance_to_next_stage(web_game)
            return DungeonGamePlayResponse(
                client_messages=[],
            )
    elif web_game.current_combat_sequence.hero_lost:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="你已经失败了，不能继续进行游戏",
        )

    # 如果既没有胜利也没有失败，这种情况应该不会发生，但为了安全起见
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="战斗状态异常",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_gameplay_api_router.post(
    path="/api/dungeon/gameplay/v1/", response_model=DungeonGamePlayResponse
)
async def dungeon_gameplay(
    payload: DungeonGamePlayRequest,
    game_server: GameServerInstance,
) -> DungeonGamePlayResponse:

    logger.info(f"/dungeon/gameplay/v1/: {payload.model_dump_json()}")
    try:
        # 验证地下城操作的前置条件
        web_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 处理逻辑
        match payload.user_input.tag:
            case "dungeon_combat_kick_off":
                return await _handle_dungeon_combat_kick_off(web_game)

            # case "dungeon_combat_complete":
            #     return await _handle_dungeon_combat_complete(web_game)

            case "draw_cards":
                return await _handle_draw_cards(web_game)

            case "play_cards":
                return await _handle_play_cards(web_game, payload)

            # case "x_card":
            #     return await _handle_x_card(web_game, payload)

            case "advance_next_dungeon":
                return await _handle_advance_next_dungeon(web_game)

            case _:
                logger.error(f"未知的请求类型 = {payload.user_input.tag}, 不能处理！")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"未知的请求类型 = {payload.user_input.tag}, 不能处理！",
                )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发生错误: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################


@dungeon_gameplay_api_router.post(
    path="/api/dungeon/trans_home/v1/", response_model=DungeonTransHomeResponse
)
async def dungeon_trans_home(
    payload: DungeonTransHomeRequest,
    game_server: GameServerInstance,
) -> DungeonTransHomeResponse:

    logger.info(f"/dungeon/trans_home/v1/: {payload.model_dump_json()}")
    try:
        # 验证地下城操作的前置条件
        web_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        if not web_game.current_combat_sequence.is_waiting:
            logger.error(f"not web_game.current_engagement.is_post_wait_phase:")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能在战斗结束后回家",
            )

        # 回家
        complete_dungeon_and_return_home(web_game)
        return DungeonTransHomeResponse(
            message="回家了",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发生错误: {str(e)}",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
