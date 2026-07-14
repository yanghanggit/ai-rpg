"""地下城战斗动作与生命周期。

包含所有在地下城模式（战斗中或战斗后）执行的游戏动作函数。
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
from ai_rpg.models import World, MonsterComponent
from ai_rpg.game import archive_world
from ai_rpg.services.dungeon_actions import (
    activate_all_card_draws,
    activate_play_cards_specified,
    activate_pass_turn,
    activate_monster_play_trigger,
    activate_retreat,
    activate_use_consumable,
    activate_use_gear,
    collect_combat_loot,
)
from ai_rpg.services.dungeon_lifecycle import (
    advance_dungeon,
    exit_dungeon,
)
from pathlib import Path
from typing import List
from agent_game_core import restore_game


###############################################################################
async def draw_cards_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> DBGGame:
    """从存档复位，为所有角色随机抽牌（等同于终端命令 /dc），并归档新状态。

    调用 activate_all_card_draws 为所有战斗角色（己方 + 敌方）激活抽牌动作，
    然后驱动 combat_pipeline.process() 完成抽牌推理（各角色输出决策依据）。

    抽牌完成后，存档处于「已抽牌、待打牌」状态，下一步应调用 play-cards。

    前置条件：combat_sequence.is_ongoing 必须为 True（战斗进行中）。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 DBGGame 实例（已归档）；前置条件不满足时提前返回未归档实例。
    """
    terminal_game = await restore_game(world, player_session)

    if not terminal_game.current_dungeon.is_ongoing:
        logger.error("draw-cards 只能在战斗进行中使用")
        return terminal_game

    success, message = activate_all_card_draws(terminal_game)
    if not success:
        logger.error(f"激活全员抽牌失败: {message}")
        return terminal_game

    await terminal_game._combat_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def play_cards_specified_game(
    world: World,
    player_session: PlayerSession,
    actor: str,
    card: str,
    targets: List[str],
    save_dir: Path,
) -> DBGGame:
    """从存档复位，让指定角色打出指定手牌，并归档新状态。

    只有指定角色触发 PlayCardsAction；其他角色本次 pipeline 不出牌。
    若角色名或卡牌名不合法，提前返回不归档。

    前置条件：
        - combat_sequence.is_ongoing 为 True（战斗进行中）
        - latest_round.is_round_completed 为 False（当前回合未完成）

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        actor: 出牌角色全名（如 旅行者.无名氏）。
        card: 要打出的卡牌名称（须存在于该角色手牌中）。
        targets: 目标名称列表，可为空。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 DBGGame 实例（已归档）；前置条件不满足时提前返回未归档实例。
    """
    terminal_game = await restore_game(world, player_session)

    if not terminal_game.current_dungeon.is_ongoing:
        logger.error("play-cards-specified 只能在战斗进行中使用")
        return terminal_game

    last_round = terminal_game.current_dungeon.latest_round
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

    await terminal_game._combat_pipeline.process()

    if terminal_game.current_dungeon.is_post_combat:
        logger.debug("在本次处理中战斗已结束，进入后处理阶段")

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def use_consumable_game(
    world: World,
    player_session: PlayerSession,
    actor: str,
    item: str,
    targets: List[str],
    save_dir: Path,
) -> DBGGame:
    """从存档复位，让指定角色使用背包内的消耗品，并归档新状态。

    使用消耗品不消耗 energy，可在玩家行动阶段内任意次数使用。
    若角色名或消耗品名不合法，提前返回不归档。

    前置条件：
        - combat_sequence.is_ongoing 为 True（战斗进行中）
        - latest_round.is_round_completed 为 False（当前回合未完成）

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        actor: 使用消耗品的角色全名（如 旅行者.无名氏）。
        item: 要使用的消耗品名称（须存在于该角色 InventoryComponent 中）。
        targets: 目标名称列表，可为空；SELF_ONLY/ENEMY_ALL 时系统自动覆盖。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 DBGGame 实例（已归档）；前置条件不满足时提前返回未归档实例。
    """
    terminal_game = await restore_game(world, player_session)

    if not terminal_game.current_dungeon.is_ongoing:
        logger.error("use-consumable 只能在战斗进行中使用")
        return terminal_game

    last_round = terminal_game.current_dungeon.latest_round
    if last_round is None or last_round.is_completed:
        logger.error("use-consumable 当前没有未完成的回合可供使用消耗品")
        return terminal_game

    success, message = activate_use_consumable(terminal_game, item, list(targets))
    if not success:
        logger.error(f"use-consumable 失败: {message}")
        return terminal_game

    await terminal_game._combat_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def use_gear_game(
    world: World,
    player_session: PlayerSession,
    actor: str,
    item: str,
    targets: List[str],
    save_dir: Path,
) -> DBGGame:
    """从存档复位，让指定角色在战斗中装备背包内的 GearItem，并归档新状态。

    装备后的属性加成立即生效（通过 EquippedGearComponent）。
    装备的 count 必须为 1，由系统断言。

    前置条件：
        - combat_sequence.is_ongoing 为 True（战斗进行中）
        - latest_round.is_round_completed 为 False（当前回合未完成）

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        actor: 装备使用者角色全名（如 旅行者.无名氏）。
        item: 要装备的道具名称（须存在于该角色 InventoryComponent 中，类型为 GearItem）。
        targets: 目标名称列表（通常含一个目标；ALLY_SINGLE 时指定盟友）。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 DBGGame 实例（已归档）；前置条件不满足时提前返回未归档实例。
    """
    terminal_game = await restore_game(world, player_session)

    if not terminal_game.current_dungeon.is_ongoing:
        logger.error("use-gear 只能在战斗进行中使用")
        return terminal_game

    last_round = terminal_game.current_dungeon.latest_round
    if last_round is None or last_round.is_completed:
        logger.error("use-gear 当前没有未完成的回合可供使用装备")
        return terminal_game

    success, message = activate_use_gear(terminal_game, item, list(targets))
    if not success:
        logger.error(f"use-gear 失败: {message}")
        return terminal_game

    await terminal_game._combat_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def pass_turn_game(
    world: World,
    player_session: PlayerSession,
    actor: str,
    save_dir: Path,
) -> DBGGame:
    """从存档复位，让指定角色跳过本次出牌机会（过牌），并归档新状态。

    消耗 1 点 energy 并推进行动顺序，不打出任何卡牌。
    若角色名不合法或非当前行动者，提前返回不归档。

    前置条件：
        - combat_sequence.is_ongoing 为 True（战斗进行中）
        - latest_round.is_round_completed 为 False（当前回合未完成）

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        actor: 过牌角色全名（如 旅行者.无名氏）。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 DBGGame 实例（已归档）；前置条件不满足时提前返回未归档实例。
    """
    terminal_game = await restore_game(world, player_session)

    if not terminal_game.current_dungeon.is_ongoing:
        logger.error("pass-turn 只能在战斗进行中使用")
        return terminal_game

    last_round = terminal_game.current_dungeon.latest_round
    if last_round is None or last_round.is_completed:
        logger.error("pass-turn 当前没有未完成的回合可供过牌")
        return terminal_game

    success, message = activate_pass_turn(terminal_game, actor)
    if not success:
        logger.error(f"pass-turn 失败: {message}")
        return terminal_game

    await terminal_game._combat_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def exit_dungeon_and_return_home_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> DBGGame:
    """从存档复位，结束地下城并返回家园（等同于终端命令 /th），并归档新状态。

    调用 exit_dungeon_and_return_home：恢复远征成员满血、清空状态效果、
    将角色从远征队移除、将玩家传送回起始家园场景，完成本次地下城流程。
    执行后游戏回到【家园模式】。

    前置条件：combat_sequence.is_post_combat 必须为 True（战斗已结束，无论胜负）。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 DBGGame 实例（已归档）；前置条件不满足时提前返回未归档实例。
    """
    terminal_game = await restore_game(world, player_session)

    # 状态守卫：只能在战斗结束后使用
    if not terminal_game.current_dungeon.is_post_combat:
        logger.error("exit-dungeon 只能在战斗结束后使用")
        return terminal_game

    # 执行退出地下城流程，返回家园
    exit_dungeon(terminal_game, terminal_game._world.dungeon)

    # 最后归档
    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def next_dungeon_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> DBGGame:
    """从存档复位，进入地下城下一关（等同于终端命令 /and），并归档新状态。

    调用 advance_to_next_stage 将地下城推进至下一关场景，
    然后驱动 combat_pipeline.process() 完成新关卡的战斗初始化
    （场景描述、初始状态效果、创建新回合）。

    前置条件：
        - combat_sequence.is_post_combat 为 True（上一关战斗已结束）
        - combat_sequence.is_won 为 True（必须胜利，失败只能 exit-dungeon）
        - current_dungeon.peek_next_stage() 不为 None（存在下一关）

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 DBGGame 实例（已归档）；前置条件不满足时提前返回未归档实例。
    """
    terminal_game = await restore_game(world, player_session)

    if not terminal_game.current_dungeon.is_post_combat:
        logger.error("next-dungeon 只能在战斗结束后使用")
        return terminal_game

    if terminal_game.current_dungeon.is_lost:
        logger.info("英雄失败，应该返回营地")
        return terminal_game

    if not terminal_game.current_dungeon.is_won:
        assert False, "不可能出现的情况！"

    # next_level = terminal_game.current_dungeon.peek_next_stage()
    # if next_level is None:
    #     logger.info("没有下一关，你胜利了，应该返回营地")
    #     return terminal_game

    # 获取下一房间索引和房间实例，确保存在下一房间，否则无法推进地下城
    next_room_index = terminal_game.current_dungeon.current_room_index + 1
    next_room = terminal_game.current_dungeon.get_room(next_room_index)
    if next_room is None:
        logger.error("地下城前进失败，没有更多房间")
        return terminal_game

    # 推进地下城到下一房间，更新当前房间索引和状态
    advance_dungeon(terminal_game, terminal_game.current_dungeon)

    # 进入下一关卡后，驱动战斗流水线处理新关卡的初始化，包括场景描述、初始状态效果、创建新回合等
    await terminal_game._combat_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def retreat_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> DBGGame:
    """从存档复位，主动撤退（等同于终端命令 /rtt），并归档新状态。

    调用 activate_retreat 激活撤退动作，驱动 combat_pipeline.execute()
    让 RetreatActionSystem 和 CombatOutcomeSystem 正常走一遍（标记死亡和战斗失败），
    再调用 exit_dungeon_and_return_home 返回家园。
    撤退后游戏回到【家园模式】，视为失败结算。

    前置条件：combat_sequence.is_ongoing 必须为 True（只能在战斗进行中撤退）。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 DBGGame 实例（已归档）；前置条件不满足时提前返回未归档实例。
    """
    # 复位游戏状态
    terminal_game = await restore_game(world, player_session)

    # 状态守卫：只能在战斗进行中撤退
    if not terminal_game.current_dungeon.is_ongoing:
        logger.error("retreat 只能在战斗进行中使用")
        return terminal_game

    # 标记撤退意图并正常走一遍战斗流程，让 RetreatActionSystem 和 CombatOutcomeSystem 处理后续结算（失败）
    success, message = activate_retreat(terminal_game)
    if not success:
        logger.error(f"撤退失败: {message}")
        return terminal_game

    logger.info(f"撤退动作激活成功: {message}")

    await terminal_game._combat_pipeline.execute()

    # 最后归档
    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def collect_loot_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> DBGGame:
    """从存档复位，将战利品背包（CombatLootComponent）中的道具合并至随身背包，归档新状态。

    调用 collect_combat_loot 将本场战斗的掉落物从临时组件 CombatLootComponent 转入
    InventoryComponent，并移除该临时组件。若玩家身上无 CombatLootComponent（本场无掉落
    或已收取），则记录警告并返回，不写新存档。

    前置条件：战斗胜利后（is_post_combat + is_won），CombatLootSystem 已将掉落物写入
    CombatLootComponent。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 DBGGame 实例；无战利品可收时返回未归档实例。
    """
    terminal_game = await restore_game(world, player_session)

    success, msg = collect_combat_loot(terminal_game)
    if not success:
        logger.warning(f"collect-loot 未归档：{msg}")
        return terminal_game

    terminal_game.flush_entities()
    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    logger.info(f"战利品收取完成：{msg}，存档: {save_dir}")
    return terminal_game
