"""
副本入口房间后台任务模块
"""

from datetime import datetime
from loguru import logger
from ..game.dbg_game import DBGGame
from ..game.dbg_store import store_game
from ..game.game_server import GameServer
from ..models import TaskStatus


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def execute_entry_room_init_task(
    task_id: str,
    user_name: str,
    game_server: GameServer,
) -> None:
    """后台执行副本入口房间初始化任务（叙事 + 牌库生成，无战斗）"""
    try:

        logger.info(f"🚀 入口房间初始化任务开始: task_id={task_id}, user={user_name}")

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证游戏实例类型
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 验证当前副本房间是否为入口房间
            if not rpg_game.is_current_room_dungeon_entry:
                raise ValueError("当前副本房间不是入口房间")

            # 推进入口房间流程（叙事 + 牌库生成，无战斗）
            await rpg_game._dungeon_entry_room_pipeline.process()

            # 存储入口房间初始化后的世界状态，便于调试和回放
            store_game(rpg_game)

        # 保存结果
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.COMPLETED
            task_record.end_time = datetime.now().isoformat()

        logger.info(f"✅ 入口房间初始化任务完成: task_id={task_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 入口房间初始化任务失败: task_id={task_id}, user={user_name}, error={e}"
        )

        # 保存失败结果
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


###################################################################################################################################################################
###################################################################################################################################################################
