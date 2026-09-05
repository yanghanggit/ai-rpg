"""
副本战斗后台任务模块
"""

from procrastinate import JobContext
from loguru import logger
from ..game.dbg_game import DBGGame
from ..game.dbg_store import store_game
from ..pgsql import procrastinate_app, save_task_error
from .game_server_dependencies import get_game_server


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_init_combat_task(
    context: JobContext,
    user_name: str,
) -> None:
    """后台执行战斗初始化任务"""
    job_id = str(context.job.id)
    try:

        logger.info(f"🚀 战斗初始化任务开始: job_id={job_id}, user={user_name}")

        game_server = get_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证游戏实例类型
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证当前副本房间是否为战斗房间
            if not rpg_game.is_current_room_dungeon_combat:
                raise ValueError("当前副本房间不是战斗房间")

            # 验证战斗状态
            if not rpg_game.current_dungeon_combat_room.combat.is_initializing:
                raise ValueError("战斗未处于开始阶段")

            # 推进战斗流程处理战斗初始化
            await rpg_game._dungeon_combat_room_pipeline.process()

            # 存储战斗初始化后的世界状态，便于调试和回放
            store_game(rpg_game)

        logger.info(f"✅ 战斗初始化任务完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 战斗初始化任务失败: job_id={job_id}, user={user_name}, error={e}"
        )
        save_task_error(job_id, str(e))
        raise


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_retreat_task(
    context: JobContext,
    user_name: str,
) -> None:
    """后台执行撤退任务"""
    job_id = str(context.job.id)
    try:

        logger.info(f"🚀 撤退任务开始: job_id={job_id}, user={user_name}")

        game_server = get_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证战斗状态
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证当前副本房间是否为战斗房间
            if not rpg_game.is_current_room_dungeon_combat:
                raise ValueError("当前副本房间不是战斗房间")

            # 执行战斗流程让 CombatOutcomeSystem 检测到角色死亡并判定失败
            await rpg_game._dungeon_combat_room_pipeline.execute()

            # 确认已进入 post_combat 状态
            if not rpg_game.current_dungeon_combat_room.combat.is_post_combat:
                raise RuntimeError(
                    "战斗管线执行后未进入 post_combat 状态，撤退流程异常"
                )

            # 存储撤退后进入 post_combat 状态的世界状态，便于调试和回放
            store_game(rpg_game)

        logger.info(
            f"✅ 撤退任务完成: job_id={job_id}, user={user_name}, "
            f"战斗已标记为失败。请调用 /api/dungeon/exit/v1/ 返回家园。"
        )

    except Exception as e:
        logger.error(f"❌ 撤退任务失败: job_id={job_id}, user={user_name}, error={e}")
        save_task_error(job_id, str(e))
        raise


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_draw_cards_task(
    context: JobContext,
    user_name: str,
) -> None:
    """后台执行抽卡任务"""
    job_id = str(context.job.id)
    try:

        logger.info(f"🚀 抽卡任务开始: job_id={job_id}, user={user_name}")

        game_server = get_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证游戏实例类型
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证当前副本房间是否为战斗房间
            if not rpg_game.is_current_room_dungeon_combat:
                raise ValueError("当前副本房间不是战斗房间")

            # 验证战斗状态
            if not rpg_game.current_dungeon_combat_room.combat.is_ongoing:
                raise ValueError("战斗未在进行中")

            # 推进战斗流程处理抽牌
            await rpg_game._dungeon_combat_room_pipeline.process()

            # 存储抽牌后的世界状态，便于调试和回放
            store_game(rpg_game)

        logger.info(f"✅ 抽卡任务完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(f"❌ 抽卡任务失败: job_id={job_id}, user={user_name}, error={e}")
        save_task_error(job_id, str(e))
        raise


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_play_cards_task(
    context: JobContext,
    user_name: str,
) -> None:
    """后台执行出牌任务"""
    job_id = str(context.job.id)
    try:
        logger.info(f"🚀 出牌任务开始: job_id={job_id}, user={user_name}")

        game_server = get_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证游戏实例类型
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证当前副本房间是否为战斗房间
            if not rpg_game.is_current_room_dungeon_combat:
                raise ValueError("当前副本房间不是战斗房间")

            # 验证战斗状态
            if not rpg_game.current_dungeon_combat_room.combat.is_ongoing:
                raise ValueError("战斗未在进行中")

            # 推进战斗流程处理出牌
            await rpg_game._dungeon_combat_room_pipeline.process()

            # 存储出牌后的世界状态，便于调试和回放
            store_game(rpg_game)

        logger.info(f"✅ 出牌任务完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(f"❌ 出牌任务失败: job_id={job_id}, user={user_name}, error={e}")
        save_task_error(job_id, str(e))
        raise


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_pass_turn_task(
    context: JobContext,
    user_name: str,
) -> None:
    """后台执行过牌任务"""
    job_id = str(context.job.id)
    try:
        logger.info(f"🚀 过牌任务开始: job_id={job_id}, user={user_name}")

        game_server = get_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证游戏实例类型
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证当前副本房间是否为战斗房间
            if not rpg_game.is_current_room_dungeon_combat:
                raise ValueError("当前副本房间不是战斗房间")

            # 验证战斗状态
            if not rpg_game.current_dungeon_combat_room.combat.is_ongoing:
                raise ValueError("战斗未在进行中")

            # 处理战斗流水线
            await rpg_game._dungeon_combat_room_pipeline.process()

            # 存储过牌后的世界状态，便于调试和回放
            store_game(rpg_game)

        logger.info(f"✅ 过牌任务完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(f"❌ 过牌任务失败: job_id={job_id}, user={user_name}, error={e}")
        save_task_error(job_id, str(e))
        raise


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_use_consumable_task(
    context: JobContext,
    user_name: str,
) -> None:
    """后台执行使用消耗品任务"""
    job_id = str(context.job.id)
    try:

        logger.info(f"🚀 使用消耗品任务开始: job_id={job_id}, user={user_name}")

        game_server = get_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证游戏实例类型
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证当前副本房间是否为战斗房间
            if not rpg_game.is_current_room_dungeon_combat:
                raise ValueError("当前副本房间不是战斗房间")

            # 验证战斗状态
            if not rpg_game.current_dungeon_combat_room.combat.is_ongoing:
                raise ValueError("战斗未在进行中")

            # 处理战斗流水线
            await rpg_game._dungeon_combat_room_pipeline.process()

            # 存储使用消耗品后的世界状态，便于调试和回放
            store_game(rpg_game)

        logger.info(f"✅ 使用消耗品任务完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 使用消耗品任务失败: job_id={job_id}, user={user_name}, error={e}"
        )
        save_task_error(job_id, str(e))
        raise


###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_equip_gear_task(
    context: JobContext,
    user_name: str,
) -> None:
    """后台执行使用装备任务"""
    job_id = str(context.job.id)
    try:

        logger.info(f"🚀 使用装备任务开始: job_id={job_id}, user={user_name}")

        game_server = get_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证游戏实例类型
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证当前副本房间是否为战斗房间
            if not rpg_game.is_current_room_dungeon_combat:
                raise ValueError("当前副本房间不是战斗房间")

            # 验证战斗状态
            if not rpg_game.current_dungeon_combat_room.combat.is_ongoing:
                raise ValueError("战斗未在进行中")

            # 处理战斗流水线
            await rpg_game._dungeon_combat_room_pipeline.process()

            # 存储使用装备后的世界状态，便于调试和回放
            store_game(rpg_game)

        logger.info(f"✅ 使用装备任务完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 使用装备任务失败: job_id={job_id}, user={user_name}, error={e}"
        )
        save_task_error(job_id, str(e))
        raise


###################################################################################################################################################################
###################################################################################################################################################################
