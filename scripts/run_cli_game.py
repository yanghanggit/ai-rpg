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
    python scripts/run_cli_game.py new [--user NAME] [--game GAME]
    python scripts/run_cli_game.py advance      --snapshot PATH
    python scripts/run_cli_game.py speak        --snapshot PATH --target ACTOR --content TEXT
    python scripts/run_cli_game.py switch-stage --snapshot PATH --stage STAGE_NAME
    python scripts/run_cli_game.py enter-dungeon --snapshot PATH
    python scripts/run_cli_game.py draw-cards   --snapshot PATH
    python scripts/run_cli_game.py play-cards   --snapshot PATH
    python scripts/run_cli_game.py exit-dungeon   --snapshot PATH
    python scripts/run_cli_game.py next-dungeon --snapshot PATH
    python scripts/run_cli_game.py retreat      --snapshot PATH

日志文件：logs/run_cli_game_{timestamp}.log（与新存档时间戳相同）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AI 操作经验总结（供后续 AI 实例参考，勿删）
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【陷阱 1】speak 之后 NPC 不会立即回应
    speak 命令只是"登记"玩家的发言意图，NPC 的回应在下一次 advance 中才生成。
    正确流程：
        speak --snapshot A --target 角色.术士.云音 --content "..."  → 存档 B
        advance --snapshot B                                         → 存档 C（云音在此回话）
    读取 NPC 回应内容：
        grep -A 20 "response_content" logs/run_cli_game_{C的时间戳}.log

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
    通过 world.json 中各实体的 current_stage 字段判断状态：
    - 玩家/NPC 在家园场景（如 场景.石氏木屋、场景.猎人备物所）→ 家园模式
    - 玩家/NPC 在地下城场景（如 场景.山林边缘、场景.密林深处）→ 地下城模式
    快速查找玩家当前场景：
        python -c "import json; d=json.load(open('.worlds/USER/Game1/TIMESTAMP/world.json')); \
        [print(e['name'], e.get('ActorComponent',{}).get('current_stage','')) for e in d['entities_serialization']]"

【陷阱 5】exit-dungeon / retreat 后场景未更新（已修复）
    EpilogueSystem 在 pipeline 末端调用 flush_entities()，此时角色仍在地下城场景。
    随后 exit_dungeon_and_return_home() 仅更新内存，若不再次 flush_entities()，
    archive_world() 会写出旧的场景数据。
    修复：flush_entities() 已内置为 exit_dungeon_and_return_home() 的最后一步
    （见 dungeon_lifecycle.py），调用方无需额外处理。

【最佳操作流程 - 完整测试一局】
    1. new --user ai-copilot
    2. advance（NPC 主动行动，推进家园叙事）
    3. speak --target ... --content ...  → advance（读取 NPC 回应）
    4. switch-stage --stage 场景.X（可选，移动玩家位置）
    5. enter-dungeon
    6. draw-cards → play-cards（循环直到 is_post_combat）
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

import asyncio
import datetime
import click
from loguru import logger
from ai_rpg.chat_client.client import ChatClient
from ai_rpg.configuration import server_configuration
from ai_rpg.game.config import (
    BLUEPRINTS_DIR,
    DUNGEONS_DIR,
    GAME_1,
    LOGS_DIR,
    WORLDS_DIR,
)
from ai_rpg.game.player_session import PlayerSession
from ai_rpg.game.tcg_game import TCGGame
from ai_rpg.image_client.client import ImageClient
from ai_rpg.models import Blueprint, Dungeon, World
from ai_rpg.game import archive_world, restore_world
from ai_rpg.services.home_actions import (
    activate_stage_plan,
    activate_speak_action,
    activate_switch_stage,
)
from ai_rpg.services.dungeon_actions import (
    activate_random_expedition_member_card_draws,
    activate_specified_expedition_member_card_draws,
    activate_random_enemy_card_draws,
    activate_play_cards,
    activate_expedition_retreat,
)
from ai_rpg.services.dungeon_lifecycle import (
    initialize_dungeon_first_entry,
    advance_to_next_stage,
    exit_dungeon_and_return_home,
)
from pathlib import Path

###########################################################################################################################################
# 日志级别配置
LOG_LEVEL: Final[str] = "DEBUG"

###########################################################################################################################################
# 默认地下城名称
DUNGEON_1: Final[str] = "Dungeon1"


###############################################################################################################################################
def _setup_logger(log_file_path: Path) -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )
    logger.add(log_file_path, level=LOG_LEVEL)
    logger.info(f"日志配置: 级别={LOG_LEVEL}, 文件路径={log_file_path}")


###############################################################################################################################################
async def _create_and_initialize_game(
    user: str, game: str, dungeon_name: str, save_dir: Path
) -> TCGGame:
    """创建并初始化一个新游戏实例。

    从 BLUEPRINTS_DIR/{game}.json 加载蓝图，从 DUNGEONS_DIR/{dungeon_name}.json 加载地下城。

    Args:
        user: 玩家用户名
        game: 游戏名称（对应 BLUEPRINTS_DIR 下的文件名）
        dungeon_name: 地下城名称（对应 DUNGEONS_DIR 下的文件名）
        save_dir: 存档目录

    Returns:
        已初始化完成的 TCGGame 实例
    """
    # 从 JSON 文件加载蓝图
    blueprint_path = BLUEPRINTS_DIR / f"{game}.json"
    assert blueprint_path.exists(), f"蓝图文件不存在: {blueprint_path}"
    world_blueprint = Blueprint.model_validate_json(
        blueprint_path.read_text(encoding="utf-8")
    )
    assert world_blueprint is not None, "world blueprint 反序列化失败"

    # 从 JSON 文件加载地下城
    dungeon_path = DUNGEONS_DIR / f"{dungeon_name}.json"
    assert dungeon_path.exists(), f"地下城文件不存在: {dungeon_path}"
    dungeon = Dungeon.model_validate_json(dungeon_path.read_text(encoding="utf-8"))
    assert dungeon is not None, "dungeon 反序列化失败"

    world_data = World(
        entity_counter=1000,
        entities_serialization=[],
        agents_context={},
        dungeon=dungeon,
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

    logger.info(
        f"游戏创建并初始化完成：user={user}, game={game}, dungeon={dungeon_name}"
    )

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
    """从已还原的 World/PlayerSession 构造 TCGGame 并完成初始化。

    各命令的共享入口：先由命令层调用 restore_world(snapshot_path) 拿到
    (World, PlayerSession)，再传入本函数完成 TCGGame 的实体重建与服务初始化。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。

    Returns:
        已完成 restore_from_snapshot() + initialize() 的 TCGGame 实例，
        可直接调用 home_pipeline / combat_pipeline。
    """
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
    """从存档复位，执行一轮家园推进（等同于终端命令 /ad），并归档新状态。

    调用 activate_stage_plan 为玩家当前场景内所有 NPC 激活行动计划，
    然后驱动 home_pipeline.process() 完成本轮推理与叙事生成。

    前置条件：玩家必须处于家园模式（is_player_in_home_stage）。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        save_dir: 新存档写入目录（由命令层根据时间戳预先构造）。

    Returns:
        执行完毕后的 TCGGame 实例（已归档）。
    """
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
    """从存档复位，玩家向指定 NPC 说话（等同于终端命令 /speak），并归档新状态。

    调用 activate_speak_action 添加玩家说话行动，然后驱动 home_pipeline.process()。
    本次 pipeline 中 NPC 不进行主动推理，仅响应玩家的对话。

    前置条件：玩家必须处于家园模式，且 target 角色须与玩家在同一场景。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        target: 对话目标角色全名（如 "角色.术士.云音"）。
        content: 玩家说话内容。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 TCGGame 实例（已归档）；激活失败时提前返回未归档实例。
    """
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
    """从存档复位，玩家切换到指定场景（等同于终端命令 /switch_stage），并归档新状态。

    调用 activate_switch_stage 添加玩家场景转换行动，然后驱动 home_pipeline.process()。
    本次 pipeline 中 NPC 不进行主动推理，仅响应场景切换。

    前置条件：玩家必须处于家园模式，且 stage_name 须为合法的 HomeComponent 场景。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        stage_name: 目标场景全名（如 "场景.村中议事堂"）。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 TCGGame 实例（已归档）；激活失败时提前返回未归档实例。
    """
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
    """从存档复位，启动地下城第一关（等同于终端命令 /ed），并归档新状态。

    调用 initialize_dungeon_first_entry 将玩家和队友传送至地下城第一关场景，
    创建首个 CombatSequence，然后驱动 combat_pipeline.process() 完成战斗初始化
    （场景描述生成、各角色初始状态效果生成、创建第一回合及行动顺序）。

    执行后游戏进入【地下城模式】，后续应使用 draw-cards → play-cards 流程。

    前置条件：玩家必须处于家园模式，且地下城尚有未清理的关卡（stages 非空）。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 TCGGame 实例（已归档）；失败时提前返回未归档实例。
    """
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
    """从存档复位，为所有角色随机抽牌（等同于终端命令 /dc），并归档新状态。

    分别调用 activate_random_expedition_member_card_draws（己方）和
    activate_random_enemy_card_draws（敌方）为所有战斗角色随机选定本回合行动牌，
    然后驱动 combat_pipeline.process() 完成抽牌推理（各角色输出决策依据）。

    抽牌完成后，存档处于「已抽牌、待打牌」状态，下一步应调用 play-cards。

    前置条件：combat_sequence.is_ongoing 必须为 True（战斗进行中）。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 TCGGame 实例（已归档）；前置条件不满足时提前返回未归档实例。
    """
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
async def _draw_cards_specified_game(
    world: World,
    player_session: PlayerSession,
    member: str,
    targets: list[str],
    skill: str,
    status_effects: list[str],
    save_dir: Path,
) -> TCGGame:
    """从存档复位，为指定远征队成员设置精确抽牌，其余成员与敌方随机抽牌，并归档新状态。

    流程：
        1. activate_random_expedition_member_card_draws → 为所有己方随机抽牌（作为基础）
        2. activate_specified_expedition_member_card_draws → 覆盖指定成员的抽牌（精确技能/目标/状态）
        3. activate_random_enemy_card_draws → 为所有敌方随机抽牌
        4. combat_pipeline.process() → 完成抽牌推理（各角色输出决策依据）

    等同于终端先 /dc（全员随机抽）再由系统覆盖玩家手牌选择。
    下一步应使用 play-cards。

    前置条件：combat_sequence.is_ongoing 为 True（战斗进行中）。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        member: 要精确抽牌的远征队成员全名（如 "角色.猎人.石坚"）。
        targets: 指定的目标名称列表（如 ["角色.精怪.山魈"]）。
        skill: 指定的技能名称（须为该成员 SkillBookComponent 中已有的技能）。
        status_effects: 指定使用的状态效果名称列表，可为空（须为当前已有的状态效果）。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 TCGGame 实例（已归档）；前置条件不满足时提前返回未归档实例。
    """
    terminal_game = await _restore_game(world, player_session)

    if not terminal_game.current_combat_sequence.is_ongoing:
        logger.error("draw-cards-specified 只能在战斗进行中使用")
        return terminal_game

    # Step 1: 先为所有己方随机抽牌（确保非指定成员都有牌）
    success, message = activate_random_expedition_member_card_draws(terminal_game)
    if not success:
        logger.error(f"激活Ally随机抽牌失败: {message}")
        return terminal_game

    # Step 2: 覆盖指定成员的抽牌（精确技能/目标）
    success, message = activate_specified_expedition_member_card_draws(
        tcg_game=terminal_game,
        expedition_member_name=member,
        target_names=targets,
        skill_name=skill,
        status_effect_names=status_effects,
    )
    if not success:
        logger.error(f"激活指定抽牌失败: {message}")
        return terminal_game

    # Step 3: 敌方随机抽牌
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
    """从存档复位，执行打牌结算（等同于终端命令 /pc），并归档新状态。

    确保所有角色有后备牌后，调用 activate_play_cards 随机打出手中的牌，
    然后驱动 combat_pipeline.process() 完成伤害结算、叙事生成、状态效果评估、
    记忆归档，并判断战斗是否结束。

    若战斗在本轮结算中结束（is_post_combat），会在日志中输出提示。
    战斗结束后，后续可调用 exit-dungeon 或 next-dungeon。
    若战斗未结束（is_ongoing），可继续执行新一轮 draw-cards → play-cards。

    前置条件：
        - combat_sequence.is_ongoing 为 True（战斗进行中）
        - latest_round.is_round_completed 为 False（当前回合未完成）

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 TCGGame 实例（已归档）；前置条件不满足时提前返回未归档实例。
    """
    terminal_game = await _restore_game(world, player_session)

    if not terminal_game.current_combat_sequence.is_ongoing:
        logger.error("play-cards 只能在战斗进行中使用")
        return terminal_game

    last_round = terminal_game.current_combat_sequence.latest_round
    if last_round is None or last_round.is_round_completed:
        logger.error("play-cards 当前没有未完成的回合可供打牌")
        return terminal_game

    # 执行打牌行动（内部会自动确保所有角色都有后备牌）
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
async def _exit_dungeon_and_return_home_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> TCGGame:
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
        执行完毕后的 TCGGame 实例（已归档）；前置条件不满足时提前返回未归档实例。
    """
    terminal_game = await _restore_game(world, player_session)

    # 状态守卫：只能在战斗结束后使用
    if (
        len(terminal_game.current_combat_sequence.combats) == 0
        or not terminal_game.current_combat_sequence.is_post_combat
    ):
        logger.error("exit-dungeon 只能在战斗结束后使用")
        return terminal_game

    # 执行退出地下城流程，返回家园
    exit_dungeon_and_return_home(terminal_game, terminal_game.world.dungeon)

    # 最后归档
    archive_world(
        terminal_game.world,
        terminal_game.player_session,
        save_dir=save_dir,
        enable_gzip=True,
    )

    # 返回
    return terminal_game


###############################################################################################################################################
async def _next_dungeon_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> TCGGame:
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
        执行完毕后的 TCGGame 实例（已归档）；前置条件不满足时提前返回未归档实例。
    """
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
    """从存档复位，主动撤退（等同于终端命令 /rtt），并归档新状态。

    调用 activate_expedition_retreat 激活撤退动作，驱动 combat_pipeline.execute()
    让 RetreatActionSystem 和 CombatOutcomeSystem 正常走一遍（标记死亡和战斗失败），
    再调用 exit_dungeon_and_return_home 返回家园。
    撤退后游戏回到【家园模式】，视为失败结算。

    前置条件：combat_sequence.is_ongoing 必须为 True（只能在战斗进行中撤退）。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 TCGGame 实例（已归档）；前置条件不满足时提前返回未归档实例。
    """

    # 复位游戏状态
    terminal_game = await _restore_game(world, player_session)

    # 状态守卫：只能在战斗进行中撤退
    if not terminal_game.current_combat_sequence.is_ongoing:
        logger.error("retreat 只能在战斗进行中使用")
        return terminal_game

    # 标记撤退意图并正常走一遍战斗流程，让 RetreatActionSystem 和 CombatOutcomeSystem 处理后续结算（失败）
    success, message = activate_expedition_retreat(terminal_game)
    if not success:
        logger.error(f"撤退失败: {message}")
        return terminal_game

    logger.info(f"撤退动作激活成功: {message}")

    await terminal_game.combat_pipeline.execute()

    # 战斗结束后返回家园
    # exit_dungeon_and_return_home(terminal_game, terminal_game.world.dungeon)

    # 最后归档
    archive_world(
        terminal_game.world,
        terminal_game.player_session,
        save_dir=save_dir,
        enable_gzip=True,
    )

    # 返回
    return terminal_game


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
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
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
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
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
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
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
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
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
def enter_dungeon(snapshot: str) -> None:
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
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
    _setup_logger(_log_file)

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
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
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
@main.command("draw-cards-specified")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
@click.option(
    "--member",
    required=True,
    help="要精确抽牌的远征队成员全名（如 角色.猎人.石坚）",
)
@click.option(
    "--targets",
    required=True,
    multiple=True,
    help="目标角色全名，可多次指定（如 --targets 角色.精怪.山魈）",
)
@click.option(
    "--skill",
    required=True,
    help="使用的技能名称（须为该成员已有的技能）",
)
@click.option(
    "--status-effects",
    multiple=True,
    default=[],
    help="使用的状态效果名称，可多次指定，可为空",
)
def draw_cards_specified(
    snapshot: str,
    member: str,
    targets: tuple[str, ...],
    skill: str,
    status_effects: tuple[str, ...],
) -> None:
    """从存档复位，为指定成员精确抽牌，其余成员与敌方随机抽牌，并写入新存档。

    等同于人类在终端执行 /dc，但允许 AI 精确控制指定成员本回合使用的技能与目标。
    适用于【地下城模式】战斗进行中（is_ongoing）。
    下一步应使用 play-cards。
    """

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(
        _draw_cards_specified_game(
            world,
            player_session,
            member,
            list(targets),
            skill,
            list(status_effects),
            _save_dir,
        )
    )


###############################################################################################################################################
@main.command("play-cards")
@click.option(
    "--snapshot",
    required=True,
    help="存档目录路径",
)
def play_cards(snapshot: str) -> None:
    """从存档复位，结算本回合所有角色的战斗行动，并写入新存档。

    等同于人类在终端输入 /pc。适用于【地下城模式】战斗进行中（is_ongoing）。
    完成伤害结算、叙事生成、状态效果评估、战斗记忆归档。
    若战斗在本轮结束（is_post_combat），可继续使用 exit-dungeon 或 next-dungeon。
    若战斗未结束（is_ongoing），继续 draw-cards → play-cards。
    """

    snapshot_path = Path(snapshot)
    if not snapshot_path.exists():
        raise click.BadParameter(
            f"存档目录不存在：{snapshot_path}", param_hint="--snapshot"
        )

    _timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
    _setup_logger(_log_file)

    world, player_session = restore_world(snapshot_path)
    _save_dir = (
        WORLDS_DIR / player_session.name / str(world.blueprint.name) / _timestamp
    )

    logger.info(f"本次运行日志文件：{_log_file}")
    logger.info(f"读取存档：{snapshot_path}")
    logger.info(f"本次存档目录：{_save_dir}")

    asyncio.run(_play_cards_game(world, player_session, _save_dir))


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
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
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
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
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
    _log_file = LOGS_DIR / f"run_cli_game_{_timestamp}.log"
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
