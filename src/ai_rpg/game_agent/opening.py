"""副本开场房间动作。

包含所有在开场房间（OpeningRoom）中执行的游戏动作函数
（房间初始化、奖励生成、从 Spoils 领卡等）。
"""

from loguru import logger
from ai_rpg.models import PlayerSession
from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.models import WorldState
from ai_rpg.game.dbg_store import store_game_async
from ai_rpg.services.dungeon_opening_actions import (
    activate_generate_spoils,
    activate_pick_spoils_card,
)
from pathlib import Path
from .core import restore_game


###############################################################################
async def init_opening_game(
    world: WorldState,
    player_session: PlayerSession,
    save_dir: Path,
) -> DBGGame:
    """初始化开场房间（叙事 + 牌库）并归档。需当前处于开场房间且尚未初始化。"""

    # 创建 DBGGame 实例并从快照恢复游戏状态
    terminal_game = await restore_game(world, player_session)

    # 状态守卫：只能在开场房间使用
    if not terminal_game.is_current_room_dungeon_opening:
        logger.error("opening-init 只能在开场房间中使用")
        return terminal_game

    # 状态守卫：开场房间已初始化则拒绝重复初始化
    if terminal_game.current_dungeon_opening_room.initialized:
        logger.error("开场房间已初始化，无需重复初始化")
        return terminal_game

    # 推动开场管道（叙事 + 牌库初始化，无战斗）
    await terminal_game._dungeon_opening_room_pipeline.process()

    # 最后归档
    await store_game_async(terminal_game, save_dir)
    return terminal_game


###############################################################################
async def generate_spoils_game(
    world: WorldState,
    player_session: PlayerSession,
    save_dir: Path,
) -> DBGGame:
    """为开场房间内的队伍成员生成候选奖励（Spoils）并归档。需开场已初始化（叙事 + 牌库）。"""

    # 创建 DBGGame 实例并从快照恢复游戏状态
    terminal_game = await restore_game(world, player_session)

    # 状态守卫：只能在开场房间使用
    if not terminal_game.is_current_room_dungeon_opening:
        logger.error("generate-spoils 只能在开场房间中使用")
        return terminal_game

    # 状态守卫：依赖开场初始化（叙事 + 牌库）已完成
    if not terminal_game.current_dungeon_opening_room.initialized:
        logger.error("generate-spoils 需开场已初始化（叙事 + 牌库）")
        return terminal_game

    # 外部显式激活奖励生成动作（内部含幂等守卫）
    success, message = activate_generate_spoils(terminal_game)
    if not success:
        logger.error(f"激活奖励生成失败: {message}")
        return terminal_game

    # 推动开场管道处理，让 GenerateSpoilsActionSystem 响应并生成奖励
    await terminal_game._dungeon_opening_room_pipeline.process()

    # 最后归档
    await store_game_async(terminal_game, save_dir)
    return terminal_game


###############################################################################
async def pick_spoils_card_game(
    world: WorldState,
    player_session: PlayerSession,
    actor: str,
    card: str,
    save_dir: Path,
) -> DBGGame:
    """从 Spoils 领取一张卡加入牌库并归档。需开场已初始化且已生成奖励。"""

    # 创建 DBGGame 实例并从快照恢复游戏状态
    terminal_game = await restore_game(world, player_session)

    # 状态守卫：只能在开场房间使用
    if not terminal_game.is_current_room_dungeon_opening:
        logger.error("pick-card 只能在开场房间中使用")
        return terminal_game

    # 状态守卫：依赖开场初始化（叙事 + 牌库）已完成
    if not terminal_game.current_dungeon_opening_room.initialized:
        logger.error("pick-card 需开场已初始化（叙事 + 牌库）")
        return terminal_game

    # 外部显式激活领卡动作（内部含 Spoils 存在 + 卡牌检索守卫）
    success, message = activate_pick_spoils_card(terminal_game, actor, card)
    if not success:
        logger.error(f"从 Spoils 领卡失败: {message}")
        return terminal_game

    # 推动开场管道处理，让 PickSpoilsActionSystem 响应并把选中卡加入牌库
    await terminal_game._dungeon_opening_room_pipeline.process()

    # 最后归档
    await store_game_async(terminal_game, save_dir)
    return terminal_game
