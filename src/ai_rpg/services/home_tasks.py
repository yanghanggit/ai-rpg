"""
家园后台任务模块

从 home_gameplay.py 抽取的后台 task 函数及验证工具函数，供端点文件 import 使用。
"""

from datetime import datetime
from fastapi import HTTPException, status
from loguru import logger
from ..game.tcg_game import TCGGame
from ..game.world_store import archive_world
from ..game.game_server import GameServer
from ..models import TaskStatus


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _validate_player_at_home(
    user_name: str,
    game_server: GameServer,
) -> TCGGame:
    """
    验证玩家是否在家园状态

    Args:
        user_name: 用户名
        game_server: 游戏服务器实例

    Returns:
        TCGGame: 验证通过的 TCG 游戏实例

    Raises:
        HTTPException(404): 房间或游戏实例不存在
        HTTPException(400): 玩家不在家园状态
    """

    # 检查房间是否存在
    if not game_server.has_room(user_name):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有登录，请先登录",
        )

    # 获取房间实例并检查游戏是否存在
    current_room = game_server.get_room(user_name)
    assert current_room is not None, "_validate_player_at_home: room instance is None"
    if current_room._tcg_game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有游戏，请先登录",
        )

    # 判断游戏状态，不是Home状态不可以推进。
    if not current_room._tcg_game.is_player_in_home_stage:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前不在家园状态，不能进行家园操作",
        )

    # 返回游戏实例
    return current_room._tcg_game


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _execute_dungeon_generate_pipeline_task(
    task_id: str,
    user_name: str,
    game_server: GameServer,
) -> None:
    """后台执行 dungeon generate pipeline 任务

    在后台异步执行 dungeon_generate_pipeline 并更新任务状态。
    使用房间锁保证同一玩家不会并发执行。

    Args:
        task_id: 任务唯一标识符
        user_name: 用户名
        game_server: 游戏服务器实例
    """
    try:
        logger.info(
            f"🚀 dungeon generate pipeline 任务开始: task_id={task_id}, user={user_name}"
        )

        current_room = game_server.get_room(user_name)
        if current_room is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            rpg_game = await _validate_player_at_home(user_name, game_server)

            # 执行地下城生成流程（包含文本生成和图片生成），该流程可能比较耗时
            await rpg_game._dungeon_generate_pipeline.process()

            # 存档当前世界状态，便于调试和回放
            archive_world(rpg_game._world, rpg_game._player_session)

        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.COMPLETED
            task_record.end_time = datetime.now().isoformat()

        logger.info(
            f"✅ dungeon generate pipeline 任务完成: task_id={task_id}, user={user_name}"
        )

    except Exception as e:
        logger.error(
            f"❌ dungeon generate pipeline 任务失败: task_id={task_id}, user={user_name}, error={e}"
        )
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _execute_home_pipeline_task(
    task_id: str,
    user_name: str,
    game_server: GameServer,
) -> None:
    """后台执行 home pipeline 任务

    在后台异步执行 home pipeline 并更新任务状态。
    使用房间锁保证同一玩家不会并发执行。

    Args:
        task_id: 任务唯一标识符
        user_name: 用户名
        game_server: 游戏服务器实例
    """
    try:
        logger.info(f"🚀 home pipeline 任务开始: task_id={task_id}, user={user_name}")

        current_room = game_server.get_room(user_name)
        if current_room is None:
            raise ValueError(f"游戏实例不存在: user={user_name}")

        async with current_room._lock:

            rpg_game = await _validate_player_at_home(user_name, game_server)

            # 执行 home pipeline，包含行动计划执行、状态更新、会话消息生成等逻辑，可能比较耗时
            await rpg_game._home_pipeline.process()

            # 存档当前世界状态，便于调试和回放
            archive_world(rpg_game._world, rpg_game._player_session)

        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.COMPLETED
            task_record.end_time = datetime.now().isoformat()

        logger.info(f"✅ home pipeline 任务完成: task_id={task_id}, user={user_name}")

    except Exception as e:
        logger.error(
            f"❌ home pipeline 任务失败: task_id={task_id}, user={user_name}, error={e}"
        )
        task_record = game_server.get_task(task_id)
        if task_record is not None:
            task_record.status = TaskStatus.FAILED
            task_record.error = str(e)
            task_record.end_time = datetime.now().isoformat()


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
