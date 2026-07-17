"""
地下城后台任务模块
"""

from datetime import datetime
from typing import List
from loguru import logger
from ..game.dbg_game import DBGGame
from ..game.world_store import archive_world
from ..game.game_server import GameServer
from ..models import MonsterComponent, TaskStatus
from .dungeon_actions import (
    activate_monster_play_trigger,
    activate_play_cards_specified,
    activate_pass_turn,
    activate_use_gear,
    activate_use_consumable,
)


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def execute_init_combat_task(
    task_id: str,
    user_name: str,
    game_server: GameServer,
) -> None:
    """后台执行战斗初始化任务"""
    try:

        logger.info(f"🚀 战斗初始化任务开始: task_id={task_id}, user={user_name}")

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证游戏实例类型
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证战斗状态
            if not rpg_game.current_combat_room.combat.is_initializing:
                raise ValueError("战斗未处于开始阶段")

            # 推进战斗流程处理战斗初始化
            await rpg_game._combat_pipeline.process()

            # 存储战斗初始化后的世界状态，便于调试和回放
            archive_world(rpg_game._world, rpg_game._player_session)

        # 保存结果
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.COMPLETED
            task_record.end_time = datetime.now().isoformat()

        logger.info(f"✅ 战斗初始化任务完成: task_id={task_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 战斗初始化任务失败: task_id={task_id}, user={user_name}, error={e}"
        )

        # 保存失败结果
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def execute_retreat_task(
    task_id: str,
    user_name: str,
    game_server: GameServer,
) -> None:
    """后台执行撤退任务"""
    try:

        logger.info(f"🚀 撤退任务开始: task_id={task_id}, user={user_name}")

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证战斗状态
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 执行战斗流程让 CombatOutcomeSystem 检测到角色死亡并判定失败
            await rpg_game._combat_pipeline.execute()

            # 确认已进入 post_combat 状态
            if not rpg_game.current_combat_room.combat.is_post_combat:
                raise RuntimeError(
                    "战斗管线执行后未进入 post_combat 状态，撤退流程异常"
                )

            # 存储撤退后进入 post_combat 状态的世界状态，便于调试和回放
            archive_world(rpg_game._world, rpg_game._player_session)

        # 保存结果
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

        # 保存失败结果
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def execute_draw_cards_task(
    task_id: str,
    user_name: str,
    game_server: GameServer,
) -> None:
    """后台执行抽卡任务"""
    try:

        logger.info(f"🚀 抽卡任务开始: task_id={task_id}, user={user_name}")

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证游戏实例类型
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证战斗状态
            if not rpg_game.current_combat_room.combat.is_ongoing:
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

        # 保存失败结果
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def execute_play_cards_task(
    task_id: str,
    user_name: str,
    actor_name: str,
    card_name: str,
    targets: List[str],
    game_server: GameServer,
) -> None:
    """后台执行出牌任务"""
    try:
        logger.info(f"🚀 出牌任务开始: task_id={task_id}, user={user_name}")

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证游戏实例类型
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证战斗状态
            if not rpg_game.current_combat_room.combat.is_ongoing:
                raise ValueError("战斗未在进行中")

            # 根据 actor_name 判断是玩家角色还是怪物，分别处理出牌逻辑
            actor_entity = rpg_game.get_actor_entity(actor_name)
            if actor_entity is not None and actor_entity.has(MonsterComponent):
                # 如果是怪物，则触发怪物的出牌逻辑
                success, message = activate_monster_play_trigger(rpg_game, actor_name)
            else:
                # 如果是玩家角色，则处理玩家的出牌逻辑
                success, message = await activate_play_cards_specified(
                    rpg_game, actor_name, card_name, targets
                )

            # 验证出牌是否成功
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

        # 保存失败结果
        logger.error(f"❌ 出牌任务失败: task_id={task_id}, user={user_name}, error={e}")
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def execute_pass_turn_task(
    task_id: str,
    user_name: str,
    actor_name: str,
    game_server: GameServer,
) -> None:
    """后台执行过牌任务"""
    try:
        logger.info(f"🚀 过牌任务开始: task_id={task_id}, user={user_name}")

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证游戏实例类型
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证战斗状态
            if not rpg_game.current_combat_room.combat.is_ongoing:
                raise ValueError("战斗未在进行中")

            # 执行过牌逻辑
            success, message = activate_pass_turn(rpg_game, actor_name)
            if not success:
                raise ValueError(f"过牌失败: {message}")

            # 处理战斗流水线
            await rpg_game._combat_pipeline.process()

            # 存储过牌后的世界状态，便于调试和回放
            archive_world(rpg_game._world, rpg_game._player_session)

        # 保存结果
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.COMPLETED
            task_record.end_time = datetime.now().isoformat()

        logger.info(f"✅ 过牌任务完成: task_id={task_id}, user={user_name}")

    except Exception as e:

        # 保存失败结果
        logger.error(f"❌ 过牌任务失败: task_id={task_id}, user={user_name}, error={e}")
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def execute_use_consumable_task(
    task_id: str,
    user_name: str,
    item_name: str,
    targets: List[str],
    game_server: GameServer,
) -> None:
    """后台执行使用消耗品任务"""
    try:

        logger.info(f"🚀 使用消耗品任务开始: task_id={task_id}, user={user_name}")

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证游戏实例类型
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证战斗状态
            if not rpg_game.current_combat_room.combat.is_ongoing:
                raise ValueError("战斗未在进行中")

            # 执行使用消耗品逻辑
            success, message = activate_use_consumable(rpg_game, item_name, targets)
            if not success:
                raise ValueError(f"使用消耗品失败: {message}")

            # 处理战斗流水线
            await rpg_game._combat_pipeline.process()

            # 存储使用消耗品后的世界状态，便于调试和回放
            archive_world(rpg_game._world, rpg_game._player_session)

        # 保存结果
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.COMPLETED
            task_record.end_time = datetime.now().isoformat()

        logger.info(f"✅ 使用消耗品任务完成: task_id={task_id}, user={user_name}")

    except Exception as e:

        # 保存失败结果
        logger.error(
            f"❌ 使用消耗品任务失败: task_id={task_id}, user={user_name}, error={e}"
        )
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


###################################################################################################################################################################
###################################################################################################################################################################
async def execute_use_gear_task(
    task_id: str,
    user_name: str,
    item_name: str,
    targets: List[str],
    game_server: GameServer,
) -> None:
    """后台执行使用装备任务"""
    try:

        logger.info(f"🚀 使用装备任务开始: task_id={task_id}, user={user_name}")

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证游戏实例类型
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证战斗状态
            if not rpg_game.current_combat_room.combat.is_ongoing:
                raise ValueError("战斗未在进行中")

            # 执行使用装备逻辑
            success, message = activate_use_gear(rpg_game, item_name, targets)
            if not success:
                raise ValueError(f"使用装备失败: {message}")

            # 处理战斗流水线
            await rpg_game._combat_pipeline.process()

            # 存储使用装备后的世界状态，便于调试和回放
            archive_world(rpg_game._world, rpg_game._player_session)

        # 保存结果
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.COMPLETED
            task_record.end_time = datetime.now().isoformat()

        logger.info(f"✅ 使用装备任务完成: task_id={task_id}, user={user_name}")

    except Exception as e:

        # 保存失败结果
        logger.error(
            f"❌ 使用装备任务失败: task_id={task_id}, user={user_name}, error={e}"
        )
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


###################################################################################################################################################################
###################################################################################################################################################################
