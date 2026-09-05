"""副本生命周期后台任务模块"""

from procrastinate import JobContext
from loguru import logger
from ..game.dbg_game import DBGGame
from ..game.dbg_store import store_game
from ..pgsql import procrastinate_app, save_task_error
from .game_server_dependencies import get_game_server
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
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_exit_dungeon_task(
    context: JobContext,
    user_name: str,
) -> None:
    """后台执行退出副本任务（返回家园 + 副本导演归档 + 实体销毁）。"""
    job_id = str(context.job.id)
    try:

        logger.info(f"🚀 退出副本任务开始: job_id={job_id}, user={user_name}")

        game_server = get_game_server()

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

            # 副本导演归档：基于其已积累的记忆总结本次副本，并重置该记忆
            # （异步 LLM，best-effort，失败不阻断退出）
            await archive_dungeon(rpg_game, rpg_game._world.dungeon)

            # 销毁副本实体并重置副本数据（同步）
            teardown_dungeon(rpg_game, rpg_game._world.dungeon)

            # 存储退出后的世界状态，便于调试和回放
            store_game(rpg_game)

        logger.info(f"✅ 退出副本任务完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 退出副本任务失败: job_id={job_id}, user={user_name}, error={e}"
        )
        save_task_error(job_id, str(e))
        raise


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
