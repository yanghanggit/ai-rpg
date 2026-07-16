"""无状态工具方法"""

from typing import List, Dict, Final
from ..models import (
    AnyItem,
    CostumeItem,
    ConsumableItem,
    GearItem,
    MaterialItem,
    Card,
    StatusEffect,
)

TARGET_MAP: Final[Dict[str, str]] = {
    "self_only": "己方",
    "enemy_single": "单体敌方",
    "enemy_all": "全体敌方",
    "enemy_random_multi": "随机多体敌方",
    "ally_single": "单体友方",
    "ally_all": "全体友方",
}

# 状态效果阶段标签；键为 PhaseType 的字符串值。
PHASE_LABEL: Final[Dict[str, str]] = {
    "draw": "抽牌",
    "arbitration": "仲裁",
    "round_end": "回合末",
}


def display_name(full_name: str) -> str:
    """从实体全名中提取 UI 显示名。"""
    return full_name


def render_item(item: AnyItem) -> str:
    """将单件道具模型实例渲染为多行 Rich markup 字符串。"""
    count_str = f" ×{item.count}" if item.count != 1 else ""
    lines = []

    if isinstance(item, GearItem):
        lines.append(f"[bold]{item.name}[/]{count_str} [yellow]【装备】[/]")
        lines.append(f"  [dim]{item.description}[/]")
        s = item.stat_bonuses
        bonus_parts = []
        for val, fmt in [
            (s.attack, "攻击+{}"),
            (s.defense, "防御+{}"),
            (s.hp, "HP+{}"),
            (s.max_hp, "MaxHP+{}"),
            (s.energy, "行动+{}"),
            (s.speed, "速度+{}"),
        ]:
            if val:
                bonus_parts.append(fmt.format(val))
        if bonus_parts:
            lines.append(f"  [dim]属性: {', '.join(bonus_parts)}[/]")
        target_label = TARGET_MAP.get(item.target_type.value, item.target_type.value)
        lines.append(f"  [dim]目标: {target_label}[/]")
        if item.equip_affixes:
            for affix in item.equip_affixes:
                lines.append(f"  [dim]词缀(装备时) {affix}[/]")
        if item.on_hit_affixes:
            for affix in item.on_hit_affixes:
                lines.append(f"  [dim]词缀(命中时) {affix}[/]")
        if item.modifiers:
            for mod in item.modifiers:
                lines.append(f"  [dim]修正 {mod}[/]")

    elif isinstance(item, CostumeItem):
        lines.append(f"[bold]{item.name}[/]{count_str} [magenta]【外观】[/]")
        lines.append(f"  [dim]{item.description}[/]")

    elif isinstance(item, ConsumableItem):
        target_label = TARGET_MAP.get(item.target_type.value, item.target_type.value)
        lines.append(
            f"[bold]{item.name}[/]{count_str} [green]【消耗品】[/]  [dim]目标: {target_label}[/]"
        )
        lines.append(f"  [dim]{item.description}[/]")
        if item.affixes:
            for affix in item.affixes:
                lines.append(f"  [dim]词缀 {affix}[/]")
        if item.modifiers:
            for mod in item.modifiers:
                lines.append(f"  [dim]修正 {mod}[/]")

    else:  # MaterialItem
        assert isinstance(item, MaterialItem)
        lines.append(f"[bold]{item.name}[/]{count_str} [dim]【材料】[/]")
        lines.append(f"  [dim]{item.description}[/]")

    return "\n".join(lines)


def render_card(card: Card) -> str:
    """渲染单张卡牌的全部字段（除 uuid 与 original_data 外）。"""
    flags: List[str] = []
    if not card.playable:
        flags.append("[bold orange1]不可出牌[/]")
    if card.exhaust:
        flags.append("[bold orange1]消耗牌[/]")
    flag_mark = "  " + " ".join(flags) if flags else ""

    target_label = TARGET_MAP.get(card.target_type.value, card.target_type.value)

    lines = [
        f"    [bold]{card.name}[/]{flag_mark}",
        f"      [dim]{card.description}[/]",
    ]

    stat_parts = [
        f"费用:{card.cost}",
        f"伤害:{card.damage_dealt}",
        f"连击:{card.hit_count}",
        f"目标:{target_label}",
    ]
    if card.energy_delta:
        stat_parts.append(f"行动改变:{card.energy_delta:+d}")
    lines.append("      " + "  ".join(stat_parts))

    if card.affixes:
        lines.append(f"      [yellow]affixes: {'、'.join(card.affixes)}[/]")
    if card.modifiers:
        lines.append(f"      [cyan]modifiers: {'、'.join(card.modifiers)}[/]")
    if card.source:
        lines.append(f"      [dim]来源: {card.source}[/]")

    return "\n".join(lines)


def render_status_effect(effect: StatusEffect, entity_name: str = "") -> str:
    """渲染单个状态效果的全部关键字段。

    entity_name: 效果所挂载实体的名称；当 effect.source 与之不同时才附加显示来源，
    避免自身施加的效果冗余标注来源。
    """
    duration_str = "永久" if effect.duration == -1 else f"剩余{effect.duration}回合"
    phase_label = PHASE_LABEL.get(effect.phase.value, effect.phase.value)
    meta_parts = [duration_str, f"阶段:{phase_label}"]
    if effect.counter:
        meta_parts.append(f"计数:{effect.counter}")
    if effect.speed:
        meta_parts.append(f"速度:{effect.speed:+d}")
    if effect.defense:
        meta_parts.append(f"防御:{effect.defense:+d}")
    if effect.source and effect.source != entity_name:
        meta_parts.append(f"来源:{display_name(effect.source)}")
    meta = "  ".join(meta_parts)

    return (
        f"    • [bold]{effect.name}[/]  [dim]{meta}[/]\n"
        f"      [dim]{effect.description}[/]"
    )
