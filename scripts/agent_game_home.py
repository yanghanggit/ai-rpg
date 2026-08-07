"""家园模式动作。

包含所有在家园模式（HomeComponent 场景）下执行的游戏动作函数。
"""

import os
import sys

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)
# 将 scripts 目录添加到模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from typing import Dict, List
from ai_rpg.models import PlayerSession
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import World
from ai_rpg.game import archive_world
from ai_rpg.services.home_actions import (
    activate_plan_action,
    activate_speak_action,
    activate_switch_stage,
    activate_generate_dungeon,
)
from ai_rpg.services.dungeon_lifecycle import (
    setup_dungeon,
    enter_dungeon,
)
from pathlib import Path
from agent_game_core import restore_game


###############################################################################
async def advance_game(
    world: World,
    player_session: PlayerSession,
    actor_names: List[str],
    save_dir: Path,
) -> DBGGame:
    """推进一轮家园剧情，为指定角色激活行动计划并归档。"""
    terminal_game = await restore_game(world, player_session)

    success, error_detail = activate_plan_action(terminal_game, actor_names)
    if not success:
        logger.debug(f"激活行动计划失败: {error_detail}")

    await terminal_game._home_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def stages_game(
    world: World,
    player_session: PlayerSession,
) -> Dict[str, List[str]]:
    """返回当前各场景内角色名单（只读，不归档）。"""
    terminal_game = await restore_game(world, player_session)
    return terminal_game.get_actors_by_stage_as_names()


###############################################################################
async def speak_game(
    world: World,
    player_session: PlayerSession,
    target: str,
    content: str,
    save_dir: Path,
) -> DBGGame:
    """玩家向指定 NPC 说话并归档。"""
    terminal_game = await restore_game(world, player_session)

    success, _ = activate_speak_action(
        dbg_game=terminal_game,
        target=target,
        content=content,
    )
    if not success:
        logger.error(f"激活对话行动失败: target={target}")
        return terminal_game

    await terminal_game._home_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def switch_stage_game(
    world: World,
    player_session: PlayerSession,
    stage_name: str,
    save_dir: Path,
) -> DBGGame:
    """玩家切换到指定场景并归档。"""
    terminal_game = await restore_game(world, player_session)

    success, _ = activate_switch_stage(
        dbg_game=terminal_game,
        stage_name=stage_name,
    )
    if not success:
        logger.error(f"激活场景切换失败: stage={stage_name}")
        return terminal_game

    await terminal_game._home_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def enter_dungeon_game(
    world: World,
    player_session: PlayerSession,
    dungeon_name: str,
    save_dir: Path,
) -> DBGGame:
    """进入指定副本第一关并归档。需处于家园模式。"""
    terminal_game = await restore_game(world, player_session)

    success, error_detail = setup_dungeon(terminal_game, dungeon_name)
    if not success:
        logger.error(f"副本实体创建失败: {error_detail}")
        return terminal_game

    success, error_detail = enter_dungeon(terminal_game, terminal_game.current_dungeon)
    if not success:
        logger.error(f"进入副本第一关失败: {error_detail}")
        return terminal_game

    # assert (
    #     terminal_game.current_combat_room.combat.state != CombatState.NONE
    # ), "没有战斗可以进行"

    # 进入副本后直接执行一次 combat_pipeline，完成战斗的初始推理与叙事生成（场景描述、角色状态效果、第一回合及行动顺序）
    await terminal_game._combat_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def generate_dungeon_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> DBGGame:
    """激活 LLM 动态生成副本流水线并归档。需处于家园模式。"""
    terminal_game = await restore_game(world, player_session)

    success, error_detail = activate_generate_dungeon(terminal_game)
    if not success:
        logger.error(f"激活副本创建失败: {error_detail}")
        return terminal_game

    await terminal_game._dungeon_generate_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game
