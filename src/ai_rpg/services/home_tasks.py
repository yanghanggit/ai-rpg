"""
家园任务模块
"""

from typing import Awaitable, Callable, List, Tuple

from procrastinate import JobContext
from fastapi import HTTPException, status
from loguru import logger
from ..game.dbg_game import DBGGame
from ..game.dbg_store import store_game_async
from ..game.game_server import GameServer
from ..pgsql import procrastinate_app, save_task_error
from .game_server_runtime import get_runtime_game_server
from .home_actions import (
    activate_craft_consumable,
    activate_craft_costume_item,
    activate_craft_gear_item,
    activate_generate_dungeon,
    activate_plan_action,
    activate_remove_costume,
    activate_speak_action,
    activate_switch_stage,
    activate_wear_costume,
)


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
async def _validate_player_at_home(
    user_name: str,
    game_server: GameServer,
) -> DBGGame:
    """
    验证玩家是否在家园状态
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
    if current_room.game is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="没有游戏，请先登录",
        )

    # 判断游戏状态，不是Home状态不可以推进。
    if not current_room.game.is_player_in_home_stage:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前不在家园状态，不能进行家园操作",
        )

    # 返回游戏实例
    return current_room.game


###################################################################################################################################################################
async def _run_home_task(
    context: JobContext,
    user_name: str,
    activate: Callable[[DBGGame], Tuple[bool, str]],
    run_pipeline: Callable[[DBGGame], Awaitable[None]],
) -> None:
    """在房间锁内激活动作并推进对应 pipeline，最后落盘。"""
    job_id = context.job.id
    assert job_id is not None, "运行中的任务必然有 job id"
    try:
        logger.info(f"🚀 home 任务开始: job_id={job_id}, user={user_name}")

        game_server = get_runtime_game_server()

        async with game_server.acquire(user_name):

            rpg_game = await _validate_player_at_home(user_name, game_server)

            # 激活动作（在锁内、pipeline 执行前完成）
            success, message = activate(rpg_game)
            if not success:
                raise ValueError(message)

            # 执行 pipeline，可能比较耗时
            await run_pipeline(rpg_game)

            # 存档当前世界状态，便于调试和回放
            await store_game_async(rpg_game)

        logger.info(f"✅ home 任务完成: job_id={job_id}, user={user_name}")

    except Exception as e:
        logger.error(f"❌ home 任务失败: job_id={job_id}, user={user_name}, error={e}")
        save_task_error(job_id, str(e))
        raise


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_home_speak_task(
    context: JobContext,
    user_name: str,
    target: str,
    content: str,
) -> None:
    """执行家园对话任务"""
    await _run_home_task(
        context,
        user_name,
        lambda game: activate_speak_action(game, target, content),
        lambda game: game._home_pipeline.process(),
    )


###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_home_switch_stage_task(
    context: JobContext,
    user_name: str,
    stage_name: str,
) -> None:
    """执行家园场景切换任务"""
    await _run_home_task(
        context,
        user_name,
        lambda game: activate_switch_stage(game, stage_name),
        lambda game: game._home_pipeline.process(),
    )


###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_home_advance_task(
    context: JobContext,
    user_name: str,
    actors: List[str],
) -> None:
    """执行家园推进任务"""
    await _run_home_task(
        context,
        user_name,
        lambda game: activate_plan_action(game, actors),
        lambda game: game._home_pipeline.process(),
    )


###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_home_wear_costume_task(
    context: JobContext,
    user_name: str,
    item_name: str,
    target_name: str,
) -> None:
    """执行穿装任务"""
    await _run_home_task(
        context,
        user_name,
        lambda game: activate_wear_costume(game, item_name, target_name),
        lambda game: game._home_pipeline.process(),
    )


###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_home_remove_costume_task(
    context: JobContext,
    user_name: str,
    target_name: str,
) -> None:
    """执行脱装任务"""
    await _run_home_task(
        context,
        user_name,
        lambda game: activate_remove_costume(game, target_name),
        lambda game: game._home_pipeline.process(),
    )


###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_dungeon_generate_pipeline_task(
    context: JobContext,
    user_name: str,
) -> None:
    """执行 dungeon generate pipeline 任务"""
    await _run_home_task(
        context,
        user_name,
        lambda game: activate_generate_dungeon(game),
        lambda game: game._dungeon_generate_pipeline.process(),
    )


###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_home_craft_consumable_task(
    context: JobContext,
    user_name: str,
    materials: List[str],
) -> None:
    """执行消耗品合成任务"""
    await _run_home_task(
        context,
        user_name,
        lambda game: activate_craft_consumable(game, materials),
        lambda game: game._home_craft_pipeline.process(),
    )


###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_home_craft_gear_task(
    context: JobContext,
    user_name: str,
    materials: List[str],
) -> None:
    """执行装备合成任务"""
    await _run_home_task(
        context,
        user_name,
        lambda game: activate_craft_gear_item(game, materials),
        lambda game: game._home_craft_pipeline.process(),
    )


###################################################################################################################################################################
@procrastinate_app.task(queue="game", pass_context=True)
async def execute_home_craft_costume_task(
    context: JobContext,
    user_name: str,
    materials: List[str],
) -> None:
    """执行时装合成任务"""
    await _run_home_task(
        context,
        user_name,
        lambda game: activate_craft_costume_item(game, materials),
        lambda game: game._home_craft_pipeline.process(),
    )


###################################################################################################################################################################
###################################################################################################################################################################
###################################################################################################################################################################
