"""副本奖励（Spoils）动作：生成候选 / 领卡 / 清理。

与房间类型无关：仅要求当前房间**不是战斗房间**（非战斗房间通用）。

``generate_spoils_game`` 可接受显式候选规格（``prototype_ids``）：调测时用来把
“抽到哪几张”从随机里拿回来（如强制抽到带自主槽的原型），生产入口不传即保持随机。
"""

from pathlib import Path
from typing import Optional, Sequence

from loguru import logger

from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.game.dbg_store import store_game_async
from ai_rpg.models import PlayerSession, WorldState
from ai_rpg.services.dungeon_spoils_actions import (
    activate_generate_spoils,
    activate_pick_spoils_card,
    party_has_any_spoils,
    remove_spoils,
)

from .core import restore_game


###############################################################################
async def generate_spoils_game(
    world: WorldState,
    player_session: PlayerSession,
    save_dir: Path,
    prototype_ids: Optional[Sequence[str]] = None,
) -> DBGGame:
    """为当前非战斗房间内的队伍成员生成候选奖励（Spoils）并归档。

    `prototype_ids` 非空时按此规格物化候选（顺序、重复照给），否则系统随机抽取。
    """

    # 创建 DBGGame 实例并从快照恢复游戏状态
    terminal_game = await restore_game(world, player_session)

    # 状态守卫：只能在非战斗房间使用
    if terminal_game.is_current_room_dungeon_combat:
        logger.error("generate-spoils 只能在非战斗房间中使用")
        return terminal_game

    # 外部显式激活奖励生成动作（内部含幂等守卫）
    success, message = activate_generate_spoils(
        terminal_game, prototype_ids=list(prototype_ids or [])
    )
    if not success:
        logger.error(f"激活奖励生成失败: {message}")
        return terminal_game

    # 推动房间管道处理，让 GenerateSpoilsActionSystem 响应并生成奖励
    await terminal_game._dungeon_opening_room_pipeline.process()

    # 零产出：设计会话出错时不会写入 SpoilsComponent（出错就没有结果），可重试
    if not party_has_any_spoils(terminal_game):
        logger.warning(
            "本次未产生任何奖励（设计会话出错或未产出候选）：可重新执行 generate-spoils"
        )

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
    """从 Spoils 领取一张卡加入牌库并归档。需当前在非战斗房间且已生成奖励。"""

    # 创建 DBGGame 实例并从快照恢复游戏状态
    terminal_game = await restore_game(world, player_session)

    # 状态守卫：只能在非战斗房间使用
    if terminal_game.is_current_room_dungeon_combat:
        logger.error("pick-card 只能在非战斗房间中使用")
        return terminal_game

    # 外部显式激活领卡动作（内部含 Spoils 存在 + 卡牌检索守卫）
    success, message = activate_pick_spoils_card(terminal_game, actor, card)
    if not success:
        logger.error(f"从 Spoils 领卡失败: {message}")
        return terminal_game

    # 推动房间管道处理，让 PickSpoilsActionSystem 响应并把选中卡加入牌库
    await terminal_game._dungeon_opening_room_pipeline.process()

    # 最后归档
    await store_game_async(terminal_game, save_dir)
    return terminal_game


###############################################################################
async def remove_spoils_game(
    world: WorldState,
    player_session: PlayerSession,
    save_dir: Path,
) -> DBGGame:
    """清理当前副本队伍成员的奖励状态（SpoilsComponent）并归档。"""

    # 创建 DBGGame 实例并从快照恢复游戏状态
    terminal_game = await restore_game(world, player_session)

    # 外部显式清理奖励状态（内部含副本态守卫）
    success, message = remove_spoils(terminal_game)
    if not success:
        logger.error(f"清理奖励失败: {message}")
        return terminal_game

    # 最后归档
    await store_game_async(terminal_game, save_dir)
    return terminal_game
