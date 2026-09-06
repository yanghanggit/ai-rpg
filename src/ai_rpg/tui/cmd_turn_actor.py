"""回合行动命令：play / use / gear / pass / advance。

供 CombatTurnActorScreen 复用。所有改变性动作返回 TurnActionResult：
- ok: 是否成功
- text: 展示文本（成功结果 / 失败原因）
- transition: 非 None 表示需要「锁 input → 回车 → 切屏」，取值见下方常量。
"""

from dataclasses import dataclass
from itertools import zip_longest
from typing import List, Optional

from loguru import logger

from ..models import (
    CharacterStatsComponent,
    Combat,
    CombatResult,
    CombatRoom,
    CombatState,
    DeathComponent,
    EntitySerialization,
    compute_effective_stats,
)
from .app import GameClient
from .cmd_combat import (
    classify_faction,
    find_component_data,
    find_stage_of_actor,
    role_label,
)
from .combat_data_access import (
    get_dungeon_room,
    get_entities_details,
    get_stages_state,
    is_mock_mode,
    resolve_identity,
)
from .mock_data import (
    simulate_mock_advance_monster_turn,
    simulate_mock_equip_gear,
    simulate_mock_pass_turn,
    simulate_mock_play_cards,
    simulate_mock_use_consumable,
)
from .server_client import (
    TaskFailedError,
    dungeon_combat_equip_gear,
    dungeon_combat_pass_turn,
    dungeon_combat_play_cards,
    dungeon_combat_use_consumable,
    watch_task_until_done,
)
from .utils import display_name

# 锁 input 后回车切屏的目标
TO_POST_COMBAT = "post_combat"
TO_ROUND_START = "round_start"
TO_NEXT_TURN = "next_turn_actor"


@dataclass
class TurnActionResult:
    ok: bool
    text: str
    transition: Optional[str] = None


@dataclass
class TurnActorOverview:
    combat: Combat
    stage_name: str
    current_actor: Optional[str]
    current_entity: Optional[EntitySerialization]
    faction: str
    entities: List[EntitySerialization]


###############################################################################################################################################
async def _fetch_combat(game_client: GameClient) -> Combat:
    room_resp = await get_dungeon_room(game_client)
    room = room_resp.room
    assert isinstance(room, CombatRoom), f"当前房间不是战斗房间：type={room.type}"
    return room.combat


###############################################################################################################################################
def _detect_transition(combat: Combat, turn_ended: bool) -> Optional[str]:
    """按优先级判定「锁 input → 回车」的切屏目标。

    1. 战斗产生结果 → post_combat
    2. 仅当本动作结束当前角色回合（turn_ended）才考虑换手：
       - 回合完成 / 无行动角色 → round_start
       - 还有下一个 → next_turn_actor
    3. 其余 → None（留在本页）
    """
    if (
        combat.state in (CombatState.COMPLETE, CombatState.POST_COMBAT)
        or combat.result != CombatResult.NONE
    ):
        return TO_POST_COMBAT
    if not turn_ended:
        return None
    latest = combat.latest_round
    if latest is None or latest.is_completed or latest.current_actor is None:
        return TO_ROUND_START
    return TO_NEXT_TURN


###############################################################################################################################################
def _combat_result_banner(combat: Combat) -> Optional[str]:
    if combat.result == CombatResult.WIN:
        return "[bold green]🏆 战斗结束：胜利！[/]"
    if combat.result == CombatResult.LOSE:
        return "[bold red]💀 战斗结束：失败！[/]"
    return None


###############################################################################################################################################
def _diff_result_text(
    baseline_logs: List[str],
    baseline_narratives: List[str],
    result_logs: List[str],
    result_narratives: List[str],
    title: str,
) -> List[str]:
    """按基线长度 diff 出本次动作新增的战斗日志 / 叙事条目并渲染。"""
    new_logs = result_logs[len(baseline_logs) :]
    new_narratives = result_narratives[len(baseline_narratives) :]
    if not new_logs and not new_narratives:
        return []
    lines = [f"[bold yellow]── {title} ─────────────────────────────────[/]"]
    for combat_log, narrative in zip_longest(new_logs, new_narratives):
        lines.append(f"  [dim]战斗：[/] {combat_log or '[dim]（无）[/]'}")
        lines.append(f"  [dim]叙事：[/] {narrative or '[dim]（无）[/]'}")
    return lines


###############################################################################################################################################
async def _mock_turn_result(
    game_client: GameClient, ok: bool, text: str, turn_ended: bool
) -> TurnActionResult:
    """mock 动作完成后按当前 mock 状态计算 transition。"""
    if not ok:
        return TurnActionResult(ok=False, text=text)
    combat = await _fetch_combat(game_client)
    transition = _detect_transition(combat, turn_ended)
    return TurnActionResult(ok=True, text=text, transition=transition)


###############################################################################################################################################
async def load_turn_actor_overview(game_client: GameClient) -> TurnActorOverview:
    """加载回合行动页所需的一次性快照（战斗 + 场景 + 当前 turn 角色 + 阵营）。"""
    _, _, player_actor = resolve_identity(game_client)

    combat = await _fetch_combat(game_client)
    stages_resp = await get_stages_state(game_client)
    stage_name = find_stage_of_actor(stages_resp.mapping, player_actor)
    assert (
        stage_name is not None
    ), f"未能在场景映射中找到玩家角色所在场景：actor={player_actor}"
    participant_names = list(stages_resp.mapping[stage_name])

    entities_resp = await get_entities_details(
        game_client, [stage_name, *participant_names]
    )
    entities_map = {e.name: e for e in entities_resp.entities}

    latest = combat.latest_round
    current_actor = latest.current_actor if latest is not None else None
    current_entity = entities_map.get(current_actor) if current_actor else None
    faction = classify_faction(current_entity)

    return TurnActorOverview(
        combat=combat,
        stage_name=stage_name,
        current_actor=current_actor,
        current_entity=current_entity,
        faction=faction,
        entities=entities_resp.entities,
    )


###############################################################################################################################################
def _append_actor_summary_lines(lines: List[str], entity: EntitySerialization) -> None:
    """渲染场景内单个角色的简要摘要（HP/攻/防 + 死亡标记）。"""
    stats_data = find_component_data(entity, CharacterStatsComponent.__name__)
    if stats_data is None:
        lines.append(f"  [dim]{display_name(entity.name)}：缺少属性组件，跳过[/]")
        return

    stats = compute_effective_stats(CharacterStatsComponent(**stats_data).stats)
    label = role_label(entity)
    is_dead = find_component_data(entity, DeathComponent.__name__) is not None
    death_mark = "  [bold red]（已战死）[/]" if is_dead else ""
    lines.append(
        f"  {label} [bold]{display_name(entity.name)}[/]{death_mark}  "
        f"HP:[yellow]{stats.hp}/{stats.max_hp}[/]  "
        f"攻:{stats.attack}  防:{stats.defense}"
    )


###############################################################################################################################################
def build_turn_actor_info_text(overview: TurnActorOverview) -> str:
    """把回合行动页快照渲染为正文区富文本（宏观：仅 HP/攻/防，无手牌/能量/格挡）。"""
    combat = overview.combat
    lines: List[str] = []

    lines.append("[bold yellow]── 战斗宏观状态 ─────────────────────────────────[/]")
    lines.append(f"  名称：   [bold]{combat.name}[/]")
    lines.append(f"  状态：   [cyan]{combat.state.name}[/]")
    lines.append(f"  结果：   [magenta]{combat.result.name}[/]")
    lines.append(f"  已撤退： {'[red]是[/]' if combat.retreated else '[green]否[/]'}")
    lines.append("")

    latest = combat.latest_round
    lines.append("[bold yellow]── 回合状态 ─────────────────────────────────────[/]")
    lines.append(f"  场景：   {display_name(overview.stage_name)}")
    lines.append(f"  当前局数： [bold]{len(combat.rounds)}[/]")
    if latest is None:
        lines.append("  [dim]（尚无回合）[/]")
    else:
        draw_tag = "[green]是[/]" if latest.draw_completed else "[yellow]否[/]"
        complete_tag = "[green]是[/]" if latest.is_completed else "[yellow]否[/]"
        current_actor_label = overview.current_actor or "[dim]（无）[/]"
        order = (
            "  →  ".join(latest.action_order)
            if latest.action_order
            else "[dim]（无）[/]"
        )
        completed = (
            "、".join(latest.completed_actors)
            if latest.completed_actors
            else "[dim]（无）[/]"
        )
        lines.append(f"  已抽牌： {draw_tag}")
        lines.append(f"  回合已结束： {complete_tag}")
        lines.append(f"  当前 turn： [bold yellow]{current_actor_label}[/]")
        lines.append(f"  行动顺序： {order}")
        lines.append(f"  已出手角色： {completed}")
    lines.append("")

    lines.append(
        f"[bold yellow]── 场景：{display_name(overview.stage_name)} ─────────────[/]"
    )
    actor_entities = [e for e in overview.entities if e.name != overview.stage_name]
    if not actor_entities:
        lines.append("  [dim]（场景内暂无角色）[/]")
    else:
        for entity in actor_entities:
            _append_actor_summary_lines(lines, entity)

    return "\n".join(lines)


###############################################################################################################################################
async def play_cards(
    game_client: GameClient, card_name: str, targets: List[str]
) -> TurnActionResult:
    """出牌（我方）：不打乱行动权，仅在战斗产生结果时触发 transition。"""
    if is_mock_mode(game_client):
        ok, text = simulate_mock_play_cards(card_name, targets)
        return await _mock_turn_result(game_client, ok, text, turn_ended=False)

    try:
        baseline_combat = await _fetch_combat(game_client)
        baseline_round = baseline_combat.latest_round
        actor = baseline_round.current_actor if baseline_round is not None else None
        if actor is None:
            return TurnActionResult(False, "[yellow]当前没有行动角色。[/]")
        user_name, game_name, _ = resolve_identity(game_client)
        resp = await dungeon_combat_play_cards(
            user_name, game_name, actor, card_name, targets
        )
        await watch_task_until_done(resp.job_id)
    except TaskFailedError as e:
        logger.error(f"play_cards: 任务失败 error={e}")
        return TurnActionResult(False, f"[bold red]❌ 出牌失败：{e}[/]")
    except Exception as e:
        logger.error(f"play_cards: 请求失败 error={e}")
        return TurnActionResult(False, f"[bold red]❌ 出牌请求失败：{e}[/]")

    try:
        result_combat = await _fetch_combat(game_client)
    except Exception as e:
        logger.error(f"play_cards: 加载结果失败 error={e}")
        return TurnActionResult(False, f"[bold red]❌ 加载出牌结果失败：{e}[/]")

    result_round = result_combat.latest_round
    lines: List[str] = ["[bold green]✅ 出牌完成[/]"]
    lines.extend(
        _diff_result_text(
            baseline_round.cards_combat_log if baseline_round is not None else [],
            baseline_round.cards_narrative if baseline_round is not None else [],
            result_round.cards_combat_log if result_round is not None else [],
            result_round.cards_narrative if result_round is not None else [],
            "出牌结果",
        )
    )
    banner = _combat_result_banner(result_combat)
    if banner is not None:
        lines.append(banner)
    transition = _detect_transition(result_combat, turn_ended=False)
    return TurnActionResult(True, "\n".join(lines), transition)


###############################################################################################################################################
async def use_consumable(
    game_client: GameClient, item_name: str, targets: List[str]
) -> TurnActionResult:
    """使用消耗品（我方队伍级行为，不推进行动权）。"""
    if is_mock_mode(game_client):
        ok, text = simulate_mock_use_consumable(item_name, targets)
        return await _mock_turn_result(game_client, ok, text, turn_ended=False)

    try:
        baseline_combat = await _fetch_combat(game_client)
        baseline_round = baseline_combat.latest_round
        user_name, game_name, _ = resolve_identity(game_client)
        resp = await dungeon_combat_use_consumable(
            user_name, game_name, item_name, targets
        )
        await watch_task_until_done(resp.job_id)
    except TaskFailedError as e:
        logger.error(f"use_consumable: 任务失败 error={e}")
        return TurnActionResult(False, f"[bold red]❌ 使用失败：{e}[/]")
    except Exception as e:
        logger.error(f"use_consumable: 请求失败 error={e}")
        return TurnActionResult(False, f"[bold red]❌ 使用请求失败：{e}[/]")

    try:
        result_combat = await _fetch_combat(game_client)
    except Exception as e:
        logger.error(f"use_consumable: 加载结果失败 error={e}")
        return TurnActionResult(False, f"[bold red]❌ 加载使用结果失败：{e}[/]")

    result_round = result_combat.latest_round
    lines: List[str] = ["[bold green]✅ 使用完成[/]"]
    lines.extend(
        _diff_result_text(
            baseline_round.consumable_combat_log if baseline_round is not None else [],
            baseline_round.consumable_narrative if baseline_round is not None else [],
            result_round.consumable_combat_log if result_round is not None else [],
            result_round.consumable_narrative if result_round is not None else [],
            "使用结果",
        )
    )
    banner = _combat_result_banner(result_combat)
    if banner is not None:
        lines.append(banner)
    transition = _detect_transition(result_combat, turn_ended=False)
    return TurnActionResult(True, "\n".join(lines), transition)


###############################################################################################################################################
async def equip_gear(game_client: GameClient, item_name: str) -> TurnActionResult:
    """使用装备（我方队伍级行为，不推进行动权）。"""
    if is_mock_mode(game_client):
        ok, text = simulate_mock_equip_gear(item_name)
        return await _mock_turn_result(game_client, ok, text, turn_ended=False)

    try:
        baseline_combat = await _fetch_combat(game_client)
        baseline_round = baseline_combat.latest_round
        user_name, game_name, _ = resolve_identity(game_client)
        resp = await dungeon_combat_equip_gear(user_name, game_name, item_name)
        await watch_task_until_done(resp.job_id)
    except TaskFailedError as e:
        logger.error(f"equip_gear: 任务失败 error={e}")
        return TurnActionResult(False, f"[bold red]❌ 使用失败：{e}[/]")
    except Exception as e:
        logger.error(f"equip_gear: 请求失败 error={e}")
        return TurnActionResult(False, f"[bold red]❌ 使用请求失败：{e}[/]")

    try:
        result_combat = await _fetch_combat(game_client)
    except Exception as e:
        logger.error(f"equip_gear: 加载结果失败 error={e}")
        return TurnActionResult(False, f"[bold red]❌ 加载使用结果失败：{e}[/]")

    result_round = result_combat.latest_round
    lines: List[str] = ["[bold green]✅ 使用完成[/]"]
    lines.extend(
        _diff_result_text(
            baseline_round.gear_combat_log if baseline_round is not None else [],
            baseline_round.gear_narrative if baseline_round is not None else [],
            result_round.gear_combat_log if result_round is not None else [],
            result_round.gear_narrative if result_round is not None else [],
            "使用结果",
        )
    )
    banner = _combat_result_banner(result_combat)
    if banner is not None:
        lines.append(banner)
    transition = _detect_transition(result_combat, turn_ended=False)
    return TurnActionResult(True, "\n".join(lines), transition)


###############################################################################################################################################
async def pass_turn(game_client: GameClient) -> TurnActionResult:
    """过牌（我方）：结束当前角色回合，推进到下一个角色 / 回 round_start / 出结果。"""
    if is_mock_mode(game_client):
        ok, text = simulate_mock_pass_turn()
        return await _mock_turn_result(game_client, ok, text, turn_ended=True)

    try:
        baseline_combat = await _fetch_combat(game_client)
        baseline_round = baseline_combat.latest_round
        actor = baseline_round.current_actor if baseline_round is not None else None
        if actor is None:
            return TurnActionResult(False, "[yellow]当前没有行动角色。[/]")
        user_name, game_name, _ = resolve_identity(game_client)
        resp = await dungeon_combat_pass_turn(user_name, game_name, actor)
        await watch_task_until_done(resp.job_id)
    except TaskFailedError as e:
        logger.error(f"pass_turn: 任务失败 error={e}")
        return TurnActionResult(False, f"[bold red]❌ 过牌失败：{e}[/]")
    except Exception as e:
        logger.error(f"pass_turn: 请求失败 error={e}")
        return TurnActionResult(False, f"[bold red]❌ 过牌请求失败：{e}[/]")

    try:
        result_combat = await _fetch_combat(game_client)
    except Exception as e:
        logger.error(f"pass_turn: 加载结果失败 error={e}")
        return TurnActionResult(False, f"[bold red]❌ 加载过牌结果失败：{e}[/]")

    result_round = result_combat.latest_round
    lines: List[str] = ["[bold green]✅ 过牌完成[/]"]
    if result_round is not None and result_round.current_actor is not None:
        lines.append(f"[dim]轮到下一个角色：{result_round.current_actor}[/]")
    banner = _combat_result_banner(result_combat)
    if banner is not None:
        lines.append(banner)
    transition = _detect_transition(result_combat, turn_ended=True)
    return TurnActionResult(True, "\n".join(lines), transition)


###############################################################################################################################################
async def advance_monster_turn(game_client: GameClient) -> TurnActionResult:
    """推进怪物回合：怪物 LLM 自动出牌或过牌；过牌则推进行动权。"""
    if is_mock_mode(game_client):
        ok, text = simulate_mock_advance_monster_turn()
        return await _mock_turn_result(game_client, ok, text, turn_ended=True)

    try:
        baseline_combat = await _fetch_combat(game_client)
        baseline_round = baseline_combat.latest_round
        actor = baseline_round.current_actor if baseline_round is not None else None
        if actor is None:
            return TurnActionResult(False, "[yellow]当前没有行动角色。[/]")
        user_name, game_name, _ = resolve_identity(game_client)
        # card_name / targets 仅作占位，服务端识别到 actor 为怪物后改走
        # MonsterPrePlaySystem 自动决策（出牌或过牌）。
        resp = await dungeon_combat_play_cards(user_name, game_name, actor, "", [])
        await watch_task_until_done(resp.job_id)
    except TaskFailedError as e:
        logger.error(f"advance_monster_turn: 任务失败 error={e}")
        return TurnActionResult(False, f"[bold red]❌ 怪物回合推进失败：{e}[/]")
    except Exception as e:
        logger.error(f"advance_monster_turn: 请求失败 error={e}")
        return TurnActionResult(False, f"[bold red]❌ 怪物回合请求失败：{e}[/]")

    try:
        result_combat = await _fetch_combat(game_client)
    except Exception as e:
        logger.error(f"advance_monster_turn: 加载结果失败 error={e}")
        return TurnActionResult(False, f"[bold red]❌ 加载回合结果失败：{e}[/]")

    result_round = result_combat.latest_round
    turn_ended = result_round is None or result_round.current_actor != actor

    lines: List[str] = ["[bold green]✅ 怪物回合推进完成[/]"]
    lines.extend(
        _diff_result_text(
            baseline_round.cards_combat_log if baseline_round is not None else [],
            baseline_round.cards_narrative if baseline_round is not None else [],
            result_round.cards_combat_log if result_round is not None else [],
            result_round.cards_narrative if result_round is not None else [],
            "回合结果",
        )
    )
    if (
        turn_ended
        and result_round is not None
        and result_round.current_actor is not None
    ):
        lines.append(f"[dim]轮到下一个角色：{result_round.current_actor}[/]")
    banner = _combat_result_banner(result_combat)
    if banner is not None:
        lines.append(banner)
    transition = _detect_transition(result_combat, turn_ended)
    return TurnActionResult(True, "\n".join(lines), transition)
