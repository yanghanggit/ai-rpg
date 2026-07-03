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
from ai_rpg.models import PlayerSession
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import CombatState, World
from ai_rpg.game import archive_world
from ai_rpg.services.home_actions import (
    activate_stage_plan,
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
    save_dir: Path,
) -> DBGGame:
    """从存档复位，执行一轮家园推进（等同于终端命令 /ad），并归档新状态。

    调用 activate_stage_plan 为玩家当前场景内所有 NPC 激活行动计划，
    然后驱动 home_pipeline.process() 完成本轮推理与叙事生成。

    前置条件：玩家必须处于家园模式（is_player_in_home_stage）。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        save_dir: 新存档写入目录（由命令层根据时间戳预先构造）。

    Returns:
        执行完毕后的 DBGGame 实例（已归档）。
    """
    terminal_game = await restore_game(world, player_session)

    success, error_detail = activate_stage_plan(terminal_game)
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
async def speak_game(
    world: World,
    player_session: PlayerSession,
    target: str,
    content: str,
    save_dir: Path,
) -> DBGGame:
    """从存档复位，玩家向指定 NPC 说话（等同于终端命令 /speak），并归档新状态。

    调用 activate_speak_action 添加玩家说话行动，然后驱动 home_pipeline.process()。
    本次 pipeline 中 NPC 不进行主动推理，仅响应玩家的对话。

    前置条件：玩家必须处于家园模式，且 target 角色须与玩家在同一场景。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        target: 对话目标角色全名（如 "术士.云音"）。
        content: 玩家说话内容。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 DBGGame 实例（已归档）；激活失败时提前返回未归档实例。
    """
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
    """从存档复位，玩家切换到指定场景（等同于终端命令 /switch_stage），并归档新状态。

    调用 activate_switch_stage 添加玩家场景转换行动，然后驱动 home_pipeline.process()。
    本次 pipeline 中 NPC 不进行主动推理，仅响应场景切换。

    前置条件：玩家必须处于家园模式，且 stage_name 须为合法的 HomeComponent 场景。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        stage_name: 目标场景全名（如 "场景.村中议事堂"）。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 DBGGame 实例（已归档）；激活失败时提前返回未归档实例。
    """
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
    """从存档复位，启动地下城第一关（等同于终端命令 /ed），并归档新状态。

    调用 setup_dungeon 从文件加载地下城、赋值并创建地下城实体，再调用 enter_dungeon_first_stage 将玩家和队友传送至第一关场景，
    创建首个 CombatSequence，然后驱动 combat_pipeline.process() 完成战斗初始化
    （场景描述生成、各角色初始状态效果生成、创建第一回合及行动顺序）。

    执行后游戏进入【地下城模式】，后续应使用 draw-cards → play-cards 流程。

    前置条件：玩家必须处于家园模式。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        dungeon_name: 地下城名称（对应 DUNGEONS_DIR 下的 JSON 文件名）。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 DBGGame 实例（已归档）；失败时提前返回未归档实例。
    """
    terminal_game = await restore_game(world, player_session)

    success, error_detail = setup_dungeon(terminal_game, dungeon_name)
    if not success:
        logger.error(f"地下城实体创建失败: {error_detail}")
        return terminal_game

    success, error_detail = enter_dungeon(terminal_game, terminal_game.current_dungeon)
    if not success:
        logger.error(f"进入地下城第一关失败: {error_detail}")
        return terminal_game

    assert (
        terminal_game.current_dungeon.current_combat_room is not None
    ), "当前尚未进入任何战斗房间"
    assert (
        terminal_game.current_dungeon.current_combat_room.combat.state
        != CombatState.NONE
    ), "没有战斗可以进行"

    # 进入地下城后直接执行一次 combat_pipeline，完成战斗的初始推理与叙事生成（场景描述、角色状态效果、第一回合及行动顺序）
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
    """从存档复位，激活地下城生成动作并执行 dungeon_generate_pipeline，并归档新状态。

    调用 activate_generate_dungeon 为玩家实体添加 GenerateDungeonAction，
    然后驱动 _dungeon_generate_pipeline.process() 触发 GenerateDungeonActionSystem
    执行地下城文本数据生成流程（Steps 1-4），成功后自动触发 IllustrateDungeonActionSystem。
    动作组件由 ActionCleanupSystem 在 pipeline 末端自动清除。

    前置条件：玩家必须处于家园模式（is_player_in_home_stage）。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 DBGGame 实例（已归档）；激活失败时提前返回未归档实例。
    """
    terminal_game = await restore_game(world, player_session)

    success, error_detail = activate_generate_dungeon(terminal_game)
    if not success:
        logger.error(f"激活地下城创建失败: {error_detail}")
        return terminal_game

    await terminal_game._dungeon_generate_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game
