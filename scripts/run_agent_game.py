"""AI 操作工具 —— 基于快照的无状态游戏推进 CLI。

每条命令 = 读快照 → 执行动作 → 写新快照。命令间无持久内存，状态全在 .worlds/ 中。
存档位置：.worlds/{user}/{game}/{timestamp}/（含 world.json / player_session.json）
查存档：find .worlds -mindepth 3 -maxdepth 3 -type d | sort
日志：logs/run_agent_game_{timestamp}.log

==== 家园模式命令 ====
  new             --game GAME --dungeon DUNGEON [--user NAME]   创建新游戏
  stages          --snapshot PATH                                列出场景-角色映射（只读）
  advance         --snapshot PATH --actors A [--actors B ...]   推进一轮剧情
  speak           --snapshot PATH --target NPC --content TEXT    与 NPC 对话
  switch-stage    --snapshot PATH --stage STAGE                  切换场景
  generate-dungeon --snapshot PATH                               LLM 动态生成副本
  roster          --snapshot PATH                                查看远征队名单（只读）
  roster-add      --snapshot PATH --member NPC                  添加远征队成员
  roster-remove   --snapshot PATH --member NPC                  移除远征队成员
  storage-to-inventory  --snapshot PATH --item ITEM             储物箱→随身背包
  inventory-to-storage  --snapshot PATH --item ITEM             随身背包→储物箱
  wear-costume    --snapshot PATH --item ITEM --target ACTOR    穿时装
  remove-costume  --snapshot PATH --target ACTOR                脱时装
  craft-item      --snapshot PATH --materials M1 [--materials M2 ...]  合成消耗品
  craft-gear      --snapshot PATH --materials M1 [--materials M2 ...]  锻造装备
  craft-costume   --snapshot PATH --materials M1 [--materials M2 ...]  制作时装
  enter-dungeon   --snapshot PATH --dungeon NAME                进入副本第一关 → 副本模式

==== 副本模式命令 ====
  draw-cards      --snapshot PATH                               全员抽牌
  play-cards-specified --snapshot PATH --actor A --card C [--targets T...]  指定角色出牌（怪物 AI 自动出牌）
  pass-turn       --snapshot PATH --actor A                     跳过出牌
  use-consumable  --snapshot PATH --actor A --item I [--targets T...]  使用消耗品
  use-gear        --snapshot PATH --actor A --item I [--targets T...]  装备 GearItem
  retreat         --snapshot PATH                               主动撤退（失败） → 家园模式
  collect-loot    --snapshot PATH                               收战利品（胜利后）
  next-dungeon    --snapshot PATH                               下一关（胜利后，需存在下一关）
  exit-dungeon    --snapshot PATH                               退出副本 → 家园模式（无论胜负）

==== 典型流程 ====
  家园：new → stages → advance(循环) / speak / switch-stage → enter-dungeon
  副本：enter-dungeon → draw-cards → play-cards-specified(循环至战斗结束)
        胜利 → collect-loot → next-dungeon 或 exit-dungeon
        失败 → exit-dungeon
        战斗中途撤退 → retreat"""

import os
import sys

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)
# 将 scripts 目录添加到模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
import datetime
import sys
import click
from loguru import logger
from ai_rpg.game.config import (
    WORLDS_DIR,
)
from config import LOGS_DIR
from ai_rpg.game import restore_world
from pathlib import Path
from typing import Final as _Final

# 仅在本 CLI 运行时启用 chat dump（调试用途）
import ai_rpg.deepseek.config

ai_rpg.deepseek.config.CHAT_DUMP_ENABLED = True

LOG_LEVEL: _Final[str] = "DEBUG"


def _setup_logger(log_file_path: Path) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    logger.add(log_file_path, level=LOG_LEVEL)
    logger.info(f"日志配置: 级别={LOG_LEVEL}, 文件路径={log_file_path}")


from agent_game_core import create_and_initialize_game
from agent_game_home import (
    advance_game,
    speak_game,
    switch_stage_game,
    enter_dungeon_game,
    generate_dungeon_game,
    stages_game,
)
from agent_game_combat import (
    draw_cards_game,
    play_cards_specified_game,
    pass_turn_game,
    use_consumable_game,
    use_gear_game,
    exit_dungeon_and_return_home_game,
    next_dungeon_game,
    retreat_game,
    collect_loot_game,
)
from agent_game_inventory import (
    add_party_member_game,
    remove_party_member_game,
    get_party_roster_game,
    move_item_to_inventory_game,
    move_item_to_storage_game,
    wear_costume_game,
    remove_costume_game,
    craft_consumable_game,
    craft_gear_item_game,
    craft_costume_game,
)


###############################################################################################################################################
@click.group()
def main() -> None:
    """AI 操作工具：基于快照驱动游戏推进。

    每条子命令读取一个存档快照，执行一次游戏动作，写出新的存档快照。
    查看可用存档：find .worlds -mindepth 3 -maxdepth 3 -type d | sort
    """


###############################################################################################################################################
@main.command("new")
@click.option(
    "--user",
    default=None,
    help="玩家用户名。默认为带时间戳的随机名称。",
)
@click.option(
    "--game",
    required=True,
    help="游戏名称（对应 BLUEPRINTS_DIR 下的文件名，如 Game1）。",
)
@click.option(
    "--dungeon",
    required=True,
    help="副本名称（对应 DUNGEONS_DIR 下的文件名，如 Dungeon1）。",
)
def new_game(user: str, game: str, dungeon: str) -> None:
    """创建新游戏实例并写入初始存档。执行后处于家园模式。"""

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    if user is None:
        user = f"cli-player-{_timestamp}"

    _save_dir = WORLDS_DIR / user / game / _timestamp
    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(create_and_initialize_game(user, game, dungeon, _save_dir))


###############################################################################################################################################
@main.command("stages")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def stages(snapshot: str) -> None:
    """打印各场景内角色名单（只读，不写新存档）。advance 前用于确认 --actors 参数。"""
    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")

    mapping = asyncio.run(stages_game(world, player_session))
    for stage_name, actor_names in mapping.items():
        click.echo(f"{stage_name}: {', '.join(actor_names)}")


###############################################################################################################################################
@main.command("advance")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径（如 .worlds/玩家名/Game1/2026-03-12_12-53-25）",
)
@click.option(
    "--actors",
    multiple=True,
    required=True,
    help="本轮需要真正触发行动规划的角色全名，可重复使用（如 --actors 术士.云音 --actors 旅行者.无名氏）。"
    "调用前建议先用 stages --snapshot PATH 查询当前场景内的角色名单。",
)
def advance(snapshot: str, actors: tuple[str, ...]) -> None:
    """推进一轮家园剧情，仅为 --actors 指定角色激活行动规划并归档。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(advance_game(world, player_session, list(actors), _save_dir))


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
    help="对话目标角色名（如 术士.云音）",
)
@click.option(
    "--content",
    required=True,
    help="对话内容",
)
def speak(snapshot: str, target: str, content: str) -> None:
    """玩家向指定 NPC 说话并归档。需处于家园模式。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(speak_game(world, player_session, target, content, _save_dir))


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
    """玩家切换到指定场景并归档。需处于家园模式。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(switch_stage_game(world, player_session, stage, _save_dir))


###############################################################################################################################################
@main.command("enter-dungeon")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--dungeon",
    required=True,
    help="副本名称（对应 DUNGEONS_DIR 下的 JSON 文件名，如 Dungeon1）",
)
def enter_dungeon(snapshot: str, dungeon: str) -> None:
    """进入指定副本第一关并归档。执行后进入副本模式，下一步用 draw-cards。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(enter_dungeon_game(world, player_session, dungeon, _save_dir))


###############################################################################################################################################
@main.command("draw-cards")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def draw_cards(snapshot: str) -> None:
    """全员抽牌并归档。需战斗进行中，下一步用 play-cards-specified。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(draw_cards_game(world, player_session, _save_dir))


###############################################################################################################################################
@main.command("play-cards-specified")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--actor",
    required=True,
    help="出牌角色全名（如 旅行者.无名氏）",
)
@click.option(
    "--card",
    required=True,
    help="要打出的卡牌名称（须存在于该角色手牌中）",
)
@click.option(
    "--targets",
    multiple=True,
    default=(),
    help="目标角色名，可重复使用（如 --targets 怪物.野猪）",
)
def play_cards_specified(
    snapshot: str, actor: str, card: str, targets: tuple[str, ...]
) -> None:
    """指定角色出牌（怪物则由 AI 自动出牌）并归档。需战斗进行中且 draw-cards 之后。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(
        play_cards_specified_game(
            world, player_session, actor, card, list(targets), _save_dir
        )
    )


###############################################################################################################################################
@main.command("pass-turn")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--actor",
    required=True,
    help="过牌角色全名（如 旅行者.无名氏）",
)
def pass_turn(snapshot: str, actor: str) -> None:
    """指定角色跳过出牌并归档。需战斗进行中。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(pass_turn_game(world, player_session, actor, _save_dir))


###############################################################################################################################################
@main.command("use-consumable")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--actor",
    required=True,
    help="使用消耗品的角色全名（如 旅行者.无名氏）",
)
@click.option(
    "--item",
    required=True,
    help="要使用的消耗品名称（须存在于该角色背包中）",
)
@click.option(
    "--targets",
    multiple=True,
    default=(),
    help="目标角色名，可重复使用（如 --targets 怪物.野猪）；SELF 时可省略，ALL/SPREAD 时需提供恰好 1 个目标作为阵营锚点",
)
def use_consumable(
    snapshot: str, actor: str, item: str, targets: tuple[str, ...]
) -> None:
    """指定角色使用消耗品并归档。需战斗进行中。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(
        use_consumable_game(
            world, player_session, actor, item, list(targets), _save_dir
        )
    )


###############################################################################################################################################
@main.command("use-gear")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--actor",
    required=True,
    help="使用装备的角色全名（如 旅行者.无名氏）",
)
@click.option(
    "--item",
    required=True,
    help="要装备的道具名称（须存在于该角色背包中，类型为 GearItem）",
)
@click.option(
    "--targets",
    multiple=True,
    default=(),
    help="目标角色名，可重复使用（如 --targets 盟友.云音）；SINGLE 时指定一个目标，敌我皆可",
)
def use_gear(snapshot: str, actor: str, item: str, targets: tuple[str, ...]) -> None:
    """指定角色装备 GearItem 并归档。需战斗进行中。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(
        use_gear_game(world, player_session, actor, item, list(targets), _save_dir)
    )


###############################################################################################################################################
@main.command("exit-dungeon")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def exit_dungeon(snapshot: str) -> None:
    """退出副本返回家园并归档。需战斗已结束（无论胜负）。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(exit_dungeon_and_return_home_game(world, player_session, _save_dir))


###############################################################################################################################################
@main.command("next-dungeon")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def next_dungeon(snapshot: str) -> None:
    """进入副本下一关并归档。需前一关已胜利且存在下一关。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(next_dungeon_game(world, player_session, _save_dir))


###############################################################################################################################################
@main.command("collect-loot")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def collect_loot(snapshot: str) -> None:
    """收取战利品至随身背包并归档。无战利品时不归档。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(collect_loot_game(world, player_session, _save_dir))


###############################################################################################################################################
@main.command("generate-dungeon")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def generate_dungeon_cmd(snapshot: str) -> None:
    """LLM 动态生成副本并归档。需处于家园模式。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(generate_dungeon_game(world, player_session, _save_dir))


###############################################################################################################################################
@main.command("roster-add")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--member",
    required=True,
    help="要加入远征队的盟友角色名称",
)
def roster_add(snapshot: str, member: str) -> None:
    """将指定盟友加入远征队名单并归档。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(add_party_member_game(world, player_session, member, _save_dir))


###############################################################################################################################################
@main.command("roster-remove")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--member",
    required=True,
    help="要移除的盟友角色名称",
)
def roster_remove(snapshot: str, member: str) -> None:
    """将指定盟友从远征队名单移除并归档。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(remove_party_member_game(world, player_session, member, _save_dir))


###############################################################################################################################################
@main.command("roster")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def roster(snapshot: str) -> None:
    """打印远征队名单（只读，不归档）。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")

    members = asyncio.run(get_party_roster_game(world, player_session))
    if members:
        click.echo("\n远征队当前名单：")
        for m in members:
            click.echo(f"  - {m}")
    else:
        click.echo("（名单为空，玩家将独自冒险）")


###############################################################################################################################################
@main.command("retreat")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def retreat(snapshot: str) -> None:
    """主动撤退（视为失败）并归档。需战斗进行中。"""

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(retreat_game(world, player_session, _save_dir))


###############################################################################################################################################
@main.command("storage-to-inventory")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--item",
    required=True,
    help="要从储物箱取出的道具名称（精确匹配）",
)
def storage_to_inventory(snapshot: str, item: str) -> None:
    """将指定道具从储物箱移入随身背包并归档。"""
    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(move_item_to_inventory_game(world, player_session, item, _save_dir))


###############################################################################################################################################
@main.command("inventory-to-storage")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--item",
    required=True,
    help="要从随身背包存回的道具名称（精确匹配）",
)
def inventory_to_storage(snapshot: str, item: str) -> None:
    """将指定道具从随身背包移回储物箱并归档。"""
    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(move_item_to_storage_game(world, player_session, item, _save_dir))


###############################################################################################################################################
@main.command("wear-costume")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--item",
    required=True,
    help="时装名称（精确匹配 CostumeItem.name）",
)
@click.option(
    "--target",
    required=True,
    help="目标角色全名（如 学者.寒蝉；若作用于自己则传入玩家全名，如 旅行者.无名氏）",
)
def wear_costume(snapshot: str, item: str, target: str) -> None:
    """为指定角色穿装并归档。需处于家园模式。"""
    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(wear_costume_game(world, player_session, item, _save_dir, target))


###############################################################################################################################################
@main.command("remove-costume")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--target",
    required=True,
    help="目标角色全名（如 学者.寒蝉；若作用于自己则传入玩家全名，如 旅行者.无名氏）",
)
def remove_costume(snapshot: str, target: str) -> None:
    """移除指定角色的时装并归档。需处于家园模式。"""
    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(remove_costume_game(world, player_session, _save_dir, target))


###############################################################################################################################################
@main.command("craft-item")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--materials",
    multiple=True,
    required=True,
    help="参与合成的材料名称，可重复使用（如 --materials 材料.草药.薄荷 --materials 材料.矿石.铁粉）",
)
def craft_item(snapshot: str, materials: tuple[str, ...]) -> None:
    """使用储物箱材料合成消耗品并归档。需处于家园模式。"""
    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(
        craft_consumable_game(world, player_session, list(materials), _save_dir)
    )


###############################################################################################################################################
@main.command("craft-gear")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--materials",
    multiple=True,
    required=True,
    help="参与锻造的材料名称，可重复使用（如 --materials 材料.遗迹铁片 --materials 材料.硬化兽骨）",
)
def craft_gear(snapshot: str, materials: tuple[str, ...]) -> None:
    """使用储物箱材料锻造装备并归档。需处于家园模式。"""
    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(craft_gear_item_game(world, player_session, list(materials), _save_dir))


###############################################################################################################################################
@main.command("craft-costume")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--materials",
    multiple=True,
    required=True,
    help="参与制作的材料名称，可重复使用（如 --materials 材料.丝质布料 --materials 材料.金线刺绣）",
)
def craft_costume(snapshot: str, materials: tuple[str, ...]) -> None:
    """使用储物箱材料制作时装并归档。需处于家园模式。"""
    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_agent_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(craft_costume_game(world, player_session, list(materials), _save_dir))


###############################################################################################################################################
if __name__ == "__main__":
    main()
