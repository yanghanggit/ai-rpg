"""run_agent_game.py 的核心实现层。

本文件包含所有游戏动作的 async def 实现函数。
CLI 入口（click 命令）位于 run_agent_game.py，由其 import 本文件的所有符号。
日志初始化（_setup_logger）定义在 run_agent_game.py 入口处。

函数命名规则：
    create_and_initialize_game  — 创建新游戏（new 命令）
    _restore_game               — 从存档复位 TCGGame（各命令共享入口，仅内部使用）
    advance_game                — 家园推进（advance 命令）
    speak_game                  — 玩家对话（speak 命令）
    switch_stage_game           — 场景切换（switch-stage 命令）
    enter_dungeon_game          — 进入地下城（enter-dungeon 命令）
    draw_cards_game             — 抽牌（draw-cards 命令）
    play_cards_specified_game   — 指定角色出牌（play-cards-specified 命令）
    exit_dungeon_and_return_home_game — 退出地下城（exit-dungeon 命令）
    next_dungeon_game           — 进入下一关（next-dungeon 命令）
    retreat_game                — 主动撤退（retreat 命令）
    generate_dungeon_game       — 生成地下城（generate-dungeon 命令）
"""

import os
import sys

# 将 src 目录添加到模块搜索路径
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
)
# 将 scripts 目录添加到模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from ai_rpg.chat_client import DeepSeekClient
from ai_rpg.services import server_configuration
from ai_rpg.game.config import (
    BLUEPRINTS_DIR,
    DUNGEONS_DIR,
)
from ai_rpg.game.player_session import PlayerSession
from ai_rpg.game.tcg_game import TCGGame
from ai_rpg.image_client.client import ImageClient
from ai_rpg.models import Blueprint, CombatState, Dungeon, World, EnemyComponent
from ai_rpg.game import archive_world
from ai_rpg.services.home_actions import (
    activate_stage_plan,
    activate_speak_action,
    activate_switch_stage,
    activate_generate_dungeon,
    add_expedition_member,
    remove_expedition_member,
    get_expedition_roster,
)
from ai_rpg.services.dungeon_actions import (
    activate_all_card_draws,
    activate_play_cards_specified,
    activate_enemy_play_trigger,
    activate_expedition_retreat,
)
from ai_rpg.services.dungeon_lifecycle import (
    setup_dungeon,
    enter_dungeon_first_stage,
    advance_to_next_stage,
    exit_dungeon_and_return_home,
)
from pathlib import Path


###############################################################################
async def create_and_initialize_game(
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

    # 从 JSON 文件加载地下城；名称为空或文件不存在时使用空地下城占位
    dungeon_path = DUNGEONS_DIR / f"{dungeon_name}.json"
    if dungeon_name and dungeon_path.exists():
        dungeon = Dungeon.model_validate_json(dungeon_path.read_text(encoding="utf-8"))
    else:
        logger.warning(
            f"地下城文件未找到（dungeon_name={dungeon_name!r}），使用空地下城占位"
        )
        dungeon = Dungeon(name="", rooms=[], ecology="")

    world_data = World(
        entity_counter=1000,
        home_planning_turn_index=0,
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

    DeepSeekClient.setup()
    ImageClient.setup(server_configuration.replicate_image_generation_server_port)

    assert (
        len(terminal_game._world.entities_serialization) == 0
    ), "测试阶段，游戏中不应该有实体数据！"
    terminal_game.build_from_blueprint().flush_entities()

    await terminal_game.initialize()

    logger.info(
        f"游戏创建并初始化完成：user={user}, game={game}, dungeon={dungeon_name}"
    )

    # 并发检查图片服务
    await ImageClient.health_check()

    # 持久化游戏世界数据到存档目录，并启用 gzip 快照功能
    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
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
    DeepSeekClient.setup()
    ImageClient.setup(server_configuration.replicate_image_generation_server_port)
    terminal_game.restore_from_snapshot()
    await terminal_game.initialize()
    logger.info(f"游戏已从存档恢复：user={player_session.name}, game={game}")
    return terminal_game


###############################################################################
async def advance_game(
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

    await terminal_game._home_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def speak_game(
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

    await terminal_game._home_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def switch_stage_game(
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

    await terminal_game._home_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def enter_dungeon_game(
    world: World,
    player_session: PlayerSession,
    dungeon_name: str,
    save_dir: Path,
) -> TCGGame:
    """从存档复位，启动地下城第一关（等同于终端命令 /ed），并归档新状态。

    调用 setup_dungeon 从文件加载地下城、赋值并创建地下城实体，再调用 enter_dungeon_first_stage 将玩家和队友传送至第一关场景，
    创建首个 CombatSequence，然后驱动 combat_pipeline.process() 完成战斗初始化
    （场景描述生成、各角色初始状态效果生成、创建第一回合及行动顺序）。

    执行后游戏进入【地下城模式】，后续应使用 draw-cards → play-cards 流程。

    前置条件：玩家必须处于家园模式。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        dungeon_name: 地下城名称（对应 DUNGEONS_DIR 下的 JSON 文件名）。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 TCGGame 实例（已归档）；失败时提前返回未归档实例。
    """
    terminal_game = await _restore_game(world, player_session)

    success, error_detail = setup_dungeon(terminal_game, dungeon_name)
    if not success:
        logger.error(f"地下城实体创建失败: {error_detail}")
        return terminal_game

    success, error_detail = enter_dungeon_first_stage(
        terminal_game, terminal_game.current_dungeon
    )
    if not success:
        logger.error(f"进入地下城第一关失败: {error_detail}")
        return terminal_game

    assert (
        terminal_game.current_dungeon.current_room is not None
    ), "当前尚未进入任何房间"
    assert (
        terminal_game.current_dungeon.current_room.combat.state != CombatState.NONE
    ), "没有战斗可以进行"
    await terminal_game._combat_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def draw_cards_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> TCGGame:
    """从存档复位，为所有角色随机抽牌（等同于终端命令 /dc），并归档新状态。

    调用 activate_all_card_draws 为所有战斗角色（己方 + 敌方）激活抽牌动作，
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

    if not terminal_game.current_dungeon.is_ongoing:
        logger.error("draw-cards 只能在战斗进行中使用")
        return terminal_game

    success, message = activate_all_card_draws(terminal_game)
    if not success:
        logger.error(f"激活全员抽牌失败: {message}")
        return terminal_game

    await terminal_game._combat_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def play_cards_specified_game(
    world: World,
    player_session: PlayerSession,
    actor: str,
    card: str,
    targets: list[str],
    save_dir: Path,
) -> TCGGame:
    """从存档复位，让指定角色打出指定手牌，并归档新状态。

    只有指定角色触发 PlayCardsAction；其他角色本次 pipeline 不出牌。
    若角色名或卡牌名不合法，提前返回不归档。

    前置条件：
        - combat_sequence.is_ongoing 为 True（战斗进行中）
        - latest_round.is_round_completed 为 False（当前回合未完成）

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        actor: 出牌角色全名（如 角色.旅行者.无名氏）。
        card: 要打出的卡牌名称（须存在于该角色手牌中）。
        targets: 目标名称列表，可为空。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 TCGGame 实例（已归档）；前置条件不满足时提前返回未归档实例。
    """
    terminal_game = await _restore_game(world, player_session)

    if not terminal_game.current_dungeon.is_ongoing:
        logger.error("play-cards-specified 只能在战斗进行中使用")
        return terminal_game

    last_round = terminal_game.current_dungeon.latest_round
    if last_round is None or last_round.is_round_completed:
        logger.error("play-cards-specified 当前没有未完成的回合可供打牌")
        return terminal_game

    actor_entity = terminal_game.get_actor_entity(actor)
    if actor_entity is not None and actor_entity.has(EnemyComponent):
        success, message = activate_enemy_play_trigger(terminal_game, actor)
    else:
        success, message = activate_play_cards_specified(
            terminal_game, actor, card, list(targets)
        )
    if not success:
        logger.error(f"play-cards-specified 失败: {message}")
        return terminal_game

    await terminal_game._combat_pipeline.process()

    if terminal_game.current_dungeon.is_post_combat:
        logger.debug("在本次处理中战斗已结束，进入后处理阶段")

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def exit_dungeon_and_return_home_game(
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
    if not terminal_game.current_dungeon.is_post_combat:
        logger.error("exit-dungeon 只能在战斗结束后使用")
        return terminal_game

    # 执行退出地下城流程，返回家园
    exit_dungeon_and_return_home(terminal_game, terminal_game._world.dungeon)

    # 最后归档
    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )

    # 返回
    return terminal_game


###############################################################################
async def next_dungeon_game(
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

    if not terminal_game.current_dungeon.is_post_combat:
        logger.error("next-dungeon 只能在战斗结束后使用")
        return terminal_game

    if terminal_game.current_dungeon.is_lost:
        logger.info("英雄失败，应该返回营地")
        return terminal_game

    if not terminal_game.current_dungeon.is_won:
        assert False, "不可能出现的情况！"

    next_level = terminal_game.current_dungeon.peek_next_stage()
    if next_level is None:
        logger.info("没有下一关，你胜利了，应该返回营地")
        return terminal_game

    advance_to_next_stage(terminal_game, terminal_game.current_dungeon)
    await terminal_game._combat_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def retreat_game(
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
    if not terminal_game.current_dungeon.is_ongoing:
        logger.error("retreat 只能在战斗进行中使用")
        return terminal_game

    # 标记撤退意图并正常走一遍战斗流程，让 RetreatActionSystem 和 CombatOutcomeSystem 处理后续结算（失败）
    success, message = activate_expedition_retreat(terminal_game)
    if not success:
        logger.error(f"撤退失败: {message}")
        return terminal_game

    logger.info(f"撤退动作激活成功: {message}")

    await terminal_game._combat_pipeline.execute()

    # 最后归档
    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )

    # 返回
    return terminal_game


###############################################################################
async def generate_dungeon_game(
    world: World,
    player_session: PlayerSession,
    save_dir: Path,
) -> TCGGame:
    """从存档复位，激活地下城生成动作并执行 dungeon_generate_pipeline，并归档新状态。

    调用 activate_generate_dungeon 为玩家实体添加 GenerateDungeonAction，
    然后驱动 _dungeon_generate_pipeline.process() 触发 GenerateDungeonActionSystem
    执行地下城文本数据生成流程（Steps 1-4），成功后自动触发 IllustrateDungeonActionSystem。
    动作组件由 ActionCleanupSystem 在 pipeline 末端自动清除。

    前置条件：玩家必须处于家园模式（is_player_in_home_stage）。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 TCGGame 实例（已归档）；激活失败时提前返回未归档实例。
    """
    terminal_game = await _restore_game(world, player_session)

    success, error_detail = activate_generate_dungeon(terminal_game)
    if not success:
        logger.error(f"激活地下城创建失败: {error_detail}")
        return terminal_game

    await terminal_game._dungeon_generate_pipeline.process()

    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    return terminal_game


###############################################################################
async def add_expedition_member_game(
    world: World,
    player_session: PlayerSession,
    member_name: str,
    save_dir: Path,
) -> TCGGame:
    """从存档复位，将指定盟友加入远征队名单，并归档新状态。

    前置条件：玩家必须处于家园模式（is_player_in_home_stage）。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        member_name: 要加入名单的盟友角色名称。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 TCGGame 实例；操作失败时提前返回未归档实例。
    """
    terminal_game = await _restore_game(world, player_session)

    success, error_detail = add_expedition_member(terminal_game, member_name)
    if not success:
        logger.error(f"添加远征队成员失败: {error_detail}")
        return terminal_game

    terminal_game.flush_entities()
    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    logger.info(f"已将 {member_name} 加入远征队名单，存档: {save_dir}")
    return terminal_game


###############################################################################
async def remove_expedition_member_game(
    world: World,
    player_session: PlayerSession,
    member_name: str,
    save_dir: Path,
) -> TCGGame:
    """从存档复位，将指定盟友从远征队名单移除，并归档新状态。

    前置条件：玩家必须处于家园模式（is_player_in_home_stage）。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。
        member_name: 要移除的盟友角色名称。
        save_dir: 新存档写入目录。

    Returns:
        执行完毕后的 TCGGame 实例；操作失败时提前返回未归档实例。
    """
    terminal_game = await _restore_game(world, player_session)

    success, error_detail = remove_expedition_member(terminal_game, member_name)
    if not success:
        logger.error(f"移除远征队成员失败: {error_detail}")
        return terminal_game

    terminal_game.flush_entities()
    archive_world(
        terminal_game._world,
        terminal_game._player_session,
        save_dir=save_dir,
    )
    logger.info(f"已将 {member_name} 从远征队名单移除，存档: {save_dir}")
    return terminal_game


###############################################################################
async def get_expedition_roster_game(
    world: World,
    player_session: PlayerSession,
) -> list[str]:
    """从存档复位，返回当前远征队名单（只读，不写新存档）。

    Args:
        world: 由 restore_world() 反序列化的世界数据。
        player_session: 由 restore_world() 反序列化的玩家会话。

    Returns:
        远征队同伴名称列表（不含玩家自身）。
    """
    terminal_game = await _restore_game(world, player_session)
    return get_expedition_roster(terminal_game)
