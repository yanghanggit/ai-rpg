"""
上下文压缩任务模块
"""

from loguru import logger
from procrastinate import JobContext

from ..game.dbg_game import DBGGame
from ..game.dbg_store import store_game_async
from ..pgsql import procrastinate_app, save_task_error
from .compact_action import activate_compact_context
from .game_server_runtime import get_runtime_game_server


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_compact_context_task(
    context: JobContext,
    user_name: str,
    target_name: str,
) -> None:
    """执行手动上下文压缩任务"""
    job_id = context.job.id
    assert job_id is not None, "运行中的任务必然有 job id"
    try:
        logger.info(f"🚀 上下文压缩任务开始: job_id={job_id}, user={user_name}")

        game_server = get_runtime_game_server()

        async with game_server.acquire(user_name) as room:

            rpg_game = room.game
            if rpg_game is None:
                raise ValueError(f"游戏实例不存在: user={user_name}")
            assert isinstance(rpg_game, DBGGame), "Invalid game type"

            # 激活手动压缩动作
            success, message = activate_compact_context(rpg_game, target_name)
            if not success:
                raise ValueError(message)

            # 执行 compact pipeline，仅处理手动触发的 CompactContextAction
            await rpg_game._compact_pipeline.process()

            # 存档压缩后的世界状态，便于调试和回放
            await store_game_async(rpg_game)

        logger.info(f"✅ 上下文压缩任务完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ 上下文压缩任务失败: job_id={job_id}, user={user_name}, error={e}"
        )
        save_task_error(job_id, str(e))
        raise
