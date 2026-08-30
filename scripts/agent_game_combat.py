"""副本战斗动作。

包含所有在战斗房间中执行的游戏动作函数（抽牌、出牌、过牌、撤退、使用物品、收取战利品等）。
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
from ai_rpg.models import PlayerSession, CombatState
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import WorldState, MonsterComponent
from ai_rpg.game.dbg_store import store_game
from ai_rpg.services.dungeon_combat_actions import (
    activate_all_card_draws,
    activate_play_cards_specified,
    activate_pass_turn,
    activate_monster_play_trigger,
    activate_retreat,
    activate_use_consumable,
    activate_equip_gear,
    collect_combat_loot,
)
from pathlib import Path
from typing import List
from agent_game_core import restore_game


###############################################################################
async def draw_cards_game(
    world: WorldState,
    player_session: PlayerSession,
    save_dir: Path,
) -> DBGGame:
    """为所有战斗角色抽牌并归档。需战斗进行中。"""
    terminal_game = await restore_game(world, player_session)

    if not terminal_game.is_current_room_dungeon_combat:
        logger.error("draw-cards 只能在战斗房间中使用")
        return terminal_game

    if not terminal_game.current_dungeon_combat_room.combat.is_ongoing:
        logger.error("draw-cards 只能在战斗进行中使用")
        return terminal_game

    success, message = activate_all_card_draws(terminal_game)
    if not success:
        logger.error(f"激活全员抽牌失败: {message}")
        return terminal_game

    await terminal_game._dungeon_combat_room_pipeline.process()

    store_game(terminal_game, save_dir)
    return terminal_game


###############################################################################
async def play_cards_specified_game(
    world: WorldState,
    player_session: PlayerSession,
    actor: str,
    card: str,
    targets: List[str],
    save_dir: Path,
) -> DBGGame:
    """让指定角色打出手牌（怪物则由 AI 自动出牌）并归档。需战斗进行中且当前回合未完成。"""
    terminal_game = await restore_game(world, player_session)

    if not terminal_game.is_current_room_dungeon_combat:
        logger.error("play-cards-specified 只能在战斗房间中使用")
        return terminal_game

    if not terminal_game.current_dungeon_combat_room.combat.is_ongoing:
        logger.error("play-cards-specified 只能在战斗进行中使用")
        return terminal_game

    last_round = terminal_game.current_dungeon_combat_room.combat.latest_round
    if last_round is None or last_round.is_completed:
        logger.error("play-cards-specified 当前没有未完成的回合可供打牌")
        return terminal_game

    actor_entity = terminal_game.get_actor_entity(actor)
    if actor_entity is not None and actor_entity.has(MonsterComponent):
        success, message = activate_monster_play_trigger(terminal_game, actor)
    else:
        success, message = await activate_play_cards_specified(
            terminal_game, actor, card, list(targets)
        )
    if not success:
        logger.error(f"play-cards-specified 失败: {message}")
        return terminal_game

    await terminal_game._dungeon_combat_room_pipeline.process()

    if (
        terminal_game.current_dungeon_combat_room.combat.state
        == CombatState.POST_COMBAT
    ):
        logger.debug("在本次处理中战斗已结束，进入后处理阶段")

    store_game(terminal_game, save_dir)
    return terminal_game


###############################################################################
async def use_consumable_game(
    world: WorldState,
    player_session: PlayerSession,
    item: str,
    targets: List[str],
    save_dir: Path,
) -> DBGGame:
    """让当前行动者使用队伍背包内的消耗品并归档。需战斗进行中且当前回合未完成。"""
    terminal_game = await restore_game(world, player_session)

    if not terminal_game.is_current_room_dungeon_combat:
        logger.error("use-consumable 只能在战斗房间中使用")
        return terminal_game

    if not terminal_game.current_dungeon_combat_room.combat.is_ongoing:
        logger.error("use-consumable 只能在战斗进行中使用")
        return terminal_game

    last_round = terminal_game.current_dungeon_combat_room.combat.latest_round
    if last_round is None or last_round.is_completed:
        logger.error("use-consumable 当前没有未完成的回合可供使用消耗品")
        return terminal_game

    success, message = activate_use_consumable(terminal_game, item, list(targets))
    if not success:
        logger.error(f"use-consumable 失败: {message}")
        return terminal_game

    await terminal_game._dungeon_combat_room_pipeline.process()

    store_game(terminal_game, save_dir)
    return terminal_game


###############################################################################
async def equip_gear_game(
    world: WorldState,
    player_session: PlayerSession,
    item: str,
    save_dir: Path,
) -> DBGGame:
    """将 GearItem 转化为当前行动者（我方）的手牌并归档。需战斗进行中且当前回合未完成。"""
    terminal_game = await restore_game(world, player_session)

    if not terminal_game.is_current_room_dungeon_combat:
        logger.error("equip-gear 只能在战斗房间中使用")
        return terminal_game

    if not terminal_game.current_dungeon_combat_room.combat.is_ongoing:
        logger.error("equip-gear 只能在战斗进行中使用")
        return terminal_game

    last_round = terminal_game.current_dungeon_combat_room.combat.latest_round
    if last_round is None or last_round.is_completed:
        logger.error("equip-gear 当前没有未完成的回合可供装备")
        return terminal_game

    success, message = activate_equip_gear(terminal_game, item)
    if not success:
        logger.error(f"equip-gear 失败: {message}")
        return terminal_game

    await terminal_game._dungeon_combat_room_pipeline.process()

    store_game(terminal_game, save_dir)
    return terminal_game


###############################################################################
async def pass_turn_game(
    world: WorldState,
    player_session: PlayerSession,
    actor: str,
    save_dir: Path,
) -> DBGGame:
    """让指定角色跳过本次出牌（过牌）并归档。需战斗进行中且当前回合未完成。"""
    terminal_game = await restore_game(world, player_session)

    if not terminal_game.is_current_room_dungeon_combat:
        logger.error("pass-turn 只能在战斗房间中使用")
        return terminal_game

    if not terminal_game.current_dungeon_combat_room.combat.is_ongoing:
        logger.error("pass-turn 只能在战斗进行中使用")
        return terminal_game

    last_round = terminal_game.current_dungeon_combat_room.combat.latest_round
    if last_round is None or last_round.is_completed:
        logger.error("pass-turn 当前没有未完成的回合可供过牌")
        return terminal_game

    success, message = activate_pass_turn(terminal_game, actor)
    if not success:
        logger.error(f"pass-turn 失败: {message}")
        return terminal_game

    await terminal_game._dungeon_combat_room_pipeline.process()

    store_game(terminal_game, save_dir)
    return terminal_game


###############################################################################
async def retreat_game(
    world: WorldState,
    player_session: PlayerSession,
    save_dir: Path,
) -> DBGGame:
    """主动撤退（视为失败）并归档。需战斗进行中。"""
    # 复位游戏状态
    terminal_game = await restore_game(world, player_session)

    if not terminal_game.is_current_room_dungeon_combat:
        logger.error("retreat 只能在战斗房间中使用")
        return terminal_game

    # 状态守卫：只能在战斗进行中撤退
    if not terminal_game.current_dungeon_combat_room.combat.is_ongoing:
        logger.error("retreat 只能在战斗进行中使用")
        return terminal_game

    # 标记撤退意图并正常走一遍战斗流程，让 RetreatActionSystem 和 CombatOutcomeSystem 处理后续结算（失败）
    success, message = activate_retreat(terminal_game)
    if not success:
        logger.error(f"撤退失败: {message}")
        return terminal_game

    logger.info(f"撤退动作激活成功: {message}")

    await terminal_game._dungeon_combat_room_pipeline.execute()

    # 最后归档
    store_game(terminal_game, save_dir)
    return terminal_game


###############################################################################
async def collect_loot_game(
    world: WorldState,
    player_session: PlayerSession,
    save_dir: Path,
) -> DBGGame:
    """收取战利品至随身背包并归档。无战利品时不归档。"""
    terminal_game = await restore_game(world, player_session)

    if not terminal_game.is_current_room_dungeon_combat:
        logger.error("collect-loot 只能在战斗房间中使用")
        return terminal_game

    success, msg = collect_combat_loot(terminal_game)
    if not success:
        logger.warning(f"collect-loot 未归档：{msg}")
        return terminal_game

    store_game(terminal_game, save_dir)
    logger.info(f"战利品收取完成：{msg}，存档: {save_dir}")
    return terminal_game
