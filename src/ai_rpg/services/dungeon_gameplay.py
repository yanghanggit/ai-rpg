"""
地下城游戏玩法服务模块

提供地下城战斗的核心API接口，处理战斗流程、卡牌操作、关卡推进和返回家园等功能。
所有接口要求玩家已登录且位于地下城状态。
"""

import asyncio
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.tcg_game import TCGGame
from ..game.world_store import archive_world
from .game_server_dependencies import CurrentGameServer
from ..models import (
    CombatState,
    EnemyComponent,
    DungeonCombatRetreatRequest,
    DungeonCombatRetreatResponse,
    DungeonAdvanceStageRequest,
    DungeonAdvanceStageResponse,
    DungeonExitRequest,
    DungeonExitResponse,
    DungeonCombatInitRequest,
    DungeonCombatInitResponse,
    DungeonCombatDrawCardsRequest,
    DungeonCombatDrawCardsResponse,
    DungeonCombatPlayCardsRequest,
    DungeonCombatPlayCardsResponse,
    TaskStatus,
)
from .dungeon_lifecycle import (
    advance_to_next_stage,
    exit_dungeon_and_return_home,
)
from .dungeon_actions import (
    activate_all_card_draws,
    activate_play_cards_specified,
    activate_enemy_play_trigger,
    activate_expedition_retreat,
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
    assert (
        tcg_game.current_dungeon.current_combat_room is not None
    ), f"地下城操作失败: 玩家 {user_name} 当前尚未进入任何战斗房间"
    assert (
        tcg_game.current_dungeon.current_combat_room.combat.state != CombatState.NONE
    ), f"地下城操作失败: 玩家 {user_name} 没有可进行的战斗"

    return tcg_game


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_gameplay_api_router.post(
    path="/api/dungeon/combat/retreat/v1/", response_model=DungeonCombatRetreatResponse
)
async def dungeon_combat_retreat(
    payload: DungeonCombatRetreatRequest,
    game_server: CurrentGameServer,
) -> DungeonCombatRetreatResponse:
    """
    地下城战斗撤退接口

    在战斗进行中触发撤退，同步标记撤退状态后启动后台任务执行 combat_pipeline，立即返回任务ID。

    Args:
        payload: 撤退请求对象
        game_server: 游戏服务器实例

    Returns:
        DungeonCombatRetreatResponse: 包含任务ID和状态的响应对象

    Raises:
        HTTPException(404): 玩家未登录或游戏不存在
        HTTPException(400): 战斗未在进行中
        HTTPException(409): 撤退标记失败
    """

    logger.info(f"/api/dungeon/combat/retreat/v1/: user={payload.user_name}")

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:
        rpg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        if not rpg_game.current_dungeon.is_ongoing:
            logger.error(f"玩家 {payload.user_name} 撤退失败: 战斗未在进行中")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能在战斗进行中撤退",
            )

        # 同步激活撤退动作（必须在 pipeline 执行前完成）
        success, message = activate_expedition_retreat(rpg_game)
        if not success:
            logger.error(f"玩家 {payload.user_name} 撤退失败: {message}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"撤退失败: {message}",
            )

        logger.info(f"玩家 {payload.user_name} 撤退动作激活成功: {message}")

    # 在锁外创建后台 task，让任务在后台独立持锁执行
    retreat_task = game_server.create_task()
    asyncio.create_task(
        _execute_retreat_task(
            retreat_task.task_id,
            payload.user_name,
            game_server,
        )
    )
    logger.info(
        f"📝 创建撤退任务: task_id={retreat_task.task_id}, user={payload.user_name}"
    )
    return DungeonCombatRetreatResponse(
        task_id=retreat_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="撤退任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_gameplay_api_router.post(
    path="/api/dungeon/progress/advance_stage/v1/",
    response_model=DungeonAdvanceStageResponse,
)
async def dungeon_advance_stage(
    payload: DungeonAdvanceStageRequest,
    game_server: CurrentGameServer,
) -> DungeonAdvanceStageResponse:
    """
    地下城关卡推进接口

    在战斗结束（post_combat 状态）后推进到下一关卡。

    Args:
        payload: 关卡推进请求对象
        game_server: 游戏服务器实例

    Returns:
        DungeonAdvanceStageResponse: 推进结果消息

    Raises:
        HTTPException(404): 玩家未登录或游戏不存在
        HTTPException(400): 战斗未处于 post_combat 状态或状态异常
        HTTPException(409): 地下城已全部通关或战斗失败
    """

    logger.info(f"/api/dungeon/progress/advance_stage/v1/: user={payload.user_name}")

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:
        rpg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        if not rpg_game.current_dungeon.is_post_combat:
            logger.error(f"玩家 {payload.user_name} 前进下一关失败: 战斗未处于等待阶段")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="战斗未处于等待阶段",
            )

        if rpg_game.current_dungeon.is_won:
            next_stage = rpg_game.current_dungeon.peek_next_stage()
            if next_stage is None:
                logger.info(f"玩家 {payload.user_name} 地下城全部通关")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="地下城已全部通关，请返回营地",
                )
            advance_to_next_stage(rpg_game, rpg_game.current_dungeon)
            return DungeonAdvanceStageResponse(message="已前进到下一关")
        elif rpg_game.current_dungeon.is_lost:
            logger.warning(f"玩家 {payload.user_name} 战斗失败")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="战斗失败，无法继续",
            )
        else:
            logger.error(f"玩家 {payload.user_name} 战斗状态异常: 既未胜利也未失败")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="战斗状态异常",
            )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_gameplay_api_router.post(
    path="/api/dungeon/combat/init/v1/", response_model=DungeonCombatInitResponse
)
async def dungeon_combat_init(
    payload: DungeonCombatInitRequest,
    game_server: CurrentGameServer,
) -> DungeonCombatInitResponse:
    """
    地下城战斗初始化接口

    触发战斗初始化后台任务，推进战斗从 INITIALIZING 转换到 ONGOING 状态，立即返回任务ID。

    Args:
        payload: 地下城战斗初始化请求对象
        game_server: 游戏服务器实例

    Returns:
        DungeonCombatInitResponse: 包含任务ID和状态的响应对象

    Raises:
        HTTPException(404): 玩家未登录或游戏不存在
        HTTPException(400): 战斗未处于开始阶段
    """

    logger.info(f"/api/dungeon/combat/init/v1/: user={payload.user_name}")

    # 获取房间并用每玩家锁避免并发状态竞争
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:
        # 验证地下城操作的前置条件
        rpg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 校验战斗处于初始化阶段
        if not rpg_game.current_dungeon.is_initializing:
            logger.error(f"玩家 {payload.user_name} 战斗初始化失败: 战斗未处于开始阶段")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="战斗未处于开始阶段",
            )

    # 创建战斗初始化后台任务（在锁外创建，让任务在后台独立持锁执行）
    init_combat_task = game_server.create_task()
    asyncio.create_task(
        _execute_init_combat_task(
            init_combat_task.task_id,
            payload.user_name,
            game_server,
        )
    )
    logger.info(
        f"📝 创建战斗初始化任务: task_id={init_combat_task.task_id}, user={payload.user_name}"
    )
    return DungeonCombatInitResponse(
        task_id=init_combat_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="战斗初始化任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_gameplay_api_router.post(
    path="/api/dungeon/exit/v1/", response_model=DungeonExitResponse
)
async def dungeon_exit(
    payload: DungeonExitRequest,
    game_server: CurrentGameServer,
) -> DungeonExitResponse:
    """
    地下城退出接口

    处理玩家从地下城返回家园的退出请求。
    适用于所有结束场景：战斗胜利、战斗失败、主动撤退等。

    Args:
        payload: 地下城退出请求对象
        game_server: 游戏服务器实例

    Returns:
        DungeonExitResponse: 包含退出结果的响应对象

    Raises:
        HTTPException(404): 玩家未登录或游戏不存在
        HTTPException(400): 战斗未结束
    """

    logger.info(f"/api/dungeon/exit/v1/: user={payload.user_name}")

    # 获取房间并用每玩家锁避免并发状态竞争
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:
        # 验证地下城操作的前置条件
        tcg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 验证战斗是否已结束
        if not tcg_game.current_dungeon.is_post_combat:
            logger.error(f"玩家 {payload.user_name} 返回家园失败: 战斗未结束")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能在战斗结束后回家",
            )

        # 退出地下城并返回家园
        exit_dungeon_and_return_home(tcg_game, tcg_game._world.dungeon)
        logger.info(f"玩家 {payload.user_name} 成功返回家园")

        # 返回
        return DungeonExitResponse(
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
    地下城战斗全员抽卡接口

    为场景中所有存活的战斗角色（远征队成员 + 敌方）激活抽牌动作，
    触发后台任务执行 combat_pipeline，立即返回任务ID。

    Args:
        payload: 抽卡请求对象
        game_server: 游戏服务器实例

    Returns:
        DungeonCombatDrawCardsResponse: 包含任务ID和状态的响应对象

    Raises:
        HTTPException(404): 玩家未登录或游戏不存在
        HTTPException(400): 战斗未在进行中或抽牌激活失败
    """

    logger.info(f"/api/dungeon/combat/draw_cards/v1/: user={payload.user_name}")

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:
        rpg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        if not rpg_game.current_dungeon.is_ongoing:
            logger.error(f"玩家 {payload.user_name} 全员抽卡失败: 战斗未在进行中")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="战斗未在进行中",
            )

        success, message = activate_all_card_draws(rpg_game)
        if not success:
            logger.error(f"全员抽牌失败: {message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"激活全员抽牌动作失败: {message}",
            )

    # 创建后台任务（在锁外创建，让任务在后台独立持锁执行）
    draw_task = game_server.create_task()
    asyncio.create_task(
        _execute_draw_cards_task(
            draw_task.task_id,
            payload.user_name,
            game_server,
        )
    )
    logger.info(
        f"📝 创建全员抽卡任务: task_id={draw_task.task_id}, user={payload.user_name}"
    )
    return DungeonCombatDrawCardsResponse(
        task_id=draw_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="全员抽卡任务已启动，请通过会话消息查询结果",
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

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:
        rpg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        if not rpg_game.current_dungeon.is_ongoing:
            logger.error(f"玩家 {payload.user_name} 出牌失败: 战斗未在进行中")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="战斗未在进行中",
            )

        last_round = rpg_game.current_dungeon.latest_round
        if last_round is None or last_round.is_round_completed:
            logger.error(f"玩家 {payload.user_name} 出牌失败: 当前没有未完成的回合")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前没有未完成的回合可供打牌",
            )

    # 在锁外创建后台 task，让任务在后台独立持锁执行
    play_cards_task = game_server.create_task()
    asyncio.create_task(
        _execute_play_cards_task(
            play_cards_task.task_id,
            payload.user_name,
            payload.actor_name,
            payload.card_name,
            payload.targets,
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
async def _execute_init_combat_task(
    task_id: str,
    user_name: str,
    game_server: GameServer,
) -> None:
    """后台执行战斗初始化任务

    在后台异步执行战斗初始化并更新任务状态。
    推进 combat_pipeline 将战斗从 INITIALIZING 转换到 ONGOING 状态。

    Args:
        task_id: 任务唯一标识符
        user_name: 用户名
        game_server: 游戏服务器实例
    """
    try:
        logger.info(f"🚀 战斗初始化任务开始: task_id={task_id}, user={user_name}")

        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._tcg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:
            rpg_game = current_room._tcg_game
            assert isinstance(rpg_game, TCGGame), "Invalid game type"

            if not rpg_game.current_dungeon.is_initializing:
                raise ValueError("战斗未处于开始阶段")

            await rpg_game._combat_pipeline.process()

            # 存储战斗初始化后的世界状态，便于调试和回放
            archive_world(rpg_game._world, rpg_game._player_session)

        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.COMPLETED
            task_record.end_time = datetime.now().isoformat()

        logger.info(f"✅ 战斗初始化任务完成: task_id={task_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 战斗初始化任务失败: task_id={task_id}, user={user_name}, error={e}"
        )
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _execute_retreat_task(
    task_id: str,
    user_name: str,
    game_server: GameServer,
) -> None:
    """后台执行撤退任务

    在后台异步执行撤退战斗流程，让 RetreatActionSystem 标记死亡，CombatOutcomeSystem 判定失败，
    最终进入 post_combat 状态。退出地下城统一由 /api/dungeon/exit/v1/ 接口处理。

    注意：activate_expedition_retreat 已在 HTTP handler 锁内执行完毕，此处只负责 pipeline 执行。

    Args:
        task_id: 任务唯一标识符
        user_name: 用户名
        game_server: 游戏服务器实例
    """
    try:
        logger.info(f"🚀 撤退任务开始: task_id={task_id}, user={user_name}")

        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._tcg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:
            rpg_game = current_room._tcg_game
            assert isinstance(rpg_game, TCGGame), "Invalid game type"

            # 执行战斗流程让 CombatOutcomeSystem 检测到角色死亡并判定失败
            await rpg_game._combat_pipeline.execute()

            # 确认已进入 post_combat 状态
            if not rpg_game.current_dungeon.is_post_combat:
                raise RuntimeError(
                    "战斗管线执行后未进入 post_combat 状态，撤退流程异常"
                )

            # 存储撤退后进入 post_combat 状态的世界状态，便于调试和回放
            archive_world(rpg_game._world, rpg_game._player_session)

        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.COMPLETED
            task_record.end_time = datetime.now().isoformat()

        logger.info(
            f"✅ 撤退任务完成: task_id={task_id}, user={user_name}, "
            f"战斗已标记为失败。请调用 /api/dungeon/exit/v1/ 返回家园。"
        )

    except Exception as e:
        logger.error(f"❌ 撤退任务失败: task_id={task_id}, user={user_name}, error={e}")
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


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

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._tcg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:
            rpg_game = current_room._tcg_game
            assert isinstance(rpg_game, TCGGame), "Invalid game type"

            # 验证战斗状态
            if not rpg_game.current_dungeon.is_ongoing:
                raise ValueError("战斗未在进行中")

            # 推进战斗流程处理抽牌
            # 注意: 这里会阻塞当前协程直到战斗流程处理完成
            # 但因为使用了 asyncio.create_task，这个阻塞只影响后台任务，不影响 API 响应
            await rpg_game._combat_pipeline.process()

            # 存储抽牌后的世界状态，便于调试和回放
            archive_world(rpg_game._world, rpg_game._player_session)

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
    actor_name: str,
    card_name: str,
    targets: List[str],
    game_server: GameServer,
) -> None:
    """后台执行出牌任务

    在后台异步执行出牌操作并更新任务状态。

    Args:
        task_id: 任务唯一标识符
        user_name: 用户名
        actor_name: 出牌角色全名
        card_name: 要打出的卡牌名称
        targets: 目标名称列表
        game_server: 游戏服务器实例
    """
    try:
        logger.info(f"🚀 出牌任务开始: task_id={task_id}, user={user_name}")

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._tcg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:
            rpg_game = current_room._tcg_game
            assert isinstance(rpg_game, TCGGame), "Invalid game type"

            # 验证战斗状态
            if not rpg_game.current_dungeon.is_ongoing:
                raise ValueError("战斗未在进行中")

            actor_entity = rpg_game.get_actor_entity(actor_name)
            if actor_entity is not None and actor_entity.has(EnemyComponent):
                success, message = activate_enemy_play_trigger(rpg_game, actor_name)
            else:
                success, message = activate_play_cards_specified(
                    rpg_game, actor_name, card_name, targets
                )
            if not success:
                raise ValueError(f"出牌失败: {message}")

            # 推进战斗流程处理出牌
            await rpg_game._combat_pipeline.process()

            # 存储出牌后的世界状态，便于调试和回放
            archive_world(rpg_game._world, rpg_game._player_session)

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
