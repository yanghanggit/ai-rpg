"""AI 操作工具 - 基于快照的游戏推进 CLI。

本脚本是供 AI（GitHub Copilot）主动调用的游戏操作工具。
人类玩家使用 run_terminal_game.py（交互式终端），AI 使用本脚本（无状态快照驱动）。

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
    python scripts/run_agent_game.py enter-dungeon     --snapshot PATH --dungeon DUNGEON_NAME
    python scripts/run_agent_game.py draw-cards        --snapshot PATH
    python scripts/run_agent_game.py play-cards-specified --snapshot PATH --actor ACTOR --card CARD [--targets TARGET...]
    python scripts/run_agent_game.py exit-dungeon      --snapshot PATH
    python scripts/run_agent_game.py next-dungeon      --snapshot PATH
    python scripts/run_agent_game.py retreat           --snapshot PATH

日志文件：logs/run_agent_game_{timestamp}.log（与新存档时间戳相同）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI 操作经验总结（供后续 AI 实例参考，勿删）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【陷阱 1】speak 之后 NPC 不会立即回应
    speak 命令只是"登记"玩家的发言意图，NPC 的回应在下一次 advance 中才生成。
    正确流程：
        speak --snapshot A --target 角色.术士.云音 --content "..."  → 存档 B
        advance --snapshot B                                         → 存档 C（云音在此回话）
    读取 NPC 回应内容：
        grep -A 20 "response_content" logs/run_agent_game_{C的时间戳}.log

【陷阱 2】选错存档导致命令静默失败或行为异常（高频陷阱！）
    每条命令对前置状态有严格要求，使用错误的存档会导致命令静默失败、不产生新存档，
    但日志中只会打印一行 ERROR，没有异常抛出——极易误判为"命令卡住"或"bug"。
    实际案例：打算从 BOSS 战存档撤退，却误传入了上一次已结算的存档，
              retreat 直接返回未归档实例，花费大量时间排查"场景未更新"的假 bug。

    操作前务必先确认存档状态（参见陷阱 4 的快速检查方法），再选择对应命令：
        家园模式存档  → advance / speak / switch-stage / enter-dungeon
        is_ongoing    → draw-cards / play-cards / retreat
        is_post_combat + is_won  → next-dungeon / exit-dungeon
        is_post_combat + is_lost → exit-dungeon

    快速确认最新存档：
        find .worlds -mindepth 3 -maxdepth 3 -type d | sort | tail -5

【陷阱 3】next-dungeon 无下一关时静默返回，不产生新存档
    若当前关卡已是最后一关（peek_next_stage() 返回 None），next-dungeon 不会报错，
    但也不会写出新存档——存档目录时间戳不会更新。
    判断是否有下一关：先尝试 next-dungeon；无新存档出现则说明已是末关，应用 exit-dungeon。

【陷阱 4】识别当前存档的游戏状态
    读取 world.json：实体结构为 {name, components:[{name, data}]}，不是平铺字段。
    快速查战斗状态（dungeon.rooms[0].combat.state）：
        0=NONE 1=INITIALIZATION 2=ONGOING 3=COMPLETE 4=POST_COMBAT
        python3 -c "import json; d=json.load(open('PATH/world.json')); \
        r=d['dungeon']['rooms'][0]['combat'] if d['dungeon']['rooms'] else {}; \
        print('state:', r.get('state'), 'result:', r.get('result'))"
    快速查玩家当前场景（components 数组方式）：
        python3 -c "import json; d=json.load(open('PATH/world.json')); \
        [print(e['name'], next((c['data'] for c in e['components'] if c['name']=='ActorComponent'),{}).get('current_stage','?')) \
        for e in d['entities_serialization'] if any(c['name']=='PlayerComponent' for c in e['components'])]"

【陷阱 5】exit-dungeon / retreat 后场景未更新（已修复）
    EpilogueSystem 在 pipeline 末端调用 flush_entities()，此时角色仍在地下城场景。
    随后 exit_dungeon_and_return_home() 仅更新内存，若不再次 flush_entities()，
    archive_world() 会写出旧的场景数据。
    修复：flush_entities() 已内置为 exit_dungeon_and_return_home() 的最后一步
    （见 dungeon_lifecycle.py），调用方无需额外处理。

【陷阱 6】play-cards-specified 每次只出一张牌
    每次调用仅让一个角色出牌并跑完整个 pipeline。
    一个回合内若有多个己方角色需要出牌，需依次调用，每次传入上一步产生的新存档。
    敌方 AI 出牌同理（需手动为每个敌方角色各调用一次）。

【陷阱 7】play-cards-specified 在战斗结束时需额外等待（CombatArchiveSystem）
    当最后一张牌打出导致战斗结束时，pipeline 内 CombatArchiveSystem 会为每个
    远征队成员调用 LLM 生成战斗总结并归档（COMPLETE→POST_COMBAT），耗时明显更长。
    归档完成后存档状态即为 is_post_combat，可直接使用 next-dungeon / exit-dungeon。

【最佳操作流程 - 完整测试一局】
    1. new --user ai-copilot --game Game1 --dungeon 地下城.XXX
    2. advance（NPC 主动行动，推进家园叙事）
    3. speak --target ... --content ...  → advance（读取 NPC 回应）
    4. switch-stage --stage 场景.X（可选，移动玩家位置）
    5. enter-dungeon --dungeon 地下城.XXX
    6. draw-cards → play-cards-specified（每个角色各一次，循环直到 is_post_combat）
    7a. 胜利且有下一关 → next-dungeon → 回到步骤 6
    7b. 胜利且无下一关 → exit-dungeon
    7c. 失败             → exit-dungeon
    7d. 主动撤退（需 is_ongoing 存档）→ retreat
    8. advance（回家后推进家园叙事，NPC 对冒险有反应）
"""

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
    _create_and_initialize_game,
    _advance_game,
    _speak_game,
    _switch_stage_game,
    _enter_dungeon_game,
    _draw_cards_game,
    _play_cards_specified_game,
    _exit_dungeon_and_return_home_game,
    _next_dungeon_game,
    _retreat_game,
    _generate_dungeon_game,
    _add_expedition_member_game,
    _remove_expedition_member_game,
    _get_expedition_roster_game,
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

    asyncio.run(_create_and_initialize_game(user, game, dungeon, _save_dir))


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

    asyncio.run(_switch_stage_game(world, player_session, stage, _save_dir))


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

    asyncio.run(_enter_dungeon_game(world, player_session, dungeon, _save_dir))


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

    asyncio.run(_draw_cards_game(world, player_session, _save_dir))


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
    help="出牌角色全名（如 角色.猎人.石坚）",
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
        _play_cards_specified_game(
            world, player_session, actor, card, list(targets), _save_dir
        )
    )


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

    asyncio.run(_exit_dungeon_and_return_home_game(world, player_session, _save_dir))


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

    asyncio.run(_next_dungeon_game(world, player_session, _save_dir))


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

    asyncio.run(_generate_dungeon_game(world, player_session, _save_dir))


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

    适用于【家园模式】。--member 必须为已存在的盟友（AllyComponent）角色名称且不能为玩家自身。
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

    asyncio.run(_add_expedition_member_game(world, player_session, member, _save_dir))


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

    asyncio.run(
        _remove_expedition_member_game(world, player_session, member, _save_dir)
    )


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

    members = asyncio.run(_get_expedition_roster_game(world, player_session))
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

    asyncio.run(_retreat_game(world, player_session, _save_dir))


###############################################################################################################################################
if __name__ == "__main__":
    main()
