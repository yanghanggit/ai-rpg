"""战斗房间渲染辅助函数（无状态，可被 CombatRoomScreen 和 PlayCardsMixin 调用）。"""

from typing import Dict, Final, List, Optional
from rich import box as rich_box
from rich.table import Table
from textual.widgets import RichLog
from ..models import (
    Card,
    EntitySerialization,
    CharacterStatsComponent,
    StatusEffectsComponent,
    DrawPileComponent,
    HandComponent,
    MonsterComponent,
    PartyMemberComponent,
    PlayerComponent,
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


def write_hand_table(log: RichLog, cards: List[Card], entity_name: str) -> None:
    """将手牌列表以表格形式写入 RichLog。"""
    hand_table = Table(
        show_header=True,
        show_lines=True,
        box=rich_box.ROUNDED,
        padding=(0, 1),
        expand=True,
    )
    hand_table.add_column("#", style="cyan", width=3, no_wrap=True)
    hand_table.add_column("名称", style="bold", min_width=10, no_wrap=True)
    hand_table.add_column("伤害", style="red", width=6, no_wrap=True)
    hand_table.add_column("目标", width=10, no_wrap=True)
    hand_table.add_column("描述 / 效果 / 词条", ratio=1)
    for idx, card in enumerate(cards, 1):
        dmg_cell = (
            f"{card.damage_dealt}x{card.hit_count}"
            if card.hit_count > 1
            else str(card.damage_dealt)
        )
        tt_str = TARGET_LABEL.get(card.target_type, f"[dim]{card.target_type}[/]")
        detail_parts: List[str] = []
        if card.description:
            detail_parts.append(f"[dim]{card.description}[/]")
        if card.affixes:
            detail_parts.append(f"[yellow]词缀：{'\u3001'.join(card.affixes)}[/]")
        if card.modifiers:
            detail_parts.append(f"[cyan]即时：{'\u3001'.join(card.modifiers)}[/]")
        if not card.playable:
            detail_parts.append("[bold orange1]【不可出牌】[/]")
        if card.exhaust:
            detail_parts.append("[bold orange1]【消耗牌】[/]")
        if card.source and card.source != entity_name:
            detail_parts.append(f"[dim]来源:{display_name(card.source)}[/]")
        hand_table.add_row(
            str(idx),
            card.name,
            dmg_cell,
            tt_str,
            "\n".join(detail_parts),
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
        if _stats_comp is not None:
            _final = compute_effective_stats(_stats_comp)
            hp_str = f"{_final.hp}/{_final.max_hp}"
        short = display_name(entity.name)
        log.write(f"    {flabel} [bold]{short}[/]  HP:[yellow]{hp_str}[/]")
    log.write("")


def write_full_entities_block(
    log: RichLog,
    entities: List[EntitySerialization],
    show_hand: bool = True,
    show_header: bool = True,
) -> None:
    """渲染每个实体的完整战斗信息（阵营/属性/状态效果/手牌）。"""
    for entity in entities:
        faction = "[dim]未知[/]"
        is_player = any(c.name == PlayerComponent.__name__ for c in entity.components)
        for comp in entity.components:
            if comp.name == PartyMemberComponent.__name__:
                faction = "[bold green]友方[/]"
                break
            elif comp.name == MonsterComponent.__name__:
                faction = "[bold red]敌方[/]"
                break
        player_tag = r"  [bold yellow]\[玩家][/]" if is_player else ""
        if show_header:
            log.write(
                f"[bold cyan]── {faction} [bold]{display_name(entity.name)}[/]{player_tag} ──[/]"
            )
        # 战斗属性
        stats_comp = next(
            (
                c
                for c in entity.components
                if c.name == CharacterStatsComponent.__name__
            ),
            None,
        )
        if stats_comp is not None:
            status_effects_comp = next(
                (
                    c
                    for c in entity.components
                    if c.name == StatusEffectsComponent.__name__
                ),
                None,
            )
            stats = compute_effective_stats(
                CharacterStatsComponent(**stats_comp.data),
                (
                    StatusEffectsComponent(**status_effects_comp.data).status_effects
                    if status_effects_comp is not None
                    else None
                ),
            )
            log.write(
                f"  [yellow]HP:{stats.hp}/{stats.max_hp}[/yellow]"
                f"  [red]ATK:{stats.attack}[/red]"
                f"  [blue]DEF:{stats.defense}[/blue]"
                f"  [cyan]SPD:{stats.speed}[/cyan]"
                f"  行动:{stats.energy}次/回合"
            )
        else:
            log.write("  [dim](无战斗属性)[/]")
        # 状态效果
        status_effects_comp = next(
            (c for c in entity.components if c.name == StatusEffectsComponent.__name__),
            None,
        )
        if status_effects_comp is not None:
            effects = StatusEffectsComponent(**status_effects_comp.data).status_effects
            if effects:
                log.write(f"  [bold]状态效果（{len(effects)}）：[/]")
                se_table = Table(
                    show_header=True,
                    show_lines=False,
                    box=rich_box.SIMPLE_HEAD,
                    padding=(0, 1),
                    expand=True,
                )
                se_table.add_column("名称", style="magenta", min_width=10, no_wrap=True)
                se_table.add_column("剩余", style="dim", width=10, no_wrap=True)
                se_table.add_column("阶段", width=12, no_wrap=True)
                se_table.add_column("速度", width=6, no_wrap=True)
                se_table.add_column("防御", width=6, no_wrap=True)
                se_table.add_column("描述", ratio=1)
                phase_colors = {
                    "draw": "cyan",
                    "arbitration": "yellow",
                    "round_end": "red",
                }
                phase_labels = {
                    "draw": "抽牌",
                    "arbitration": "仲裁",
                    "round_end": "回合末",
                }
                for effect in effects:
                    duration_str = (
                        "永久"
                        if effect.duration == -1
                        else f"剩余{effect.duration}回合"
                    )
                    phase_color = phase_colors.get(effect.phase, "white")
                    phase_label = phase_labels.get(effect.phase, effect.phase)
                    phase_cell = f"[{phase_color}]{phase_label}[/{phase_color}]"
                    if effect.speed > 0:
                        speed_cell = f"[green]+{effect.speed}[/green]"
                    elif effect.speed < 0:
                        speed_cell = f"[red]{effect.speed}[/red]"
                    else:
                        speed_cell = "[dim]0[/dim]"
                    if effect.defense > 0:
                        defense_cell = f"[green]+{effect.defense}[/green]"
                    elif effect.defense < 0:
                        defense_cell = f"[red]{effect.defense}[/red]"
                    else:
                        defense_cell = "[dim]0[/dim]"
                    desc_cell = effect.description
                    if effect.source and effect.source != entity.name:
                        desc_cell += f"  [dim]来源:{display_name(effect.source)}[/]"
                    se_table.add_row(
                        effect.name,
                        duration_str,
                        phase_cell,
                        speed_cell,
                        defense_cell,
                        desc_cell,
                    )
                log.write(se_table)
            else:
                log.write("  [dim](无状态效果)[/]")
        else:
            log.write("  [dim](无状态效果)[/]")
        log.write("")
        # 抽牌堆
        draw_pile_comp = next(
            (c for c in entity.components if c.name == DrawPileComponent.__name__),
            None,
        )
        if draw_pile_comp is not None:
            draw_pile = DrawPileComponent(**draw_pile_comp.data)
            log.write(f"  [bold]抽牌堆（{len(draw_pile.cards)} 张）：[/]")
            if draw_pile.cards:
                write_hand_table(log, draw_pile.cards, entity.name)
            else:
                log.write("    [dim](空)[/]")
        log.write("")
        # 手牌
        if show_hand:
            hand_comp = next(
                (c for c in entity.components if c.name == HandComponent.__name__),
                None,
            )
            if hand_comp is not None:
                hand = HandComponent(**hand_comp.data)
                log.write(
                    f"  [bold]手牌（回合 {hand.round}，共 {len(hand.cards)} 张）：[/]"
                )
                if hand.cards:
                    write_hand_table(log, hand.cards, entity.name)
                else:
                    log.write("    [dim](手牌为空)[/]")
            else:
                log.write("  [dim](无手牌)[/]")
        log.write("")
