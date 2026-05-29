"""AI 操作工具 - 基于快照的游戏推进 CLI。

本脚本是供 AI（GitHub Copilot）主动调用的游戏操作工具。
人类玩家使用 run_tui_game_client.py（交互式终端），AI 使用本脚本（无状态快照驱动）。

核心设计：
    每条命令 = 读取一个存档快照 → 执行一次游戏动作 → 写出新的存档快照。
    命令之间没有持久内存；所有状态都保存在 .worlds/ 目录的快照文件中。

存档目录结构：
    .worlds/{username}/{game}/{timestamp}/
        world.json          # 世界实体序列化
        player_session.json # 玩家会话
        entities/           # 实体调试输出
        contexts/           # Agent 上下文调试输出
        dungeon/            # 地下城调试输出
        snapshot/snapshot.zip  # gzip 快照（可选）

查看可用存档：
    find .worlds -mindepth 3 -maxdepth 3 -type d | sort

游戏状态机（两种模式）：
    【家园模式 Home】玩家在某个 HomeComponent 场景中
        可用命令：new / advance / speak / switch-stage / enter-dungeon
    【地下城模式 Dungeon】玩家在某个地下城场景中
        可用命令：draw-cards / play-cards / exit-dungeon / next-dungeon / retreat

典型家园流程：
    new  →  advance（循环推进 NPC）
         →  speak --target <角色> --content <内容>
         →  switch-stage --stage <场景名>
         →  enter-dungeon  →【进入地下城模式】

典型地下城流程（每关）：
    enter-dungeon  →  draw-cards（抽牌）→  play-cards（打牌/结算）
    若战斗未结束（is_ongoing）：继续 draw-cards → play-cards
    战斗结束后（is_post_combat）：
        is_won + 有下一关 → next-dungeon → 继续战斗
        is_won + 无下一关 → exit-dungeon
        is_lost           → exit-dungeon
        主动撤退（战斗中）→ retreat

命令速查表：
    python scripts/run_agent_game.py new [--user NAME] [--game GAME] [--dungeon DUNGEON]
    python scripts/run_agent_game.py advance           --snapshot PATH
    python scripts/run_agent_game.py speak             --snapshot PATH --target ACTOR --content TEXT
    python scripts/run_agent_game.py switch-stage      --snapshot PATH --stage STAGE_NAME
    python scripts/run_agent_game.py equip-item        --snapshot PATH [--weapon ITEM] [--armor ITEM] [--accessory ITEM]
    python scripts/run_agent_game.py craft-item        --snapshot PATH --materials 材料1 [--materials 材料2 ...]
    python scripts/run_agent_game.py enter-dungeon     --snapshot PATH --dungeon DUNGEON_NAME
    python scripts/run_agent_game.py draw-cards        --snapshot PATH
    python scripts/run_agent_game.py play-cards-specified --snapshot PATH --actor ACTOR --card CARD [--targets TARGET...]
    python scripts/run_agent_game.py exit-dungeon      --snapshot PATH
    python scripts/run_agent_game.py next-dungeon      --snapshot PATH
    python scripts/run_agent_game.py retreat           --snapshot PATH

日志文件：logs/run_agent_game_{timestamp}.log（与新存档时间戳相同）"""

import os
import sys
from typing import Final

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
    GAME_1,
    WORLDS_DIR,
)
from config import LOGS_DIR
from ai_rpg.game import restore_world
from pathlib import Path
from typing import Final as _Final

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


from agent_game_actions import (
    create_and_initialize_game,
    advance_game,
    speak_game,
    switch_stage_game,
    enter_dungeon_game,
    draw_cards_game,
    play_cards_specified_game,
    pass_turn_game,
    exit_dungeon_and_return_home_game,
    next_dungeon_game,
    retreat_game,
    generate_dungeon_game,
    add_party_member_game,
    remove_party_member_game,
    get_party_roster_game,
    move_item_to_inventory_game,
    move_item_to_storage_game,
)

###########################################################################################################################################
# 默认地下城名称
DUNGEON_1: Final[str] = "Dungeon1"


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
    default=GAME_1,
    show_default=True,
    help="游戏名称（对应 BLUEPRINTS_DIR 下的文件名，如 Game1）。",
)
@click.option(
    "--dungeon",
    default=DUNGEON_1,
    show_default=True,
    help="地下城名称（对应 DUNGEONS_DIR 下的文件名，如 Dungeon1）。",
)
def new_game(user: str, game: str, dungeon: str) -> None:
    """创建并初始化一个新的游戏实例，写出初始存档。

    从 BLUEPRINTS_DIR/{game}.json 加载世界蓝图，从 DUNGEONS_DIR/{dungeon}.json 加载地下城，
    完成 build_from_blueprint / initialize，并将初始状态归档。
    归档路径：.worlds/{user}/{game}/{timestamp}/

    执行后游戏处于【家园模式】，可继续使用 advance / speak / switch-stage / enter-dungeon。
    """

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
@main.command("advance")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径（如 .worlds/玩家名/Game1/2026-03-12_12-53-25）",
)
def advance(snapshot: str) -> None:
    """从存档复位游戏，执行一轮家园推进（NPC 行动），并写入新存档。

    等同于人类在终端输入 /ad。适用于【家园模式】。
    LLM 为场景内所有 NPC 生成行动，推进叙事。
    """

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

    asyncio.run(advance_game(world, player_session, _save_dir))


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
    """从存档复位，玩家向指定 NPC 说话，并写入新存档。

    等同于人类在终端输入 /speak --target=<角色> --content=<内容>。
    适用于【家园模式】，target 必须与玩家在同一场景。
    本次 pipeline NPC 不主动推理，仅响应对话。
    """

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
    """从存档复位，将玩家传送至指定场景，并写入新存档。

    等同于人类在终端输入 /switch_stage --stage=<场景名>。
    适用于【家园模式】，stage 必须为合法的 HomeComponent 场景名。
    """

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
    help="地下城名称（对应 DUNGEONS_DIR 下的 JSON 文件名，如 Dungeon1）",
)
def enter_dungeon(snapshot: str, dungeon: str) -> None:
    """从存档复位，启动地下城第一关，并写入新存档。

    等同于人类在终端输入 /ed。适用于【家园模式】。
    执行后进入【地下城模式】，战斗第一回合已创建。
    下一步应使用 draw-cards。
    """

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
    """从存档复位，为所有角色随机抽牌，并写入新存档。

    等同于人类在终端输入 /dc。适用于【地下城模式】战斗进行中（is_ongoing）。
    己方和敌方均随机选定本回合使用的技能牌。
    下一步应使用 play-cards。
    """

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
    help="出牌角色全名（如 角色.旅行者.无名氏）",
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
    help="目标角色名，可重复使用（如 --targets 角色.常物.野猪）",
)
def play_cards_specified(
    snapshot: str, actor: str, card: str, targets: tuple[str, ...]
) -> None:
    """从存档复位，让指定角色打出指定手牌，并写入新存档。

    适用于【地下城模式】战斗进行中（is_ongoing），draw-cards 之后调用。
    只有指定角色触发出牌结算，其他角色本次 pipeline 不出牌。
    --card 须与手牌中卡牌名称完全一致，否则报错不归档。
    """

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
    help="过牌角色全名（如 角色.旅行者.无名氏）",
)
def pass_turn(snapshot: str, actor: str) -> None:
    """从存档复位，让指定角色跳过本次出牌机会，并写入新存档。

    适用于【地下城模式】战斗进行中（is_ongoing），draw-cards 之后调用。
    指定角色消耗 1 点 energy，不打出任何卡牌，行动顺序推进至下一角色。
    """

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
@main.command("exit-dungeon")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def exit_dungeon(snapshot: str) -> None:
    """从存档复位，结束地下城并返回家园，并写入新存档。

    等同于人类在终端输入 /th。适用于【地下城模式】战斗结束后（is_post_combat）。
    无论胜负，完成恢复满血、清空状态效果、移出远征队后回到家园场景。
    执行后回到【家园模式】。
    """

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
    """从存档复位，进入地下城下一关，并写入新存档。

    等同于人类在终端输入 /and。适用于【地下城模式】胜利结算后（is_post_combat + is_won）。
    且地下城存在下一关（peek_next_stage() 不为 None）。
    执行后新关卡战斗初始化完成，下一步继续 draw-cards。
    若已是最后一关（peek_next_stage() 为 None），应使用 exit-dungeon。
    """

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
@main.command("generate-dungeon")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def generate_dungeon_cmd(snapshot: str) -> None:
    """从存档复位，调用 LLM 生成地下城文件并写入新存档。

    在家园模式下为玩家实体添加 GenerateDungeonAction，驱动 dungeon_generate_pipeline
    执行 GenerateDungeonActionSystem（Steps 1-4 文本数据）成功后自动触发 IllustrateDungeonActionSystem。
    适用于【家园模式】，执行结束后仍处于家园模式。
    """

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
    """从存档复位，将指定盟友加入远征队名单，并写入新存档。

    适用于【家园模式】。--member 必须为已存在的 NPC（NPCComponent）角色名称且不能为玩家自身。
    添加后可继续使用 enter-dungeon 进入地下城。
    """

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
    """从存档复位，将指定盟友从远征队名单移除，并写入新存档。

    适用于【家园模式】。--member 必须已在远征队名单中。
    """

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
    """从存档复位，打印当前远征队名单（只读，不写新存档）。

    输出格式：每行一个同伴名称。名单为空时输出"（名单为空，玩家将独自冒险）"。
    适用于任意模式。
    """

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
    """从存档复位，主动撤退并返回家园，并写入新存档。

    等同于人类在终端输入 /rtt。适用于【地下城模式】战斗进行中（is_ongoing）。
    标记远征队撤退 → 战斗以失败结算 → 恢复满血并返回家园。
    执行后回到【家园模式】，视为失败。
    """

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
    """从存档复位，将指定道具从玩家储物箱移入随身背包，并写入新存档。

    --item 必须精确匹配 StorageComponent.items 中的道具名称。道具对象本身被移动，不会复制。
    """
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
    """从存档复位，将指定道具从玩家随身背包移回储物箱，并写入新存档。

    --item 必须精确匹配 InventoryComponent.items 中的道具名称。道具对象本身被移动，不会复制。
    """
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
if __name__ == "__main__":
    main()
