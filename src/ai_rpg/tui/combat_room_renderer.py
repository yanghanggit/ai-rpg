"""战斗房间渲染辅助函数（无状态，可被 CombatRoomScreen 和 PlayCardsMixin 调用）。"""

from typing import Dict, Final, List, Optional
from rich import box as rich_box
from rich.table import Table
from textual.widgets import RichLog
from ..models import (
    Card,
    EntitySerialization,
    CharacterStatsComponent,
    PhaseType,
    StatusEffect,
    StatusEffectsComponent,
    DrawPileComponent,
    EquippedGearComponent,
    GearItem,
    HandComponent,
    MonsterComponent,
    PartyMemberComponent,
    PlayerComponent,
    CharacterStats,
)
from ..models.utils import compute_effective_stats
from .utils import display_name

# ─────────────────────────────────────────────────
# 目标类型标签（渲染器权威来源）
# ─────────────────────────────────────────────────
TARGET_LABEL: Final[Dict[str, str]] = {
    "enemy_single": "[red]敌方单体[/]",
    "enemy_all": "[red]敌方全体[/]",
    "ally_single": "[green]友方单体[/]",
    "ally_all": "[green]友方全体[/]",
    "self_only": "[cyan]仅自己[/]",
}

# ─────────────────────────────────────────────────
# 状态效果阶段标签（渲染器权威来源）
# ─────────────────────────────────────────────────
_PHASE_COLOR: Final[Dict[str, str]] = {
    PhaseType.DRAW: "cyan",
    # PhaseType.PLAY: "green",
    PhaseType.ARBITRATION: "yellow",
    PhaseType.ROUND_END: "red",
}

_PHASE_LABEL: Final[Dict[str, str]] = {
    PhaseType.DRAW: "抽牌",
    # PhaseType.PLAY: "出牌",
    PhaseType.ARBITRATION: "仲裁",
    PhaseType.ROUND_END: "回合末",
}


def write_hand_table(
    log: RichLog,
    cards: List[Card],
    entity_name: str,
    current_energy: Optional[int] = None,
) -> None:
    """将手牌列表以表格形式写入 RichLog。

    Args:
        current_energy: 当前行动者剩余 energy 点数；仅在展示可出牌的实时手牌时传入，
            用于在标记列中提示费用超出可用 energy 的卡牌。传 None 时不展示该提示（如
            浏览牌库/弃牌堆/消耗堆等无实时 energy 上下文的场景）。
    """
    hand_table = Table(
        show_header=True,
        show_lines=True,
        box=rich_box.ROUNDED,
        padding=(0, 1),
        expand=True,
    )
    hand_table.add_column("#", style="cyan", width=3, no_wrap=True)
    hand_table.add_column("名称", style="bold", min_width=10, no_wrap=True)
    hand_table.add_column("费用", style="yellow", width=5, no_wrap=True)
    hand_table.add_column("伤害", style="red", width=9, no_wrap=True)
    hand_table.add_column("目标", width=10, no_wrap=True)
    hand_table.add_column("描述 / affixes / modifiers", ratio=1)
    hand_table.add_column("标记", width=14)
    for idx, card in enumerate(cards, 1):
        # ── 伤害列：damage（多段）+ energy_delta ──
        dmg_parts: List[str] = []
        dmg_parts.append(
            f"{card.damage_dealt}x{card.hit_count}"
            if card.hit_count > 1
            else str(card.damage_dealt)
        )
        if card.energy_delta > 0:
            dmg_parts.append(f"[green]+{card.energy_delta}行动[/green]")
        elif card.energy_delta < 0:
            dmg_parts.append(f"[red]{card.energy_delta}行动[/red]")
        dmg_cell = "\n".join(dmg_parts)

        # ── 目标列 ──
        tt_str = TARGET_LABEL.get(card.target_type, f"[dim]{card.target_type}[/]")

        # ── 描述列：description + affixes + modifiers ──
        desc_parts: List[str] = []
        if card.description:
            desc_parts.append(f"[dim]{card.description}[/]")
        if card.affixes:
            desc_parts.append(f"[yellow]affixes: {'、'.join(card.affixes)}[/]")
        if card.modifiers:
            desc_parts.append(f"[cyan]modifiers: {'、'.join(card.modifiers)}[/]")
        desc_cell = "\n".join(desc_parts)

        # ── 标记列：playable / exhaust / energy 不足 / source ──
        flag_parts: List[str] = []
        if not card.playable:
            flag_parts.append("[bold orange1]不可出牌[/]")
        if card.exhaust:
            flag_parts.append("[bold orange1]消耗牌[/]")
        if current_energy is not None and current_energy < card.cost:
            flag_parts.append("[bold red]能量不足[/]")
        if card.source and card.source != entity_name:
            flag_parts.append(f"[dim]来源:{display_name(card.source)}[/]")
        flag_cell = "\n".join(flag_parts)

        hand_table.add_row(
            str(idx),
            card.name,
            str(card.cost),
            dmg_cell,
            tt_str,
            desc_cell,
            flag_cell,
        )
    log.write(hand_table)


def write_battlefield_block(
    log: RichLog,
    entities: List[EntitySerialization],
    round_num: int = 0,
    action_order: Optional[List[str]] = None,
    completed_actors: Optional[List[str]] = None,
) -> None:
    """从 ECS 实体列表渲染战场态势一览（回合信息 / HP）。"""
    if round_num > 0:
        ao_str = " → ".join(display_name(a) for a in (action_order or []))
        done_list = completed_actors or []
        done_str = (
            "  ".join(display_name(a) for a in done_list) if done_list else "（无）"
        )
        log.write(
            f"  [bold yellow]回合 {round_num}[/]  行动序列：{ao_str}  已出手：{done_str}"
        )
    log.write("  [bold]战场态势：[/]")
    for entity in entities:
        comp_names = {c.name for c in entity.components}
        if MonsterComponent.__name__ in comp_names:
            flabel = "[red]敌[/]"
        elif PartyMemberComponent.__name__ in comp_names:
            flabel = "[green]友[/]"
        else:
            flabel = "[dim]?[/]"
        hp_str = "?/?"
        _stats_comp = None
        for comp in entity.components:
            if comp.name == CharacterStatsComponent.__name__:
                _stats_comp = CharacterStatsComponent(**comp.data)
        equipped_gear_comp = next(
            (c for c in entity.components if c.name == EquippedGearComponent.__name__),
            None,
        )
        if _stats_comp is not None:
            _final = compute_effective_stats(
                _stats_comp.stats,
                equipped_gear=(
                    GearItem(**equipped_gear_comp.data["item"])
                    if equipped_gear_comp is not None
                    else None
                ),
            )
            hp_str = f"{_final.hp}/{_final.max_hp}"
        short = display_name(entity.name)
        log.write(f"    {flabel} [bold]{short}[/]  HP:[yellow]{hp_str}[/]")
    log.write("")


def _write_entity_header_block(
    log: RichLog,
    entity_name: str,
    faction_label: str,
    is_player: bool,
    stats: CharacterStats,
) -> None:
    """渲染实体宏观信息块（阵营 / 名称 / 玩家标记 + 战斗属性，作为一个整体输出）。"""
    player_tag = r"  [bold yellow]\[玩家][/]" if is_player else ""
    log.write(
        f"[bold cyan]── {faction_label} [bold]{display_name(entity_name)}[/]{player_tag} ──[/]"
        f"  [yellow]HP:{stats.hp}/{stats.max_hp}[/yellow]"
        f"  [red]ATK:{stats.attack}[/red]"
        f"  [blue]DEF:{stats.defense}[/blue]"
        f"  [cyan]SPD:{stats.speed}[/cyan]"
        f"  能量:{stats.energy}次/回合"
    )


def _write_status_effects_table(
    log: RichLog, effects: List[StatusEffect], entity_name: str
) -> None:
    """渲染状态效果表格（effects 非空时调用）。"""
    log.write(f"  [bold]状态效果（{len(effects)}）：[/]")
    se_table = Table(
        show_header=True,
        show_lines=True,
        box=rich_box.ROUNDED,
        padding=(0, 1),
        expand=True,
    )
    se_table.add_column("名称", style="magenta", min_width=10, no_wrap=True)
    se_table.add_column("剩余", style="dim", width=10, no_wrap=True)
    se_table.add_column("计数", width=6, no_wrap=True)
    se_table.add_column("阶段", width=10, no_wrap=True)
    se_table.add_column("速度", width=6, no_wrap=True)
    se_table.add_column("防御", width=6, no_wrap=True)
    se_table.add_column("描述", ratio=1)
    for effect in effects:
        duration_str = "永久" if effect.duration == -1 else f"剩余{effect.duration}回合"
        counter_str = (
            f"[bold]{effect.counter}[/bold]" if effect.counter != 0 else "[dim]0[/dim]"
        )
        phase_color = _PHASE_COLOR.get(effect.phase, "white")
        phase_label = _PHASE_LABEL.get(effect.phase, str(effect.phase))
        phase_cell = f"[{phase_color}]{phase_label}[/{phase_color}]"
        speed_cell = (
            f"[green]+{effect.speed}[/green]"
            if effect.speed > 0
            else (f"[red]{effect.speed}[/red]" if effect.speed < 0 else "[dim]0[/dim]")
        )
        defense_cell = (
            f"[green]+{effect.defense}[/green]"
            if effect.defense > 0
            else (
                f"[red]{effect.defense}[/red]" if effect.defense < 0 else "[dim]0[/dim]"
            )
        )
        desc_cell = effect.description
        if effect.source and effect.source != entity_name:
            desc_cell += f"  [dim]来源:{display_name(effect.source)}[/]"
        se_table.add_row(
            effect.name,
            duration_str,
            counter_str,
            phase_cell,
            speed_cell,
            defense_cell,
            desc_cell,
        )
    log.write(se_table)


def _write_draw_pile(
    log: RichLog, draw_pile: DrawPileComponent, entity_name: str
) -> None:
    """渲染抽牌堆区块。"""
    log.write(f"  [bold]抽牌堆（{len(draw_pile.cards)} 张）：[/]")
    if draw_pile.cards:
        write_hand_table(log, draw_pile.cards, entity_name)
    else:
        log.write("    [dim](空)[/]")


def _write_hand(log: RichLog, hand: Optional[HandComponent], entity_name: str) -> None:
    """渲染手牌区块（hand 为 None 时显示占位文字）。"""
    if hand is None:
        log.write("  [dim](无手牌)[/]")
        return
    log.write(f"  [bold]手牌 {len(hand.cards)} 张）：[/]")
    if hand.cards:
        write_hand_table(log, hand.cards, hand.name)
    else:
        log.write("    [dim](手牌为空)[/]")


def write_full_entities_block(
    log: RichLog,
    entities: List[EntitySerialization],
    show_hand: bool = True,
    show_header: bool = True,
) -> None:
    """骨架函数：逐实体渲染完整战斗信息（属性 / 状态效果 / 抽牌堆 / 手牌）。"""
    for entity in entities:
        # ── 集中提取所有组件 ──
        comp_map = {c.name: c for c in entity.components}

        # 阵营与标识（互斥、可选）
        is_player = PlayerComponent.__name__ in comp_map
        is_monster = MonsterComponent.__name__ in comp_map
        is_party = PartyMemberComponent.__name__ in comp_map

        # 必须存在的组件（断言，让问题尽早暴露）
        assert (
            CharacterStatsComponent.__name__ in comp_map
        ), f"[renderer] {entity.name} 缺少 CharacterStatsComponent"
        assert (
            StatusEffectsComponent.__name__ in comp_map
        ), f"[renderer] {entity.name} 缺少 StatusEffectsComponent"

        # 解析必须组件
        stats_comp = CharacterStatsComponent(
            **comp_map[CharacterStatsComponent.__name__].data
        )
        status_effects_comp = StatusEffectsComponent(
            **comp_map[StatusEffectsComponent.__name__].data
        )

        # 解析可选组件
        _gear_raw = comp_map.get(EquippedGearComponent.__name__)
        equipped_gear = GearItem(**_gear_raw.data["item"]) if _gear_raw else None

        _hand_raw = comp_map.get(HandComponent.__name__)
        hand = HandComponent(**_hand_raw.data) if _hand_raw else None

        # ── 阵营标签 ──
        if is_monster:
            faction_label = "[bold red]敌方[/]"
        elif is_party:
            faction_label = "[bold green]友方[/]"
        else:
            faction_label = "[dim]未知[/]"

        # ── 渲染各阶段 ──
        stats = compute_effective_stats(
            stats_comp.stats,
            status_effects_comp.status_effects,
            equipped_gear,
        )
        if show_header:
            _write_entity_header_block(
                log, entity.name, faction_label, is_player, stats
            )
        log.write("")

        if status_effects_comp.status_effects:
            _write_status_effects_table(
                log, status_effects_comp.status_effects, entity.name
            )
        else:
            log.write("  [dim](无状态效果)[/]")
        log.write("")

        if show_hand:
            _write_hand(log, hand, entity.name)
            log.write("")
