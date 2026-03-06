"""
地下城游戏玩法服务模块

提供地下城战斗的核心API接口，处理战斗流程、卡牌操作、关卡推进和返回家园等功能。
所有接口要求玩家已登录且位于地下城状态。
"""

import asyncio
from datetime import datetime
from typing import Final
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.tcg_game import TCGGame
from .game_server_dependencies import CurrentGameServer
from ..models import (
    DungeonProgressRequest,
    DungeonProgressResponse,
    DungeonProgressType,
    DungeonTransHomeRequest,
    DungeonTransHomeResponse,
    DungeonCombatDrawCardsRequest,
    DungeonCombatDrawCardsResponse,
    DungeonCombatPlayCardsRequest,
    DungeonCombatPlayCardsResponse,
    TaskStatus,
)
from .dungeon_stage_transition import (
    advance_to_next_stage,
    complete_dungeon_and_return_home,
)
from .dungeon_actions import (
    activate_random_enemy_card_draws,
    activate_specified_expedition_member_card_draws,
    activate_random_play_cards,
    retreat_from_dungeon_combat,
    ensure_all_actors_have_fallback_cards,
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
    验证地下城操作的前置条件

    验证玩家已登录、游戏实例存在、玩家在地下城状态且有可进行的战斗。

    Args:
        user_name: 用户名
        game_server: 游戏服务器实例

    Returns:
        TCGGame: 验证通过的游戏实例

    Raises:
        HTTPException(404): 玩家未登录、游戏不存在或没有战斗
        HTTPException(400): 玩家不在地下城状态
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
    assert (
        current_room is not None
    ), f"_validate_dungeon_prerequisites: room is None for {user_name}"

    if current_room._tcg_game is None:
        logger.error(f"地下城操作失败: 玩家 {user_name} 没有游戏实例")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="游戏实例不存在，请重新登录",
        )

    # 3. 获取并验证游戏实例类型
    tcg_game = current_room._tcg_game
    assert isinstance(
        tcg_game, TCGGame
    ), f"_validate_dungeon_prerequisites: invalid game type for {user_name}"

    # 4. 验证玩家在地下城状态
    if not tcg_game.is_player_in_dungeon_stage:
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
@dungeon_gameplay_api_router.post(
    path="/api/dungeon/progress/v1/", response_model=DungeonProgressResponse
)
async def dungeon_progress(
    payload: DungeonProgressRequest,
    game_server: CurrentGameServer,
) -> DungeonProgressResponse:
    """
    地下城流程推进接口

    处理战斗初始化、战斗状态评估、战斗归档和关卡推进等流程操作。

    Args:
        payload: 地下城流程推进请求对象
        game_server: 游戏服务器实例

    Returns:
        DungeonProgressResponse: 包含会话消息列表的响应对象

    Raises:
        HTTPException(404): 玩家未登录或游戏不存在
        HTTPException(400): 战斗状态不匹配
        HTTPException(409): 战斗已结束或地下城已通关
    """

    logger.info(
        f"/api/dungeon/progress/v1/: user={payload.user_name}, action={payload.action.value}"
    )

    # 验证地下城操作的前置条件
    rpg_game = _validate_dungeon_prerequisites(
        user_name=payload.user_name,
        game_server=game_server,
    )

    # 记录当前事件序列号，便于后续获取新增消息
    last_event_sequence: Final[int] = rpg_game.player_session.event_sequence

    # 根据操作类型分发处理
    match payload.action:
        case DungeonProgressType.INIT_COMBAT:
            # 处理地下城战斗开始
            if not rpg_game.current_combat_sequence.is_initializing:
                logger.error(
                    f"玩家 {payload.user_name} 战斗开始失败: 战斗未处于开始阶段"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="战斗未处于开始阶段",
                )
            # 推进战斗流程，转换到 ONGOING 状态
            await rpg_game.combat_execution_pipeline.process()
            return DungeonProgressResponse(
                session_messages=rpg_game.player_session.get_messages_since(
                    last_event_sequence
                )
            )

        case DungeonProgressType.COMBAT_STATUS_EVALUATION:
            if not (
                rpg_game.current_combat_sequence.is_ongoing
                or rpg_game.current_combat_sequence.is_completed
            ):
                logger.error(
                    f"玩家 {payload.user_name} 状态评估失败: 战斗未处于进行中或已结束状态"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="战斗未处于进行中或已结束状态",
                )

            # 评估战斗中角色的状态效果变化
            await rpg_game.combat_status_evaluation_pipeline.execute()
            return DungeonProgressResponse(
                session_messages=rpg_game.player_session.get_messages_since(
                    last_event_sequence
                )
            )

        case DungeonProgressType.POST_COMBAT:
            # 处理战斗结束后的归档和状态转换
            if not rpg_game.current_combat_sequence.is_completed:
                logger.error(f"玩家 {payload.user_name} 归档战斗失败: 战斗未结束")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="战斗未结束，无法归档",
                )

            # 验证战斗必须有结果（胜利或失败）
            if not (
                rpg_game.current_combat_sequence.is_won
                or rpg_game.current_combat_sequence.is_lost
            ):
                logger.error(f"玩家 {payload.user_name} 归档战斗失败: 战斗状态异常")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="战斗状态异常，既未胜利也未失败",
                )

            # 归档战斗记录（使用 pipeline）
            await rpg_game.combat_archive_pipeline.execute()

            # 进入战斗后准备状态
            rpg_game.current_combat_sequence.transition_to_post_combat()

            logger.info(f"玩家 {payload.user_name} 战斗归档完成，进入战斗后准备状态")
            return DungeonProgressResponse(
                session_messages=rpg_game.player_session.get_messages_since(
                    last_event_sequence
                )
            )

        case DungeonProgressType.ADVANCE_STAGE:
            # 处理前进下一个地下城关卡
            if not rpg_game.current_combat_sequence.is_post_combat:
                logger.error(
                    f"玩家 {payload.user_name} 前进下一关失败: 战斗未处于等待阶段"
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="战斗未处于等待阶段",
                )

            # 判断战斗结果并处理
            if rpg_game.current_combat_sequence.is_won:
                # 玩家胜利，检查是否有下一关
                next_stage = rpg_game.current_dungeon.peek_next_stage()
                if next_stage is None:
                    # 没有下一关了，地下城全部通关
                    logger.info(f"玩家 {payload.user_name} 地下城全部通关")
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="地下城已全部通关，请返回营地",
                    )
                # 前进到下一关
                advance_to_next_stage(rpg_game, rpg_game.current_dungeon)
                return DungeonProgressResponse(
                    session_messages=rpg_game.player_session.get_messages_since(
                        last_event_sequence
                    )
                )
            elif rpg_game.current_combat_sequence.is_lost:
                # 玩家失败
                logger.warning(f"玩家 {payload.user_name} 战斗失败")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="战斗失败，无法继续",
                )
            else:
                # 战斗状态异常（既没胜利也没失败）
                logger.error(f"玩家 {payload.user_name} 战斗状态异常: 既未胜利也未失败")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="战斗状态异常",
                )

        case DungeonProgressType.RETREAT:
            # 处理战斗中撤退
            if not rpg_game.current_combat_sequence.is_ongoing:
                logger.error(f"玩家 {payload.user_name} 撤退失败: 战斗未在进行中")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="只能在战斗进行中撤退",
                )

            # 执行撤退操作
            success, message = retreat_from_dungeon_combat(rpg_game)
            if not success:
                logger.error(f"玩家 {payload.user_name} 撤退失败: {message}")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"撤退失败: {message}",
                )

            logger.info(f"玩家 {payload.user_name} 撤退成功: {message}")

            # 执行战斗流程让 CombatOutcomeSystem 检测到角色死亡
            await rpg_game.combat_execution_pipeline.execute()

            # 转换到战斗后状态
            rpg_game.current_combat_sequence.transition_to_post_combat()

            # 返回家园
            complete_dungeon_and_return_home(rpg_game)

            logger.info(f"玩家 {payload.user_name} 已从地下城撤退并返回家园")
            return DungeonProgressResponse(
                session_messages=rpg_game.player_session.get_messages_since(
                    last_event_sequence
                )
            )

        case _:
            # 未知的操作类型，理论上不应该到达这里
            logger.error(f"未知的地下城操作类型: {payload.action}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"未知的操作类型: {payload.action}",
            )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_gameplay_api_router.post(
    path="/api/dungeon/trans_home/v1/", response_model=DungeonTransHomeResponse
)
async def dungeon_trans_home(
    payload: DungeonTransHomeRequest,
    game_server: CurrentGameServer,
) -> DungeonTransHomeResponse:
    """
    地下城传送回家接口

    处理玩家从地下城返回家园的传送请求。

    Args:
        payload: 地下城传送回家请求对象
        game_server: 游戏服务器实例

    Returns:
        DungeonTransHomeResponse: 包含传送结果的响应对象

    Raises:
        HTTPException(404): 玩家未登录或游戏不存在
        HTTPException(400): 战斗未结束
    """

    logger.info(f"/api/dungeon/trans_home/v1/: user={payload.user_name}")

    # 验证地下城操作的前置条件
    tcg_game = _validate_dungeon_prerequisites(
        user_name=payload.user_name,
        game_server=game_server,
    )

    # 验证战斗是否已结束
    if not tcg_game.current_combat_sequence.is_post_combat:
        logger.error(f"玩家 {payload.user_name} 返回家园失败: 战斗未结束")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能在战斗结束后回家",
        )

    # 完成地下城并返回家园
    complete_dungeon_and_return_home(tcg_game)
    logger.info(f"玩家 {payload.user_name} 成功返回家园")

    return DungeonTransHomeResponse(
        message="成功返回家园",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_gameplay_api_router.post(
    path="/api/dungeon/combat/draw_cards/v1/",
    response_model=DungeonCombatDrawCardsResponse,
)
async def dungeon_combat_draw_cards(
    payload: DungeonCombatDrawCardsRequest,
    game_server: CurrentGameServer,
) -> DungeonCombatDrawCardsResponse:
    """
    地下城战斗抽卡接口

    触发玩家在战斗中抽取卡牌的后台任务，立即返回任务ID。

    Args:
        payload: 地下城战斗抽卡请求对象
        game_server: 游戏服务器实例

    Returns:
        DungeonCombatDrawCardsResponse: 包含任务ID和状态的响应对象

    Raises:
        HTTPException(404): 玩家未登录或游戏不存在
        HTTPException(400): 战斗未在进行中
    """

    logger.info(f"/api/dungeon/combat/draw_cards/v1/: user={payload.user_name}")

    # 验证地下城操作的前置条件
    rpg_game = _validate_dungeon_prerequisites(
        user_name=payload.user_name,
        game_server=game_server,
    )

    # 验证战斗状态
    if not rpg_game.current_combat_sequence.is_ongoing:
        logger.error(f"玩家 {payload.user_name} 抽卡失败: 战斗未在进行中")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="战斗未在进行中",
        )

    # 为所有角色激活抽牌动作, 这2个函数内部不会进行LLM调用, 只是设置状态
    # 处理 Ally 阵营的抽牌 指定抽取：遍历每个指定动作
    for action in payload.specified_actions:
        success, message = activate_specified_expedition_member_card_draws(
            entity_name=action.entity_name,
            tcg_game=rpg_game,
            skill_name=action.skill_name,
            target_names=action.target_names,
            status_effect_names=action.status_effect_names,
        )
        if not success:
            logger.error(f"指定抽牌失败: {message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"激活抽牌动作失败: {message}",
            )

    # 敌人的就用随机（根据标记控制是否执行）
    if payload.enable_enemy_draw:
        success, message = activate_random_enemy_card_draws(rpg_game)
        if not success:
            logger.error(f"Enemy抽牌失败: {message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"激活Enemy抽牌动作失败: {message}",
            )

    # 创建抽卡后台任务
    draw_cards_task = game_server.create_task()

    # 使用 asyncio.create_task 创建真正的后台协程
    # 这样任务会立即在事件循环中异步执行，不会阻塞响应
    asyncio.create_task(
        _execute_draw_cards_task(
            draw_cards_task.task_id,
            payload.user_name,
            game_server,
        )
    )

    logger.info(
        f"📝 创建抽卡后台任务: task_id={draw_cards_task.task_id}, user={payload.user_name}"
    )

    return DungeonCombatDrawCardsResponse(
        task_id=draw_cards_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="抽卡任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_gameplay_api_router.post(
    path="/api/dungeon/combat/play_cards/v1/",
    response_model=DungeonCombatPlayCardsResponse,
)
async def dungeon_combat_play_cards(
    payload: DungeonCombatPlayCardsRequest,
    game_server: CurrentGameServer,
) -> DungeonCombatPlayCardsResponse:
    """
    地下城战斗出牌接口

    触发玩家在战斗中打出卡牌的后台任务，立即返回任务ID。

    Args:
        payload: 地下城战斗出牌请求对象
        game_server: 游戏服务器实例

    Returns:
        DungeonCombatPlayCardsResponse: 包含任务ID和状态的响应对象

    Raises:
        HTTPException(404): 玩家未登录或游戏不存在
        HTTPException(400): 战斗未在进行中
    """

    logger.info(f"/api/dungeon/combat/play_cards/v1/: user={payload.user_name}")

    # 验证地下城操作的前置条件
    rpg_game = _validate_dungeon_prerequisites(
        user_name=payload.user_name,
        game_server=game_server,
    )

    # 验证战斗状态
    if not rpg_game.current_combat_sequence.is_ongoing:
        logger.error(f"玩家 {payload.user_name} 出牌失败: 战斗未在进行中")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="战斗未在进行中",
        )

    # 创建出牌后台任务
    play_cards_task = game_server.create_task()

    # 使用 asyncio.create_task 创建真正的后台协程
    # 这样任务会立即在事件循环中异步执行，不会阻塞响应
    asyncio.create_task(
        _execute_play_cards_task(
            play_cards_task.task_id,
            payload.user_name,
            game_server,
        )
    )

    logger.info(
        f"📝 创建出牌后台任务: task_id={play_cards_task.task_id}, user={payload.user_name}"
    )

    return DungeonCombatPlayCardsResponse(
        task_id=play_cards_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="出牌任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _execute_draw_cards_task(
    task_id: str,
    user_name: str,
    game_server: GameServer,
) -> None:
    """后台执行抽卡任务

    在后台异步执行抽卡操作并更新任务状态。

    Args:
        task_id: 任务唯一标识符
        user_name: 用户名
        game_server: 游戏服务器实例
    """
    try:
        logger.info(f"🚀 抽卡任务开始: task_id={task_id}, user={user_name}")

        # 重新获取游戏实例（确保获取最新状态）
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._tcg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        rpg_game = current_room._tcg_game
        assert isinstance(rpg_game, TCGGame), "Invalid game type"

        # 验证战斗状态
        if not rpg_game.current_combat_sequence.is_ongoing:
            raise ValueError("战斗未在进行中")

        # 推进战斗流程处理抽牌
        # 注意: 这里会阻塞当前协程直到战斗流程处理完成
        # 但因为使用了 asyncio.create_task，这个阻塞只影响后台任务，不影响 API 响应
        await rpg_game.combat_execution_pipeline.process()

        # 保存结果
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.COMPLETED
            task_record.end_time = datetime.now().isoformat()

        logger.info(f"✅ 抽卡任务完成: task_id={task_id}, user={user_name}")

    except Exception as e:
        logger.error(f"❌ 抽卡任务失败: task_id={task_id}, user={user_name}, error={e}")
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _execute_play_cards_task(
    task_id: str,
    user_name: str,
    game_server: GameServer,
) -> None:
    """后台执行出牌任务

    在后台异步执行出牌操作并更新任务状态。

    Args:
        task_id: 任务唯一标识符
        user_name: 用户名
        game_server: 游戏服务器实例
    """
    try:
        logger.info(f"🚀 出牌任务开始: task_id={task_id}, user={user_name}")

        # 重新获取游戏实例（确保获取最新状态）
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._tcg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        rpg_game = current_room._tcg_game
        assert isinstance(rpg_game, TCGGame), "Invalid game type"

        # 验证战斗状态
        if not rpg_game.current_combat_sequence.is_ongoing:
            raise ValueError("战斗未在进行中")

        success, message = ensure_all_actors_have_fallback_cards(rpg_game)
        if not success:
            raise ValueError(f"确保所有角色都有后备牌失败: {message}")

        # 为所有角色随机选择并激活打牌动作
        success, message = activate_random_play_cards(rpg_game)
        if not success:
            raise ValueError(f"出牌失败: {message}")

        # 推进战斗流程处理出牌
        # 注意: 这里会阻塞当前协程直到战斗流程处理完成
        # 但因为使用了 asyncio.create_task，这个阻塞只影响后台任务，不影响 API 响应
        await rpg_game.combat_execution_pipeline.process()

        # 保存结果
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.COMPLETED
            task_record.end_time = datetime.now().isoformat()

        logger.info(f"✅ 出牌任务完成: task_id={task_id}, user={user_name}")

    except Exception as e:
        logger.error(f"❌ 出牌任务失败: task_id={task_id}, user={user_name}, error={e}")
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
