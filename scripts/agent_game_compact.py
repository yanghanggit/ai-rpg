"""上下文压缩动作。

包含手动触发指定实体上下文压缩的游戏动作函数。
"""

import os
import sys

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)
# 将 scripts 目录添加到模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pathlib import Path

from agent_game_core import restore_game
from loguru import logger

from ai_rpg.game.dbg_game import DBGGame
from ai_rpg.game.dbg_store import store_game_async
from ai_rpg.models import PlayerSession, WorldState
from ai_rpg.services.compact_action import activate_compact_context


###############################################################################
async def compact_context_game(
    world: WorldState,
    player_session: PlayerSession,
    target_name: str,
    save_dir: Path,
) -> DBGGame:
    """手动压缩指定实体的 LLM 记忆并归档。"""
    terminal_game = await restore_game(world, player_session)

    success, error_detail = activate_compact_context(terminal_game, target_name)
    if not success:
        logger.error(f"激活上下文压缩失败: {error_detail}")
        return terminal_game

    await terminal_game._compact_pipeline.process()

    await store_game_async(terminal_game, save_dir)
    logger.info(f"已完成上下文压缩: target={target_name}, 存档: {save_dir}")
    return terminal_game
