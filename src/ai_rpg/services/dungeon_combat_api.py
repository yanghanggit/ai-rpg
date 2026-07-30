"""
副本战斗玩法服务模块（战斗房间内的专属接口）
"""

import asyncio
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from .game_server_dependencies import CurrentGameServer
from ..models import (
    DungeonCombatRetreatRequest,
    DungeonCombatRetreatResponse,
    DungeonCombatInitRequest,
    DungeonCombatInitResponse,
    DungeonCombatDrawCardsRequest,
    DungeonCombatDrawCardsResponse,
    DungeonCombatPlayCardsRequest,
    DungeonCombatPlayCardsResponse,
    DungeonCombatPassTurnRequest,
    DungeonCombatPassTurnResponse,
    DungeonCombatUseConsumableItemRequest,
    DungeonCombatUseConsumableItemResponse,
    DungeonCombatUseGearItemRequest,
    DungeonCombatUseGearItemResponse,
    DungeonCombatCollectLootRequest,
    DungeonCombatCollectLootResponse,
    TaskStatus,
)
from .dungeon_lifecycle_api import _validate_dungeon_prerequisites
from .dungeon_combat_actions import (
    activate_all_card_draws,
    activate_retreat,
    collect_combat_loot,
)
from .dungeon_combat_tasks import (
    execute_init_combat_task,
    execute_retreat_task,
    execute_draw_cards_task,
    execute_play_cards_task,
    execute_pass_turn_task,
    execute_use_gear_task,
    execute_use_consumable_task,
)

###################################################################################################################################################################
dungeon_combat_api_router = APIRouter()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_combat_api_router.post(
    path="/api/dungeon/combat/retreat/v1/", response_model=DungeonCombatRetreatResponse
)
async def dungeon_combat_retreat(
    payload: DungeonCombatRetreatRequest,
    game_server: CurrentGameServer,
) -> DungeonCombatRetreatResponse:
    """
    副本战斗撤退接口
    """

    logger.info(f"/api/dungeon/combat/retreat/v1/: user={payload.user_name}")

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:

        # 验证副本操作的前置条件
        rpg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 验证战斗是否在进行中
        if not rpg_game.current_combat_room.combat.is_ongoing:
            logger.error(f"玩家 {payload.user_name} 撤退失败: 战斗未在进行中")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能在战斗进行中撤退",
            )

        # 同步激活撤退动作（必须在 pipeline 执行前完成）
        success, message = activate_retreat(rpg_game)
        if not success:
            logger.error(f"玩家 {payload.user_name} 撤退失败: {message}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"撤退失败: {message}",
            )

        # 激活撤退动作成功
        logger.info(f"玩家 {payload.user_name} 撤退动作激活成功: {message}")

    # 在锁外创建后台 task，让任务在后台独立持锁执行
    retreat_task = game_server.create_task()
    asyncio.create_task(
        execute_retreat_task(
            retreat_task.task_id,
            payload.user_name,
            game_server,
        )
    )
    logger.info(
        f"📝 创建撤退任务: task_id={retreat_task.task_id}, user={payload.user_name}"
    )

    # 返回撤退任务启动成功的响应
    return DungeonCombatRetreatResponse(
        task_id=retreat_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="撤退任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_combat_api_router.post(
    path="/api/dungeon/combat/init/v1/", response_model=DungeonCombatInitResponse
)
async def dungeon_combat_init(
    payload: DungeonCombatInitRequest,
    game_server: CurrentGameServer,
) -> DungeonCombatInitResponse:
    """
    副本战斗初始化接口
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

        # 验证副本操作的前置条件
        rpg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 校验战斗处于初始化阶段
        if not rpg_game.current_combat_room.combat.is_initializing:
            logger.error(f"玩家 {payload.user_name} 战斗初始化失败: 战斗未处于开始阶段")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="战斗未处于开始阶段",
            )

    # 创建战斗初始化后台任务（在锁外创建，让任务在后台独立持锁执行）
    init_combat_task = game_server.create_task()
    asyncio.create_task(
        execute_init_combat_task(
            init_combat_task.task_id,
            payload.user_name,
            game_server,
        )
    )
    logger.info(
        f"📝 创建战斗初始化任务: task_id={init_combat_task.task_id}, user={payload.user_name}"
    )

    # 返回战斗初始化任务启动成功的响应
    return DungeonCombatInitResponse(
        task_id=init_combat_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="战斗初始化任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_combat_api_router.post(
    path="/api/dungeon/combat/collect_loot/v1/",
    response_model=DungeonCombatCollectLootResponse,
)
async def dungeon_combat_collect_loot(
    payload: DungeonCombatCollectLootRequest,
    game_server: CurrentGameServer,
) -> DungeonCombatCollectLootResponse:
    """
    收取战斗战利品接口
    """

    logger.info(f"/api/dungeon/combat/collect_loot/v1/: user={payload.user_name}")

    # 获取房间并用每玩家锁避免并发状态竞争
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:

        # 验证副本操作的前置条件
        dbg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 验证战斗是否已结束
        success, message = collect_combat_loot(dbg_game)
        if not success:
            logger.warning(f"玩家 {payload.user_name} 收取战利品失败: {message}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=message,
            )

        # 收取战利品成功
        logger.info(f"玩家 {payload.user_name} 收取战利品成功: {message}")
        return DungeonCombatCollectLootResponse(message=message)


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_combat_api_router.post(
    path="/api/dungeon/combat/draw_cards/v1/",
    response_model=DungeonCombatDrawCardsResponse,
)
async def dungeon_combat_draw_cards(
    payload: DungeonCombatDrawCardsRequest,
    game_server: CurrentGameServer,
) -> DungeonCombatDrawCardsResponse:
    """
    副本战斗全员抽卡接口
    """

    logger.info(f"/api/dungeon/combat/draw_cards/v1/: user={payload.user_name}")

    # 获取房间并用每玩家锁避免并发状态竞争
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:

        # 验证副本操作的前置条件
        rpg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 验证战斗是否在进行中
        if not rpg_game.current_combat_room.combat.is_ongoing:
            logger.error(f"玩家 {payload.user_name} 全员抽卡失败: 战斗未在进行中")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="战斗未在进行中",
            )

        # 同步激活全员抽牌动作（必须在 pipeline 执行前完成）
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
        execute_draw_cards_task(
            draw_task.task_id,
            payload.user_name,
            game_server,
        )
    )
    logger.info(
        f"📝 创建全员抽卡任务: task_id={draw_task.task_id}, user={payload.user_name}"
    )

    # 返回全员抽卡任务启动成功的响应
    return DungeonCombatDrawCardsResponse(
        task_id=draw_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="全员抽卡任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_combat_api_router.post(
    path="/api/dungeon/combat/play_cards/v1/",
    response_model=DungeonCombatPlayCardsResponse,
)
async def dungeon_combat_play_cards(
    payload: DungeonCombatPlayCardsRequest,
    game_server: CurrentGameServer,
) -> DungeonCombatPlayCardsResponse:
    """
    副本战斗出牌接口
    """

    logger.info(f"/api/dungeon/combat/play_cards/v1/: user={payload.user_name}")

    # 获取房间并用每玩家锁避免并发状态竞争
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:

        # 验证副本操作的前置条件
        rpg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 验证战斗是否在进行中
        if not rpg_game.current_combat_room.combat.is_ongoing:
            logger.error(f"玩家 {payload.user_name} 出牌失败: 战斗未在进行中")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="战斗未在进行中",
            )

        # 验证当前回合是否存在且未完成
        last_round = rpg_game.current_combat_room.combat.latest_round
        if last_round is None or last_round.is_completed:
            logger.error(f"玩家 {payload.user_name} 出牌失败: 当前没有未完成的回合")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前没有未完成的回合可供打牌",
            )

    # 在锁外创建后台 task，让任务在后台独立持锁执行
    play_cards_task = game_server.create_task()
    asyncio.create_task(
        execute_play_cards_task(
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

    # 返回出牌任务启动成功的响应
    return DungeonCombatPlayCardsResponse(
        task_id=play_cards_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="出牌任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_combat_api_router.post(
    path="/api/dungeon/combat/pass_turn/v1/",
    response_model=DungeonCombatPassTurnResponse,
)
async def dungeon_combat_pass_turn(
    payload: DungeonCombatPassTurnRequest,
    game_server: CurrentGameServer,
) -> DungeonCombatPassTurnResponse:
    """副本战斗过牌接口"""

    logger.info(f"/api/dungeon/combat/pass_turn/v1/: user={payload.user_name}")

    # 获取房间并用每玩家锁避免并发状态竞争
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:

        # 验证副本操作的前置条件
        rpg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 验证战斗是否在进行中
        if not rpg_game.current_combat_room.combat.is_ongoing:
            logger.error(f"玩家 {payload.user_name} 过牌失败: 战斗未在进行中")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="战斗未在进行中",
            )

        # 验证当前回合是否存在且未完成
        last_round = rpg_game.current_combat_room.combat.latest_round
        if last_round is None or last_round.is_completed:
            logger.error(f"玩家 {payload.user_name} 过牌失败: 当前没有未完成的回合")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前没有未完成的回合可供过牌",
            )

    # 在锁外创建后台 task，让任务在后台独立持锁执行
    pass_turn_task = game_server.create_task()
    asyncio.create_task(
        execute_pass_turn_task(
            pass_turn_task.task_id,
            payload.user_name,
            payload.actor_name,
            game_server,
        )
    )

    logger.info(
        f"📝 创建过牌后台任务: task_id={pass_turn_task.task_id}, user={payload.user_name}"
    )

    # 返回过牌任务启动成功的响应
    return DungeonCombatPassTurnResponse(
        task_id=pass_turn_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="过牌任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_combat_api_router.post(
    path="/api/dungeon/combat/use_consumable/v1/",
    response_model=DungeonCombatUseConsumableItemResponse,
)
async def dungeon_combat_use_consumable(
    payload: DungeonCombatUseConsumableItemRequest,
    game_server: CurrentGameServer,
) -> DungeonCombatUseConsumableItemResponse:
    """副本战斗使用消耗品接口"""

    logger.info(
        f"/api/dungeon/combat/use_consumable/v1/: user={payload.user_name} "
        f"item={payload.item_name}"
    )

    # 获取房间并用每玩家锁避免并发状态竞争
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:

        # 验证副本操作的前置条件
        rpg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 验证战斗是否在进行中
        if not rpg_game.current_combat_room.combat.is_ongoing:
            logger.error(f"玩家 {payload.user_name} 使用消耗品失败: 战斗未在进行中")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="战斗未在进行中",
            )

        # 验证当前回合是否存在且未完成
        last_round = rpg_game.current_combat_room.combat.latest_round
        if last_round is None or last_round.is_completed:
            logger.error(
                f"玩家 {payload.user_name} 使用消耗品失败: 当前没有未完成的回合"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前没有未完成的回合",
            )

    # 在锁外创建后台 task，让任务在后台独立持锁执行
    use_consumable_task = game_server.create_task()
    asyncio.create_task(
        execute_use_consumable_task(
            use_consumable_task.task_id,
            payload.user_name,
            payload.item_name,
            payload.targets,
            game_server,
        )
    )

    logger.info(
        f"📝 创建使用消耗品后台任务: task_id={use_consumable_task.task_id}, user={payload.user_name}"
    )

    # 返回使用消耗品任务启动成功的响应
    return DungeonCombatUseConsumableItemResponse(
        task_id=use_consumable_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="使用消耗品任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
@dungeon_combat_api_router.post(
    path="/api/dungeon/combat/use_gear/v1/",
    response_model=DungeonCombatUseGearItemResponse,
)
async def dungeon_combat_use_gear(
    payload: DungeonCombatUseGearItemRequest,
    game_server: CurrentGameServer,
) -> DungeonCombatUseGearItemResponse:
    """副本战斗使用装备接口。
    触发玩家在战斗中使用背包内装备的后台任务，立即返回任务ID。
    """

    logger.info(
        f"/api/dungeon/combat/use_gear/v1/: user={payload.user_name} "
        f"item={payload.item_name}"
    )

    # 获取房间并用每玩家锁避免并发状态竞争
    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:

        # 验证副本操作的前置条件
        rpg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 验证战斗是否在进行中
        if not rpg_game.current_combat_room.combat.is_ongoing:
            logger.error(f"玩家 {payload.user_name} 使用装备失败: 战斗未在进行中")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="战斗未在进行中",
            )

        # 验证当前回合是否存在且未完成
        last_round = rpg_game.current_combat_room.combat.latest_round
        if last_round is None or last_round.is_completed:
            logger.error(f"玩家 {payload.user_name} 使用装备失败: 当前没有未完成的回合")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前没有未完成的回合",
            )

    # 在锁外创建后台 task，让任务在后台独立持锁执行
    use_gear_task = game_server.create_task()
    asyncio.create_task(
        execute_use_gear_task(
            use_gear_task.task_id,
            payload.user_name,
            payload.item_name,
            payload.targets,
            game_server,
        )
    )

    logger.info(
        f"📝 创建使用装备后台任务: task_id={use_gear_task.task_id}, user={payload.user_name}"
    )

    # 返回使用装备任务启动成功的响应
    return DungeonCombatUseGearItemResponse(
        task_id=use_gear_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="使用装备任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
