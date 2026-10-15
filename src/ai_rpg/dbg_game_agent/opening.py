"""副本开场房间动作：开场初始化（叙事 + 环境注入）。"""

from pathlib import Path

from loguru import logger

from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.game.dbg_store import store_game_async
from ai_rpg.models import PlayerSession, WorldState

from .core import restore_game


###############################################################################
async def init_opening_game(
    world: WorldState,
    player_session: PlayerSession,
    save_dir: Path,
) -> DBGGame:
    """初始化开场房间（叙事 + 环境）并归档。需当前处于开场房间（管道按消息标记幂等）。"""

    # 创建 DBGGame 实例并从快照恢复游戏状态
    terminal_game = await restore_game(world, player_session)

    # 状态守卫：只能在开场房间使用
    if not terminal_game.is_current_room_dungeon_opening:
        logger.error("opening-init 只能在开场房间中使用")
        return terminal_game

    # 推动开场管道（外观 + 环境叙事生成 + 注入给队员，无战斗；内部按消息标记幂等）
    await terminal_game._dungeon_opening_room_pipeline.process()

    # 最后归档
    await store_game_async(terminal_game, save_dir)
    return terminal_game
