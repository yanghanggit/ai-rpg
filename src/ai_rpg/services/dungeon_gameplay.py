"""
地下城游戏玩法服务模块

本模块提供地下城系统的核心API接口，负责处理玩家在地下城探险中的各种战斗操作。
地下城是游戏的核心PVE内容，玩家需要在此进行回合制卡牌战斗，击败敌人并推进关卡。

主要功能:
    - 战斗流程管理: 处理战斗开始、进行、结束的完整流程
    - 卡牌操作: 处理抽卡和出牌等核心战斗行为
    - 关卡推进: 处理地下城关卡的前进和通关
    - 返回家园: 处理从地下城返回家园的传送

API端点:
    - POST /api/dungeon/gameplay/v1/: 地下城游戏玩法主接口
    - POST /api/dungeon/trans_home/v1/: 地下城传送回家接口

核心概念:
    - Combat Sequence: 战斗序列，管理整个战斗的状态和流程
    - Combat Pipeline: 战斗处理流程，负责执行战斗中的各种动作
    - Stage: 地下城关卡，玩家需要逐个挑战
    - Round System: 回合系统，管理战斗中的行动顺序

战斗状态:
    - STARTING: 战斗准备开始阶段
    - ONGOING: 战斗进行中
    - WAITING: 战斗结束，等待下一步操作

依赖关系:
    - GameServer: 游戏服务器实例，管理所有玩家房间
    - TCGGame: 具体的游戏实例，包含玩家状态和战斗逻辑
    - dungeon_actions: 地下城动作激活模块（抽牌、出牌等）
    - dungeon_stage_transition: 地下城关卡转换相关逻辑

使用说明:
    所有接口都需要玩家处于已登录状态，且当前位置必须在地下城。
    接口会自动验证玩家状态和战斗状态，验证失败会抛出相应的HTTP异常。
"""

import asyncio
from datetime import datetime
from typing import Final
from fastapi import APIRouter, HTTPException, status
from loguru import logger
from ..game.tcg_game import TCGGame
from .game_server_dependencies import CurrentGameServer
from ..models import (
    DungeonGamePlayRequest,
    DungeonGamePlayResponse,
    DungeonTransHomeRequest,
    DungeonTransHomeResponse,
    DungeonCombatPlayCardsRequest,
    DungeonCombatPlayCardsResponse,
    TaskStatus,
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
@dungeon_gameplay_api_router.post(
    path="/api/dungeon/gameplay/v1/", response_model=DungeonGamePlayResponse
)
async def dungeon_gameplay(
    payload: DungeonGamePlayRequest,
    game_server: CurrentGameServer,
) -> DungeonGamePlayResponse:
    """
    地下城游戏玩法主接口，处理玩家在地下城中的各种战斗操作

    该接口是地下城战斗系统的核心处理入口，根据玩家的不同操作标记(tag)分发到对应的处理逻辑。
    支持的操作包括：战斗开始、抽卡、出牌、前进下一关等。所有操作都需要玩家处于地下城状态。

    Args:
        payload: 地下城游戏玩法请求对象，包含用户名和用户输入信息
            - user_name: 用户名，用于标识玩家
            - user_input: 用户输入对象，包含操作标记(tag)和相关数据(data)
        game_server: 游戏服务器实例，由依赖注入提供

    Returns:
        DungeonGamePlayResponse: 地下城游戏玩法响应对象
            - client_messages: 返回给客户端的消息列表

    Raises:
        HTTPException(404): 玩家未登录、游戏实例不存在或没有战斗
        HTTPException(400): 玩家不在地下城状态、战斗状态不匹配或请求类型未知
        HTTPException(409): 战斗已结束（胜利或失败）

    支持的操作标记:
        - combat_init: 开始地下城战斗，转换到战斗进行状态
        - draw_cards: 抽卡操作，为所有角色抽取手牌
        - play_cards: 出牌操作，角色使用手牌进行战斗
        - advance_next_dungeon: 前进到下一个地下城关卡
    """

    logger.info(
        f"/api/dungeon/gameplay/v1/: user={payload.user_name}, action={payload.user_input.tag}"
    )

    # 验证地下城操作的前置条件
    rpg_game = _validate_dungeon_prerequisites(
        user_name=payload.user_name,
        game_server=game_server,
    )

    # 记录当前事件序列号，便于后续获取新增消息
    last_event_sequence: Final[int] = rpg_game.player_session.event_sequence

    # 根据操作类型分发处理
    match payload.user_input.tag:
        case "combat_init":
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
            await rpg_game.combat_pipeline.process()
            return DungeonGamePlayResponse(
                session_messages=rpg_game.player_session.get_messages_since(
                    last_event_sequence
                )
            )

        case "draw_cards":
            # 处理抽卡操作
            if not rpg_game.current_combat_sequence.is_ongoing:
                logger.error(f"玩家 {payload.user_name} 抽卡失败: 战斗未在进行中")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="战斗未在进行中",
                )
            # 为所有角色激活抽牌动作
            activate_actor_card_draws(rpg_game)
            # 推进战斗流程处理抽牌
            await rpg_game.combat_pipeline.process()
            return DungeonGamePlayResponse(
                session_messages=rpg_game.player_session.get_messages_since(
                    last_event_sequence
                )
            )

        case "advance_next_dungeon":
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
                return DungeonGamePlayResponse(
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

        case _:
            # 未知的操作类型
            logger.error(
                f"玩家 {payload.user_name} 未知的请求类型: {payload.user_input.tag}"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"未知的请求类型: {payload.user_input.tag}",
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
    地下城传送回家接口，处理玩家从地下城返回家园的传送请求

    该接口负责将玩家从地下城状态传送回家园。在传送前会验证玩家状态和战斗是否已结束，
    然后完成地下城并执行返回家园的流程。这是玩家结束地下城探险的出口。

    Args:
        payload: 地下城传送回家请求对象
            - user_name: 用户名，用于标识玩家
        game_server: 游戏服务器实例，由依赖注入提供

    Returns:
        DungeonTransHomeResponse: 地下城传送回家响应对象
            - message: 包含传送结果的响应消息

    Raises:
        HTTPException(404): 玩家未登录、游戏实例不存在或没有战斗
        HTTPException(400): 玩家不在地下城状态或战斗未结束

    处理流程:
        1. 验证玩家是否在地下城状态
        2. 检查战斗是否已结束（处于等待阶段）
        3. 完成地下城并返回家园
        4. 返回传送成功响应

    注意事项:
        - 玩家必须处于地下城状态才能返回家园
        - 必须在战斗结束后才能返回
        - 返回后玩家状态将切换到家园状态
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
    path="/api/dungeon/combat/play_cards/v1/",
    response_model=DungeonCombatPlayCardsResponse,
)
async def dungeon_combat_play_cards(
    payload: DungeonCombatPlayCardsRequest,
    game_server: CurrentGameServer,
) -> DungeonCombatPlayCardsResponse:
    """
    地下城战斗出牌接口（真正的后台任务版），触发玩家在战斗中打出卡牌的后台任务

    该接口负责创建并触发玩家在地下城战斗中的出牌后台任务。出牌操作会使用 asyncio.create_task
    在事件循环中异步执行，客户端会立即得到响应而不必等待耗时的战斗流程处理完成。

    Args:
        payload: 地下城战斗出牌请求对象
            - user_name: 用户名，用于标识玩家
            - game_name: 游戏名称
        game_server: 游戏服务器实例，由依赖注入提供

    Returns:
        DungeonCombatPlayCardsResponse: 地下城战斗出牌响应对象
            - task_id: 任务唯一标识符，可用于后续查询任务状态
            - status: 任务初始状态（"running"）
            - message: 提示信息

    Raises:
        HTTPException(404): 玩家未登录、游戏实例不存在或没有战斗
        HTTPException(400): 玩家不在地下城状态或战斗未在进行中

    处理流程:
        1. 验证玩家是否在地下城状态
        2. 检查战斗是否在进行中
        3. 生成任务ID并初始化任务信息
        4. 使用 asyncio.create_task 创建真正的后台协程
        5. 立即返回任务信息（不等待任务完成）

    注意事项:
        - 战斗必须处于 ONGOING 状态才能触发任务
        - 使用 asyncio.create_task 确保任务真正在后台执行，不阻塞响应
        - 客户端会立即收到响应，任务在事件循环中异步执行
        - 客户端需要通过其他方式（如轮询会话消息）获取任务结果
        - 任务信息存储在内存中，服务重启后会丢失
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
async def _execute_play_cards_task(
    task_id: str,
    user_name: str,
    game_server: GameServer,
) -> None:
    """后台执行出牌任务

    在后台异步执行出牌操作，包括激活打牌动作和推进战斗流程。
    任务完成后会更新任务存储中的状态和消息。

    Args:
        task_id: 任务唯一标识符
        user_name: 用户名，用于获取游戏实例
        game_server: 游戏服务器实例
        last_event_sequence: 任务开始前的事件序列号

    Note:
        - 任务执行期间会记录日志
        - 任务完成后状态会更新为 "completed"，并保存会话消息
        - 异常情况下状态会更新为 "failed"，并记录错误信息
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

        # 为所有角色随机选择并激活打牌动作
        success, message = activate_random_play_cards(rpg_game)
        if not success:
            raise ValueError(f"出牌失败: {message}")

        # 推进战斗流程处理出牌
        # 注意: 这里会阻塞当前协程直到战斗流程处理完成
        # 但因为使用了 asyncio.create_task，这个阻塞只影响后台任务，不影响 API 响应
        await rpg_game.combat_pipeline.process()

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
