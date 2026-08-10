"""副本生命周期动作。

包含副本模式下的关卡推进与退出等通用生命周期函数（不依赖具体房间类型）。
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
from ai_rpg.models import World
from ai_rpg.game.dbg_store import store_game
from ai_rpg.services.dungeon_advance_action import (
    advance_dungeon,
)
from ai_rpg.services.dungeon_exit_action import (
    exit_dungeon,
)
from ai_rpg.services.dungeon_enter_action import (
    enter_dungeon,
)
from ai_rpg.services.dungeon_setup_action import (
    setup_dungeon,
    teardown_dungeon,
)
from pathlib import Path
from agent_game_core import restore_game


###############################################################################
async def next_dungeon_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> DBGGame:
    """进入副本下一关并归档。需前一关已胜利（或为非战斗房间）且存在下一关。"""

    # 创建 DBGGame 实例并从快照恢复游戏状态
    terminal_game = await restore_game(world, player_session)

    # 若当前为战斗房间，需确认战斗已结束且胜利
    if terminal_game.is_current_room_dungeon_combat:
        if not terminal_game.current_dungeon_combat_room.combat.is_post_combat:
            logger.error("next-dungeon 只能在战斗结束后使用")
            return terminal_game

        if terminal_game.current_dungeon_combat_room.combat.is_lost:
            logger.info("英雄失败，应该返回营地")
            return terminal_game

        if not terminal_game.current_dungeon_combat_room.combat.is_won:
            assert False, "不可能出现的情况！"

    elif terminal_game.is_current_room_dungeon_entry:
        logger.info("当前为非战斗房间，直接进入下一关")

    # 获取下一房间索引和房间实例，确保存在下一房间，否则无法推进副本
    next_room_index = terminal_game.current_dungeon.current_room_index + 1
    next_room = terminal_game.current_dungeon.get_room(next_room_index)
    if next_room is None:
        logger.error("副本前进失败，没有更多房间")
        return terminal_game

    # 推进副本到下一房间，更新当前房间索引和状态
    success, msg = advance_dungeon(terminal_game, terminal_game.current_dungeon)
    if not success:
        logger.error(f"advance_dungeon 失败: {msg}")
        return terminal_game

    # 进入下一关卡后，驱动战斗流水线处理新关卡的初始化，包括场景描述、初始状态效果、创建新回合等
    await terminal_game._dungeon_combat_room_pipeline.process()

    # 最后归档
    store_game(terminal_game, save_dir)

    # 返回更新后的游戏实例
    return terminal_game


###############################################################################
async def enter_dungeon_game(
    world: World,
    player_session: PlayerSession,
    dungeon_name: str,
    save_dir: Path,
) -> DBGGame:
    """进入指定副本第一关并归档。需处于家园模式。"""

    # 创建 DBGGame 实例并从快照恢复游戏状态
    terminal_game = await restore_game(world, player_session)

    # 创建副本实体
    success, error_detail = setup_dungeon(terminal_game, dungeon_name)
    if not success:
        logger.error(f"副本实体创建失败: {error_detail}")
        return terminal_game

    # 进入副本第一关
    success, error_detail = enter_dungeon(terminal_game, terminal_game.current_dungeon)
    if not success:
        logger.error(f"进入副本第一关失败: {error_detail}")
        return terminal_game

    # 若是战斗房间则初始化战斗；入口房间运行入口管道（叙事 + 牌库生成）
    if terminal_game.is_current_room_dungeon_combat:
        await terminal_game._dungeon_combat_room_pipeline.process()
    elif terminal_game.is_current_room_dungeon_entry:
        await terminal_game._dungeon_entry_room_pipeline.process()
    else:
        assert (
            terminal_game.current_dungeon.current_room is not None
        ), f"当前房间为 {terminal_game.current_dungeon.current_room!r}，无法处理"
        logger.error(
            f"未知房间类型 {terminal_game.current_dungeon.current_room.type!r}，无法处理"
        )
        return terminal_game

    # 最后归档
    store_game(terminal_game, save_dir)

    # 返回更新后的游戏实例
    return terminal_game


###############################################################################
async def exit_dungeon_and_return_home_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> DBGGame:
    """结束副本返回家园并归档。需战斗已结束（无论胜负），非战斗房间可直接退出。"""

    # 创建 DBGGame 实例并从快照恢复游戏状态
    terminal_game = await restore_game(world, player_session)

    # 若当前为战斗房间，状态守卫：只能在战斗结束后使用
    if terminal_game.is_current_room_dungeon_combat:
        if not terminal_game.current_dungeon_combat_room.combat.is_post_combat:
            logger.error("exit-dungeon 只能在战斗结束后使用")
            return terminal_game

    elif terminal_game.is_current_room_dungeon_entry:
        logger.info("当前为非战斗房间，直接退出副本")

    # 执行退出副本流程，返回家园
    success, msg = exit_dungeon(terminal_game, terminal_game._world.dungeon)
    if not success:
        logger.error(f"exit_dungeon 失败: {msg}")
        return terminal_game

    # 销毁副本实体并重置副本数据
    teardown_dungeon(terminal_game, terminal_game._world.dungeon)

    # 最后归档
    store_game(terminal_game, save_dir)

    # 返回更新后的游戏实例
    return terminal_game
