"""背包、队伍与道具管理动作。

包含所有与道具移动、队伍管理、外观更新、合成相关的游戏动作函数。
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
from ai_rpg.game.player_session import PlayerSession
from ai_rpg.game.tcg_game import TCGGame
from ai_rpg.models import World
from ai_rpg.game import archive_world
from ai_rpg.services.home_actions import (
    activate_craft_consumable,
    add_party_member,
    remove_party_member,
    get_party_roster,
    move_item_to_inventory,
    move_item_to_storage,
    activate_update_appearance,
)
from pathlib import Path
from typing import List
from agent_game_core import restore_game


###############################################################################
async def add_party_member_game(
    world: World,
    player_session: PlayerSession,
    member_name: str,
    save_dir: Path,
) -> TCGGame:
    """从存档复位，将指定盟友加入远征队名单，并归档新状态。

    前置条件：玩家必须处于家园模式（is_player_in_home_stage）。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        member_name: 要加入名单的盟友角色名称。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 TCGGame 实例；操作失败时提前返回未归档实例。
    """
    terminal_game = await restore_game(world, player_session)

    success, error_detail = add_party_member(terminal_game, member_name)
    if not success:
        logger.error(f"添加远征队成员失败: {error_detail}")
        return terminal_game

    terminal_game.flush_entities()
    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    logger.info(f"已将 {member_name} 加入远征队名单，存档: {save_dir}")
    return terminal_game


###############################################################################
async def remove_party_member_game(
    world: World,
    player_session: PlayerSession,
    member_name: str,
    save_dir: Path,
) -> TCGGame:
    """从存档复位，将指定盟友从远征队名单移除，并归档新状态。

    前置条件：玩家必须处于家园模式（is_player_in_home_stage）。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        member_name: 要移除的盟友角色名称。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 TCGGame 实例；操作失败时提前返回未归档实例。
    """
    terminal_game = await restore_game(world, player_session)

    success, error_detail = remove_party_member(terminal_game, member_name)
    if not success:
        logger.error(f"移除远征队成员失败: {error_detail}")
        return terminal_game

    terminal_game.flush_entities()
    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    logger.info(f"已将 {member_name} 从远征队名单移除，存档: {save_dir}")
    return terminal_game


###############################################################################
async def get_party_roster_game(
    world: World,
    player_session: PlayerSession,
) -> List[str]:
    """从存档复位，返回当前远征队名单（只读，不写新存档）。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。

    Returns:
        远征队同伴名称列表（不含玩家自身）。
    """
    terminal_game = await restore_game(world, player_session)
    return get_party_roster(terminal_game)


###############################################################################
async def move_item_to_inventory_game(
    world: World,
    player_session: PlayerSession,
    item_name: str,
    save_dir: Path,
) -> TCGGame:
    """从存档复位，将指定道具从储物箱移入随身背包，并归档新状态。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        item_name: 要移动的道具名称（精确匹配 StorageComponent.items）。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 TCGGame 实例；操作失败时提前返回未归档实例。
    """
    terminal_game = await restore_game(world, player_session)

    success, error_detail = move_item_to_inventory(terminal_game, item_name)
    if not success:
        logger.error(f"移动道具到背包失败: {error_detail}")
        return terminal_game

    terminal_game.flush_entities()
    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    logger.info(f"道具 {item_name!r} 已从储物箱移入随身背包，存档: {save_dir}")
    return terminal_game


###############################################################################
async def move_item_to_storage_game(
    world: World,
    player_session: PlayerSession,
    item_name: str,
    save_dir: Path,
) -> TCGGame:
    """从存档复位，将指定道具从随身背包移回储物箱，并归档新状态。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        item_name: 要移动的道具名称（精确匹配 InventoryComponent.items）。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 TCGGame 实例；操作失败时提前返回未归档实例。
    """
    terminal_game = await restore_game(world, player_session)

    success, error_detail = move_item_to_storage(terminal_game, item_name)
    if not success:
        logger.error(f"移动道具到储物箱失败: {error_detail}")
        return terminal_game

    terminal_game.flush_entities()
    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    logger.info(f"道具 {item_name!r} 已从随身背包移回储物箱，存档: {save_dir}")
    return terminal_game


###############################################################################
async def update_appearance_game(
    world: World,
    player_session: PlayerSession,
    item_name: str,
    save_dir: Path,
    target_name: str = "",
) -> TCGGame:
    """从存档复位，触发外观更新动作并通过 home pipeline 执行 LLM 合成，归档新状态。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        item_name: CostumeItem 的精确名称；传入空字符串表示移除时装。
        save_dir: 新存档写入目录。
        target_name: 目标角色全名；为空时默认玩家自身。

    Returns:
        执行完毕后的 TCGGame 实例；操作失败时提前返回未归档实例。
    """
    terminal_game = await restore_game(world, player_session)

    success, error_detail = activate_update_appearance(
        terminal_game, item_name, target_name
    )
    if not success:
        logger.error(f"外观更新失败: {error_detail}")
        return terminal_game

    await terminal_game._home_pipeline.process()
    terminal_game.flush_entities()
    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    action = "移除时装" if not item_name else f"穿上时装 {item_name!r}"
    target_desc = target_name if target_name else "玩家"
    logger.info(f"外观更新完成（{target_desc} {action}），存档: {save_dir}")
    return terminal_game


###############################################################################
async def craft_consumable_game(
    world: World,
    player_session: PlayerSession,
    material_names: List[str],
    save_dir: Path,
) -> TCGGame:
    """从存档复位，触发工坊合成消耗品动作并通过 home pipeline 执行 LLM 推理，归档新状态。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        material_names: 参与合成的材料名称列表（允许重复代表多份）。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 TCGGame 实例；操作失败时提前返回未归档实例。
    """
    terminal_game = await restore_game(world, player_session)

    success, error_detail = activate_craft_consumable(terminal_game, material_names)
    if not success:
        logger.error(f"合成消耗品失败: {error_detail}")
        return terminal_game

    await terminal_game._home_pipeline.process()
    terminal_game.flush_entities()
    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    logger.info(f"合成消耗品完成（材料={material_names}），存档: {save_dir}")
    return terminal_game
