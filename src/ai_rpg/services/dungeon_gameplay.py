"""
地下城游戏玩法服务模块

提供地下城战斗的核心API接口，处理战斗流程、卡牌操作、关卡推进和返回家园等功能。
所有接口要求玩家已登录且位于地下城状态。
"""

import asyncio
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.dbg_game import DBGGame
from .game_server_dependencies import CurrentGameServer
from ..models import (
    CombatState,
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
from .dungeon_lifecycle import (
    advance_dungeon,
    exit_dungeon,
)
from .dungeon_actions import (
    activate_all_card_draws,
    activate_retreat,
    collect_combat_loot,
)
from .dungeon_tasks import (
    execute_init_combat_task,
    execute_retreat_task,
    execute_draw_cards_task,
    execute_play_cards_task,
    # _execute_exhaust_card_task,
    execute_pass_turn_task,
    execute_use_gear_task,
    execute_use_consumable_task,
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
) -> DBGGame:
    """
    验证地下城操作的前置条件

    验证玩家已登录、游戏实例存在、玩家在地下城状态且有可进行的战斗。

    Args:
        user_name: 用户名
        game_server: 游戏服务器实例

    Returns:
        DBGGame: 验证通过的游戏实例

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

    if current_room._dbg_game is None:
        logger.error(f"地下城操作失败: 玩家 {user_name} 没有游戏实例")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="游戏实例不存在，请重新登录",
        )

    # 3. 获取并验证游戏实例类型
    dbg_game = current_room._dbg_game
    assert isinstance(
        dbg_game, DBGGame
    ), f"_validate_dungeon_prerequisites: invalid game type for {user_name}"

    # 4. 验证玩家在地下城状态
    if not dbg_game.is_player_in_dungeon_stage:
        logger.error(f"地下城操作失败: 玩家 {user_name} 不在地下城状态")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能在地下城状态下使用",
        )

    # 5. 验证存在可进行的战斗
    # assert (
    #     dbg_game.current_dungeon.current_combat_room is not None
    # ), f"地下城操作失败: 玩家 {user_name} 当前尚未进入任何战斗房间"
    assert (
        dbg_game.current_combat_room.combat.state != CombatState.NONE
    ), f"地下城操作失败: 玩家 {user_name} 没有可进行的战斗"

    return dbg_game


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

        if not rpg_game.current_combat_room.combat.is_post_combat:
            logger.error(f"玩家 {payload.user_name} 前进下一关失败: 战斗未处于等待阶段")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="战斗未处于等待阶段",
            )

        if rpg_game.current_combat_room.combat.is_won:
            # 获取下一房间索引和房间实例，确保存在下一房间，否则无法推进地下城
            next_room_index = rpg_game.current_dungeon.current_room_index + 1
            next_room = rpg_game.current_dungeon.get_room(next_room_index)
            if next_room is None:
                logger.error(f"玩家 {payload.user_name} 地下城前进失败，没有更多房间")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="地下城已全部通关，请返回营地",
                )

            # 推进地下城到下一房间前，先检查下一房间是否存在，若不存在则抛出异常
            advance_dungeon(rpg_game, rpg_game.current_dungeon)

            # 推进地下城到下一房间后，返回成功消息
            return DungeonAdvanceStageResponse(message="已前进到下一关")
        elif rpg_game.current_combat_room.combat.is_lost:
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
        dbg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        # 验证战斗是否已结束
        if not dbg_game.current_combat_room.combat.is_post_combat:
            logger.error(f"玩家 {payload.user_name} 返回家园失败: 战斗未结束")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能在战斗结束后回家",
            )

        # 退出地下城并返回家园
        exit_dungeon(dbg_game, dbg_game._world.dungeon)
        logger.info(f"玩家 {payload.user_name} 成功返回家园")

        # 返回
        return DungeonExitResponse(
            message="成功返回家园",
        )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_gameplay_api_router.post(
    path="/api/dungeon/combat/collect_loot/v1/",
    response_model=DungeonCombatCollectLootResponse,
)
async def dungeon_combat_collect_loot(
    payload: DungeonCombatCollectLootRequest,
    game_server: CurrentGameServer,
) -> DungeonCombatCollectLootResponse:
    """
    收取战斗战利品接口

    将玩家实体上的 CombatLootComponent 中的道具全部转入随身背包（InventoryComponent），
    并移除临时战利品组件。

    Args:
        payload: 收取战利品请求对象
        game_server: 游戏服务器实例

    Returns:
        DungeonCombatCollectLootResponse: 包含收取结果消息的响应对象

    Raises:
        HTTPException(404): 玩家未登录或游戏不存在
        HTTPException(409): 无战利品可收取（本场无掉落或已收取）
    """

    logger.info(f"/api/dungeon/combat/collect_loot/v1/: user={payload.user_name}")

    current_room = game_server.get_room(payload.user_name)
    if current_room is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    async with current_room._lock:
        dbg_game = _validate_dungeon_prerequisites(
            user_name=payload.user_name,
            game_server=game_server,
        )

        success, message = collect_combat_loot(dbg_game)
        if not success:
            logger.warning(f"玩家 {payload.user_name} 收取战利品失败: {message}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=message,
            )

        logger.info(f"玩家 {payload.user_name} 收取战利品成功: {message}")
        return DungeonCombatCollectLootResponse(message=message)


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

        if not rpg_game.current_combat_room.combat.is_ongoing:
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
        execute_draw_cards_task(
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

        if not rpg_game.current_combat_room.combat.is_ongoing:
            logger.error(f"玩家 {payload.user_name} 出牌失败: 战斗未在进行中")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="战斗未在进行中",
            )

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

    return DungeonCombatPlayCardsResponse(
        task_id=play_cards_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="出牌任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_gameplay_api_router.post(
    path="/api/dungeon/combat/pass_turn/v1/",
    response_model=DungeonCombatPassTurnResponse,
)
async def dungeon_combat_pass_turn(
    payload: DungeonCombatPassTurnRequest,
    game_server: CurrentGameServer,
) -> DungeonCombatPassTurnResponse:
    """地下城战斗过牌接口

    触发指定角色跳过本次出牌机会（消耗 1 点 energy）的后台任务，立即返回任务ID。

    Raises:
        HTTPException(404): 玩家未登录或游戏不存在
        HTTPException(400): 战斗未在进行中或无未完成的回合
    """

    logger.info(f"/api/dungeon/combat/pass_turn/v1/: user={payload.user_name}")

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

        if not rpg_game.current_combat_room.combat.is_ongoing:
            logger.error(f"玩家 {payload.user_name} 过牌失败: 战斗未在进行中")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="战斗未在进行中",
            )

        last_round = rpg_game.current_combat_room.combat.latest_round
        if last_round is None or last_round.is_completed:
            logger.error(f"玩家 {payload.user_name} 过牌失败: 当前没有未完成的回合")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前没有未完成的回合可供过牌",
            )

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
    return DungeonCombatPassTurnResponse(
        task_id=pass_turn_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="过牌任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@dungeon_gameplay_api_router.post(
    path="/api/dungeon/combat/use_consumable/v1/",
    response_model=DungeonCombatUseConsumableItemResponse,
)
async def dungeon_combat_use_consumable(
    payload: DungeonCombatUseConsumableItemRequest,
    game_server: CurrentGameServer,
) -> DungeonCombatUseConsumableItemResponse:
    """地下城战斗使用消耗品接口

    触发玩家在战斗中使用背包内消耗品的后台任务，立即返回任务ID。

    Raises:
        HTTPException(404): 玩家未登录或游戏不存在
        HTTPException(400): 战斗未在进行中或无未完成的回合
    """

    logger.info(
        f"/api/dungeon/combat/use_consumable/v1/: user={payload.user_name} "
        f"item={payload.item_name}"
    )

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

        if not rpg_game.current_combat_room.combat.is_ongoing:
            logger.error(f"玩家 {payload.user_name} 使用消耗品失败: 战斗未在进行中")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="战斗未在进行中",
            )

        last_round = rpg_game.current_combat_room.combat.latest_round
        if last_round is None or last_round.is_completed:
            logger.error(
                f"玩家 {payload.user_name} 使用消耗品失败: 当前没有未完成的回合"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前没有未完成的回合",
            )

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

    return DungeonCombatUseConsumableItemResponse(
        task_id=use_consumable_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="使用消耗品任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
@dungeon_gameplay_api_router.post(
    path="/api/dungeon/combat/use_gear/v1/",
    response_model=DungeonCombatUseGearItemResponse,
)
async def dungeon_combat_use_gear(
    payload: DungeonCombatUseGearItemRequest,
    game_server: CurrentGameServer,
) -> DungeonCombatUseGearItemResponse:
    """地下城战斗使用装备接口。

    触发玩家在战斗中使用背包内装备的后台任务，立即返回任务ID。
    """

    logger.info(
        f"/api/dungeon/combat/use_gear/v1/: user={payload.user_name} "
        f"item={payload.item_name}"
    )

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

        if not rpg_game.current_combat_room.combat.is_ongoing:
            logger.error(f"玩家 {payload.user_name} 使用装备失败: 战斗未在进行中")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="战斗未在进行中",
            )

        last_round = rpg_game.current_combat_room.combat.latest_round
        if last_round is None or last_round.is_completed:
            logger.error(f"玩家 {payload.user_name} 使用装备失败: 当前没有未完成的回合")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="当前没有未完成的回合",
            )

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

    return DungeonCombatUseGearItemResponse(
        task_id=use_gear_task.task_id,
        status=TaskStatus.RUNNING.value,
        message="使用装备任务已启动，请通过会话消息查询结果",
    )


###################################################################################################################################################################
###################################################################################################################################################################
