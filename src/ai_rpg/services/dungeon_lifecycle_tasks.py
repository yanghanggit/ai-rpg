"""副本生命周期后台任务模块"""

from datetime import datetime
from loguru import logger
from ..game.dbg_game import DBGGame
from ..game.dbg_store import store_game
from ..game.game_server import GameServer
from ..models import TaskStatus
from .dungeon_archive_action import (
    archive_dungeon,
)
from .dungeon_exit_action import (
    exit_dungeon,
)
from .dungeon_teardown_action import (
    teardown_dungeon,
)


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def execute_exit_dungeon_task(
    task_id: str,
    user_name: str,
    game_server: GameServer,
) -> None:
    """后台执行退出副本任务（返回家园 + 副本本体归档 + 实体销毁）。"""
    try:

        logger.info(f"🚀 退出副本任务开始: task_id={task_id}, user={user_name}")

        # 获取房间并用每玩家锁避免并发状态竞争
        current_room = game_server.get_room(user_name)
        if current_room is None or current_room._dbg_game is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            # 验证游戏实例类型
            rpg_game = current_room._dbg_game
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 退出副本并返回家园（同步，内部自带状态守卫）
            success, msg = exit_dungeon(rpg_game, rpg_game._world.dungeon)
            if not success:
                raise ValueError(f"退出副本失败: {msg}")

            # 副本本体归档：以拟人化副本视角总结本次所有场景/角色的记忆
            # （异步 LLM，best-effort，失败不阻断退出，且不写入任何状态）
            await archive_dungeon(rpg_game, rpg_game._world.dungeon)

            # 销毁副本实体并重置副本数据（同步）
            teardown_dungeon(rpg_game, rpg_game._world.dungeon)

            # 存储退出后的世界状态，便于调试和回放
            store_game(rpg_game)

        # 保存结果
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.COMPLETED
            task_record.end_time = datetime.now().isoformat()

        logger.info(f"✅ 退出副本任务完成: task_id={task_id}, user={user_name}")

    except Exception as e:

        # 保存失败结果
        logger.error(
            f"❌ 退出副本任务失败: task_id={task_id}, user={user_name}, error={e}"
        )
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
