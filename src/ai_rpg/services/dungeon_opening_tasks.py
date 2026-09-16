"""
副本开场房间任务模块
"""

from procrastinate import JobContext
from loguru import logger
from ..game.dbg_game import DBGGame
from ..game.dbg_store import store_game_async
from ..pgsql import procrastinate_app, save_task_error
from .game_server_dependencies import get_game_server
from .dungeon_opening_actions import (
    activate_generate_spoils,
    activate_pick_spoils_card,
)


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_opening_room_init_task(
    context: JobContext,
    user_name: str,
) -> None:
    """执行副本开场房间初始化任务（叙事 + 牌库初始化，无战斗）"""
    job_id = context.job.id
    assert job_id is not None, "运行中的任务必然有 job id"
    try:

        logger.info(f"🚀 开场房间初始化任务开始: job_id={job_id}, user={user_name}")

        game_server = get_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证游戏实例类型
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证当前副本房间是否为开场房间
            if not rpg_game.is_current_room_dungeon_opening:
                raise ValueError("当前副本房间不是开场房间")

            # 状态守护：开场房间已初始化则拒绝重复初始化
            if rpg_game.current_dungeon_opening_room.initialized:
                raise ValueError("开场房间已初始化")

            # 推进开场房间流程（叙事 + 牌库初始化，无战斗）
            await rpg_game._dungeon_opening_room_pipeline.process()

            # 存储开场房间初始化后的世界状态，便于调试和回放
            await store_game_async(rpg_game)

        logger.info(f"✅ 开场房间初始化任务完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 开场房间初始化任务失败: job_id={job_id}, user={user_name}, error={e}"
        )
        save_task_error(job_id, str(e))
        raise


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_generate_spoils_task(
    context: JobContext,
    user_name: str,
) -> None:
    """执行奖励生成任务（外部触发 GenerateSpoilsAction 后推动开场管道处理）"""
    job_id = context.job.id
    assert job_id is not None, "运行中的任务必然有 job id"
    try:

        logger.info(f"🚀 奖励生成任务开始: job_id={job_id}, user={user_name}")

        game_server = get_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证游戏实例类型
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证当前副本房间是否为开场房间
            if not rpg_game.is_current_room_dungeon_opening:
                raise ValueError("当前副本房间不是开场房间")

            # 外部显式激活奖励生成动作（内部含开场已初始化 + 幂等守卫）
            success, message = activate_generate_spoils(rpg_game)
            if not success:
                raise ValueError(f"奖励生成失败: {message}")

            # 推进开场房间流程，让 GenerateSpoilsActionSystem 响应并生成奖励
            await rpg_game._dungeon_opening_room_pipeline.process()

            # 存储奖励生成后的世界状态，便于调试和回放
            await store_game_async(rpg_game)

        logger.info(f"✅ 奖励生成任务完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 奖励生成任务失败: job_id={job_id}, user={user_name}, error={e}"
        )
        save_task_error(job_id, str(e))
        raise


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_pick_spoils_card_task(
    context: JobContext,
    user_name: str,
    actor_name: str,
    card_name: str,
) -> None:
    """执行从 Spoils 领取一张卡牌任务（外部触发 PickSpoilsAction 后推动开场管道处理）"""
    job_id = context.job.id
    assert job_id is not None, "运行中的任务必然有 job id"
    try:

        logger.info(
            f"🚀 领卡任务开始: job_id={job_id}, user={user_name}, "
            f"actor={actor_name}, card={card_name}"
        )

        game_server = get_game_server()

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证游戏实例类型
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证当前副本房间是否为开场房间
            if not rpg_game.is_current_room_dungeon_opening:
                raise ValueError("当前副本房间不是开场房间")

            # 外部显式激活领卡动作（内部含初始化 + Spoils 存在 + 卡牌检索守卫）
            success, message = activate_pick_spoils_card(
                rpg_game, actor_name, card_name
            )
            if not success:
                raise ValueError(f"从 Spoils 领卡失败: {message}")

            # 推进开场房间流程，让 PickSpoilsActionSystem 响应并把选中卡加入牌库
            await rpg_game._dungeon_opening_room_pipeline.process()

            # 存储领卡后的世界状态，便于调试和回放
            await store_game_async(rpg_game)

        logger.info(f"✅ 领卡任务完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(f"❌ 领卡任务失败: job_id={job_id}, user={user_name}, error={e}")
        save_task_error(job_id, str(e))
        raise


###################################################################################################################################################################
###################################################################################################################################################################
