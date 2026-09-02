"""
副本开场房间后台任务模块
"""

from datetime import datetime
from loguru import logger
from ..game.dbg_game import DBGGame
from ..game.dbg_store import store_game
from ..game.game_server import GameServer
from ..models import TaskStatus
from .dungeon_opening_actions import activate_generate_card_pool


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def execute_opening_room_init_task(
    task_id: str,
    user_name: str,
    game_server: GameServer,
) -> None:
    """后台执行副本开场房间初始化任务（叙事 + 牌库初始化，无战斗）"""
    try:

        logger.info(f"🚀 开场房间初始化任务开始: task_id={task_id}, user={user_name}")

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
            store_game(rpg_game)

        # 保存结果
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.COMPLETED
            task_record.end_time = datetime.now().isoformat()

        logger.info(f"✅ 开场房间初始化任务完成: task_id={task_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 开场房间初始化任务失败: task_id={task_id}, user={user_name}, error={e}"
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
async def execute_generate_card_pool_task(
    task_id: str,
    user_name: str,
    game_server: GameServer,
) -> None:
    """后台执行卡池生成任务（外部触发 GenerateCardPoolAction 后推动开场管道处理）"""
    try:

        logger.info(f"🚀 卡池生成任务开始: task_id={task_id}, user={user_name}")

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

            # 外部显式激活卡池生成动作（内部含开场已初始化 + 幂等守卫）
            success, message = activate_generate_card_pool(rpg_game)
            if not success:
                raise ValueError(f"卡池生成失败: {message}")

            # 推进开场房间流程，让 GenerateCardPoolActionSystem 响应并生成卡池
            await rpg_game._dungeon_opening_room_pipeline.process()

            # 存储卡池生成后的世界状态，便于调试和回放
            store_game(rpg_game)

        # 保存结果
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.COMPLETED
            task_record.end_time = datetime.now().isoformat()

        logger.info(f"✅ 卡池生成任务完成: task_id={task_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 卡池生成任务失败: task_id={task_id}, user={user_name}, error={e}"
        )

        # 保存失败结果
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


###################################################################################################################################################################
###################################################################################################################################################################
