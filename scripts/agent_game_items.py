"""背包与道具管理动作。

包含所有与道具移动、外观更新、合成相关的游戏动作函数。
（远征队 roster 相关已移至 agent_game_home.py）
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
from ai_rpg.services.home_actions import (
    activate_craft_consumable,
    activate_craft_gear_item,
    activate_craft_costume_item,
    move_item_to_inventory,
    move_item_to_storage,
    activate_wear_costume,
    activate_remove_costume,
)
from pathlib import Path
from typing import List
from agent_game_core import restore_game


###############################################################################
async def move_item_to_inventory_game(
    world: World,
    player_session: PlayerSession,
    item_name: str,
    save_dir: Path,
) -> DBGGame:
    """将指定道具从储物箱移入随身背包并归档。"""
    terminal_game = await restore_game(world, player_session)

    success, error_detail = move_item_to_inventory(terminal_game, item_name)
    if not success:
        logger.error(f"移动道具到背包失败: {error_detail}")
        return terminal_game

    store_game(terminal_game, save_dir)
    logger.info(f"道具 {item_name!r} 已从储物箱移入随身背包，存档: {save_dir}")
    return terminal_game


###############################################################################
async def move_item_to_storage_game(
    world: World,
    player_session: PlayerSession,
    item_name: str,
    save_dir: Path,
) -> DBGGame:
    """将指定道具从随身背包移回储物箱并归档。"""
    terminal_game = await restore_game(world, player_session)

    success, error_detail = move_item_to_storage(terminal_game, item_name)
    if not success:
        logger.error(f"移动道具到储物箱失败: {error_detail}")
        return terminal_game

    store_game(terminal_game, save_dir)
    logger.info(f"道具 {item_name!r} 已从随身背包移回储物箱，存档: {save_dir}")
    return terminal_game


###############################################################################
async def wear_costume_game(
    world: World,
    player_session: PlayerSession,
    item_name: str,
    save_dir: Path,
    target_name: str,
) -> DBGGame:
    """为指定角色穿装并归档。"""
    terminal_game = await restore_game(world, player_session)

    success, error_detail = activate_wear_costume(terminal_game, item_name, target_name)
    if not success:
        logger.error(f"穿装失败: {error_detail}")
        return terminal_game

    await terminal_game._home_pipeline.process()
    store_game(terminal_game, save_dir)
    logger.info(f"穿装完成（{target_name} 穿上时装 {item_name!r}），存档: {save_dir}")
    return terminal_game


###############################################################################
async def remove_costume_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
    target_name: str,
) -> DBGGame:
    """移除指定角色的时装并归档。"""
    terminal_game = await restore_game(world, player_session)

    success, error_detail = activate_remove_costume(terminal_game, target_name)
    if not success:
        logger.error(f"脱装失败: {error_detail}")
        return terminal_game

    await terminal_game._home_pipeline.process()
    store_game(terminal_game, save_dir)
    logger.info(f"脱装完成（{target_name} 移除时装），存档: {save_dir}")
    return terminal_game


###############################################################################
async def craft_consumable_game(
    world: World,
    player_session: PlayerSession,
    material_names: List[str],
    save_dir: Path,
) -> DBGGame:
    """使用材料合成消耗品并归档。"""
    terminal_game = await restore_game(world, player_session)

    success, error_detail = activate_craft_consumable(terminal_game, material_names)
    if not success:
        logger.error(f"合成消耗品失败: {error_detail}")
        return terminal_game

    await terminal_game._home_craft_pipeline.process()
    store_game(terminal_game, save_dir)
    logger.info(f"合成消耗品完成（材料={material_names}），存档: {save_dir}")
    return terminal_game


async def craft_gear_item_game(
    world: World,
    player_session: PlayerSession,
    material_names: list[str],
    save_dir: Path,
) -> DBGGame:
    """使用材料锻造装备并归档。"""
    terminal_game = await restore_game(world, player_session)

    success, error_detail = activate_craft_gear_item(terminal_game, material_names)
    if not success:
        logger.error(f"锻造装备失败: {error_detail}")
        return terminal_game

    await terminal_game._home_craft_pipeline.process()
    store_game(terminal_game, save_dir)
    logger.info(f"锻造装备完成（材料={material_names}），存档: {save_dir}")
    return terminal_game


###############################################################################
async def craft_costume_game(
    world: World,
    player_session: PlayerSession,
    material_names: list[str],
    save_dir: Path,
) -> DBGGame:
    """使用材料制作时装并归档。"""
    terminal_game = await restore_game(world, player_session)

    success, error_detail = activate_craft_costume_item(terminal_game, material_names)
    if not success:
        logger.error(f"制作时装失败: {error_detail}")
        return terminal_game

    await terminal_game._home_craft_pipeline.process()
    store_game(terminal_game, save_dir)
    logger.info(f"制作时装完成（材料={material_names}），存档: {save_dir}")
    return terminal_game
