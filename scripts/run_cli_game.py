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
from ai_rpg.game.config import GAME_1, LOGS_DIR, WORLDS_DIR, setup_logger
from ai_rpg.demo import (
    create_hunter_mystic_blueprint,
    create_mountain_beasts_dungeon,
)
from ai_rpg.game.player_session import PlayerSession
from ai_rpg.game.tcg_game import TCGGame
from ai_rpg.image_client.client import ImageClient
from ai_rpg.models import World
from ai_rpg.game import archive_world, restore_world
from ai_rpg.services.home_actions import (
    activate_stage_plan,
    activate_speak_action,
    activate_switch_stage,
)
from ai_rpg.services.dungeon_actions import (
    activate_random_expedition_member_card_draws,
    activate_random_enemy_card_draws,
    ensure_all_actors_have_fallback_cards,
    activate_play_cards,
    mark_expedition_retreat,
)
from ai_rpg.services.dungeon_stage_transition import (
    initialize_dungeon_first_entry,
    advance_to_next_stage,
    complete_dungeon_and_return_home,
)
from pathlib import Path


###############################################################################################################################################
async def _create_and_initialize_game(user: str, game: str, save_dir: Path) -> TCGGame:
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

    # 检查聊天服务
    await ChatClient.health_check()

    # 检查图片服务
    await ImageClient.health_check()

    # 持久化游戏世界数据到存档目录，并启用 gzip 快照功能
    archive_world(
        terminal_game.world,
        terminal_game.player_session,
        save_dir=save_dir,
        enable_gzip=True,
    )
    return terminal_game


###############################################################################################################################################
async def _restore_game(
    world: World,
    player_session: PlayerSession,
) -> TCGGame:
    """从已还原的 World/PlayerSession 构造 TCGGame 并完成初始化。"""
    game = str(world.blueprint.name)
    terminal_game = TCGGame(
        name=game,
        player_session=player_session,
        world=world,
    )
    ChatClient.initialize_url_config(server_configuration)
    ImageClient.initialize_url_config(server_configuration)
    terminal_game.restore_from_snapshot()
    await terminal_game.initialize()
    logger.info(f"游戏已从存档恢复：user={player_session.name}, game={game}")
    return terminal_game


###############################################################################################################################################
async def _advance_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> TCGGame:
    """从已还原的 World/PlayerSession 出发，执行一轮家园推进并归档新状态。"""
    terminal_game = await _restore_game(world, player_session)

    success, error_detail = activate_stage_plan(terminal_game)
    if not success:
        logger.debug(f"激活行动计划失败: {error_detail}")

    await terminal_game.home_pipeline.process()

    archive_world(
        terminal_game.world,
        terminal_game.player_session,
        save_dir=save_dir,
        enable_gzip=True,
    )
    return terminal_game


###############################################################################################################################################
async def _speak_game(
    world: World,
    player_session: PlayerSession,
    target: str,
    content: str,
    save_dir: Path,
) -> TCGGame:
    """从存档复位，执行一次对话行动，并归档新状态。"""
    terminal_game = await _restore_game(world, player_session)

    success, _ = activate_speak_action(
        tcg_game=terminal_game,
        target=target,
        content=content,
    )
    if not success:
        logger.error(f"激活对话行动失败: target={target}")
        return terminal_game

    await terminal_game.home_pipeline.process()

    archive_world(
        terminal_game.world,
        terminal_game.player_session,
        save_dir=save_dir,
        enable_gzip=True,
    )
    return terminal_game


###############################################################################################################################################
async def _switch_stage_game(
    world: World,
    player_session: PlayerSession,
    stage_name: str,
    save_dir: Path,
) -> TCGGame:
    """从存档复位，执行场景切换行动，并归档新状态。"""
    terminal_game = await _restore_game(world, player_session)

    success, _ = activate_switch_stage(
        tcg_game=terminal_game,
        stage_name=stage_name,
    )
    if not success:
        logger.error(f"激活场景切换失败: stage={stage_name}")
        return terminal_game

    await terminal_game.home_pipeline.process()

    archive_world(
        terminal_game.world,
        terminal_game.player_session,
        save_dir=save_dir,
        enable_gzip=True,
    )
    return terminal_game


###############################################################################################################################################
async def _enter_dungeon_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> TCGGame:
    """从存档复位，进入地下城，并归档新状态。"""
    terminal_game = await _restore_game(world, player_session)

    if len(terminal_game.current_dungeon.stages) == 0:
        logger.error("地下城全部已结束，没有可进入的地下城")
        return terminal_game

    if not initialize_dungeon_first_entry(terminal_game, terminal_game.current_dungeon):
        logger.error("传送地下城失败")
        return terminal_game

    if len(terminal_game.current_combat_sequence.combats) == 0:
        logger.error("没有战斗可以进行")
        return terminal_game

    await terminal_game.combat_pipeline.process()

    archive_world(
        terminal_game.world,
        terminal_game.player_session,
        save_dir=save_dir,
        enable_gzip=True,
    )
    return terminal_game


###############################################################################################################################################
async def _draw_cards_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> TCGGame:
    """从存档复位，为所有角色抽牌（dc），并归档新状态。"""
    terminal_game = await _restore_game(world, player_session)

    if not terminal_game.current_combat_sequence.is_ongoing:
        logger.error("draw-cards 只能在战斗进行中使用")
        return terminal_game

    success, message = activate_random_expedition_member_card_draws(terminal_game)
    if not success:
        logger.error(f"激活Ally抽牌失败: {message}")
        return terminal_game

    success, message = activate_random_enemy_card_draws(terminal_game)
    if not success:
        logger.error(f"激活Enemy抽牌失败: {message}")
        return terminal_game

    await terminal_game.combat_pipeline.process()

    archive_world(
        terminal_game.world,
        terminal_game.player_session,
        save_dir=save_dir,
        enable_gzip=True,
    )
    return terminal_game


###############################################################################################################################################
async def _play_cards_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> TCGGame:
    """从存档复位，执行打牌（pc），并归档新状态。"""
    terminal_game = await _restore_game(world, player_session)

    if not terminal_game.current_combat_sequence.is_ongoing:
        logger.error("play-cards 只能在战斗进行中使用")
        return terminal_game

    last_round = terminal_game.current_combat_sequence.latest_round
    if last_round is None or last_round.is_round_completed:
        logger.error("play-cards 当前没有未完成的回合可供打牌")
        return terminal_game

    success, message = ensure_all_actors_have_fallback_cards(terminal_game)
    if not success:
        logger.error(f"确保所有角色都有后备牌失败: {message}")
        return terminal_game

    success, message = activate_play_cards(terminal_game)
    if not success:
        logger.error(f"打牌失败: {message}")
        return terminal_game

    await terminal_game.combat_pipeline.process()

    if terminal_game.current_combat_sequence.is_post_combat:
        logger.debug("在本次处理中战斗已结束，进入后处理阶段")

    archive_world(
        terminal_game.world,
        terminal_game.player_session,
        save_dir=save_dir,
        enable_gzip=True,
    )
    return terminal_game


###############################################################################################################################################
async def _trans_home_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> TCGGame:
    """从存档复位，返回家园（th），并归档新状态。"""
    terminal_game = await _restore_game(world, player_session)

    if (
        len(terminal_game.current_combat_sequence.combats) == 0
        or not terminal_game.current_combat_sequence.is_post_combat
    ):
        logger.error("trans-home 只能在战斗结束后使用")
        return terminal_game

    complete_dungeon_and_return_home(terminal_game, terminal_game.world.dungeon)

    archive_world(
        terminal_game.world,
        terminal_game.player_session,
        save_dir=save_dir,
        enable_gzip=True,
    )
    return terminal_game


###############################################################################################################################################
async def _next_dungeon_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> TCGGame:
    """从存档复位，进入下一关（and），并归档新状态。"""
    terminal_game = await _restore_game(world, player_session)

    if not terminal_game.current_combat_sequence.is_post_combat:
        logger.error("next-dungeon 只能在战斗结束后使用")
        return terminal_game

    if terminal_game.current_combat_sequence.is_lost:
        logger.info("英雄失败，应该返回营地")
        return terminal_game

    if not terminal_game.current_combat_sequence.is_won:
        assert False, "不可能出现的情况！"

    next_level = terminal_game.current_dungeon.peek_next_stage()
    if next_level is None:
        logger.info("没有下一关，你胜利了，应该返回营地")
        return terminal_game

    advance_to_next_stage(terminal_game, terminal_game.current_dungeon)
    await terminal_game.combat_pipeline.process()

    archive_world(
        terminal_game.world,
        terminal_game.player_session,
        save_dir=save_dir,
        enable_gzip=True,
    )
    return terminal_game


###############################################################################################################################################
async def _retreat_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> TCGGame:
    """从存档复位，执行撤退（rtt），并归档新状态。"""
    terminal_game = await _restore_game(world, player_session)

    if not terminal_game.current_combat_sequence.is_ongoing:
        logger.error("retreat 只能在战斗进行中使用")
        return terminal_game

    success, message = mark_expedition_retreat(terminal_game)
    if not success:
        logger.error(f"撤退失败: {message}")
        return terminal_game

    logger.info(f"撤退成功: {message}")

    await terminal_game.combat_pipeline.execute()
    complete_dungeon_and_return_home(terminal_game, terminal_game.world.dungeon)

    archive_world(
        terminal_game.world,
        terminal_game.player_session,
        save_dir=save_dir,
        enable_gzip=True,
    )
    return terminal_game


###############################################################################################################################################
@click.group()
def main() -> None:
    pass


###############################################################################################################################################
@main.command("new")
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
def new_game(user: str, game: str) -> None:
    """创建并初始化一个新的游戏实例。"""

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
    setup_logger(_log_file)

    if user is None:
        user = f"cli-player-{_timestamp}"

    _save_dir = WORLDS_DIR / user / game / _timestamp
    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(_create_and_initialize_game(user, game, _save_dir))


###############################################################################################################################################
@main.command("advance")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径（如 .worlds/玩家名/Game1/2026-03-12_12-53-25）",
)
def advance(snapshot: str) -> None:
    """从存档复位游戏，执行一轮家园推进，并写入新存档。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
    setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(_advance_game(world, player_session, _save_dir))


###############################################################################################################################################
@main.command("speak")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--target",
    required=True,
    help="对话目标角色名（如 角色.术士.云音）",
)
@click.option(
    "--content",
    required=True,
    help="对话内容",
)
def speak(snapshot: str, target: str, content: str) -> None:
    """从存档复位，与 NPC 对话，并写入新存档。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
    setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(_speak_game(world, player_session, target, content, _save_dir))


###############################################################################################################################################
@main.command("switch-stage")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--stage",
    required=True,
    help="目标场景名（如 场景.云音居所）",
)
def switch_stage(snapshot: str, stage: str) -> None:
    """从存档复位，切换玩家场景，并写入新存档。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
    setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(_switch_stage_game(world, player_session, stage, _save_dir))


###############################################################################################################################################
@main.command("enter-dungeon")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def enter_dungeon(snapshot: str) -> None:
    """从存档复位，进入地下城，并写入新存档。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
    setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(_enter_dungeon_game(world, player_session, _save_dir))


###############################################################################################################################################
@main.command("draw-cards")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def draw_cards(snapshot: str) -> None:
    """从存档复位，为所有角色随机抽牌（dc），并写入新存档。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
    setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(_draw_cards_game(world, player_session, _save_dir))


###############################################################################################################################################
@main.command("play-cards")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def play_cards(snapshot: str) -> None:
    """从存档复位，执行打牌（pc），并写入新存档。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
    setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(_play_cards_game(world, player_session, _save_dir))


###############################################################################################################################################
@main.command("trans-home")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def trans_home(snapshot: str) -> None:
    """从存档复位，返回家园（th），并写入新存档。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
    setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(_trans_home_game(world, player_session, _save_dir))


###############################################################################################################################################
@main.command("next-dungeon")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def next_dungeon(snapshot: str) -> None:
    """从存档复位，进入下一关（and），并写入新存档。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
    setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(_next_dungeon_game(world, player_session, _save_dir))


###############################################################################################################################################
@main.command("retreat")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def retreat(snapshot: str) -> None:
    """从存档复位，执行撤退（rtt），并写入新存档。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
    setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(_retreat_game(world, player_session, _save_dir))


###############################################################################################################################################
if __name__ == "__main__":
    main()
