"""CLI 工具 - 游戏创建与初始化。

使用方法：
    python scripts/run_cli_game.py
    python scripts/run_cli_game.py --user 玩家名 --game 游戏名
"""

import os
import sys

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)

import asyncio
import datetime
import click
from loguru import logger
from ai_rpg.chat_client.client import ChatClient
from ai_rpg.configuration import server_configuration
from ai_rpg.game.config import GAME_1, LOGS_DIR, setup_logger
from ai_rpg.demo import (
    create_hunter_mystic_blueprint,
    create_mountain_beasts_dungeon,
)
from ai_rpg.game.player_session import PlayerSession
from ai_rpg.game.tcg_game import TCGGame
from ai_rpg.image_client.client import ImageClient
from ai_rpg.models import World


###############################################################################################################################################
async def _create_and_initialize_game(user: str, game: str) -> TCGGame:
    """创建并初始化一个新游戏实例。

    Args:
        user: 玩家用户名
        game: 游戏名称

    Returns:
        已初始化完成的 TCGGame 实例
    """

    world_blueprint = create_hunter_mystic_blueprint(game)
    assert world_blueprint is not None, "world blueprint 反序列化失败"

    world_data = World(
        entity_counter=1000,
        entities_serialization=[],
        agents_context={},
        dungeon=create_mountain_beasts_dungeon(),
        blueprint=world_blueprint,
    )

    assert world_data is not None, "World data must exist to create a game"
    terminal_game = TCGGame(
        name=game,
        player_session=PlayerSession(
            name=user,
            actor=world_data.blueprint.player_actor,
            game=game,
        ),
        world=world_data,
    )

    ChatClient.initialize_url_config(server_configuration)
    ImageClient.initialize_url_config(server_configuration)

    assert (
        len(terminal_game.world.entities_serialization) == 0
    ), "测试阶段，游戏中不应该有实体数据！"
    terminal_game.build_from_blueprint().flush_entities()

    await terminal_game.initialize()

    logger.info(f"游戏创建并初始化完成：user={user}, game={game}")
    return terminal_game


###############################################################################################################################################
@click.command()
@click.option(
    "--user",
    default=None,
    help="玩家用户名。默认为带时间戳的随机名称。",
)
@click.option(
    "--game",
    default=GAME_1,
    show_default=True,
    help="游戏名称。",
)
def cli(user: str, game: str) -> None:
    """创建并初始化一个新的游戏实例。"""

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
    setup_logger(_log_file)
    logger.info(f"本次运行日志文件：{_log_file}")

    if user is None:
        user = f"cli-player-{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}"

    asyncio.run(_create_and_initialize_game(user, game))


###############################################################################################################################################
if __name__ == "__main__":
    cli()
