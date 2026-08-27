"""无状态工具方法"""

from typing import List, Dict, Final
from ..models import (
    AnyItem,
    CostumeItem,
    ConsumableItem,
    GearItem,
    MaterialItem,
    Card,
    AnyAgentEvent,
    SpeakEvent,
    WhisperEvent,
    AnnounceEvent,
    MindEvent,
    QueryEvent,
    TransStageEvent,
    CombatInitiationEvent,
    CombatArbitrationEvent,
    CombatArchiveEvent,
    AppearanceUpdateEvent,
)


TARGET_MAP: Final[Dict[str, str]] = {
    "single": "单体",
    "all": "阵营全体",
    "spread": "阵营散射",
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
        ]:
            if val:
                bonus_parts.append(fmt.format(val))
        if bonus_parts:
            lines.append(f"  [dim]属性: {', '.join(bonus_parts)}[/]")
        lines.append(f"  [dim]费用: 目标 energy -{item.cost}[/]")

    elif isinstance(item, CostumeItem):
        lines.append(f"[bold]{item.name}[/]{count_str} [magenta]【外观】[/]")
        lines.append(f"  [dim]{item.description}[/]")

    elif isinstance(item, ConsumableItem):
        target_label = TARGET_MAP.get(item.target_type.value, item.target_type.value)
        lines.append(
            f"[bold]{item.name}[/]{count_str} [green]【消耗品】[/]  [dim]目标: {target_label}[/]"
        )
        lines.append(f"  [dim]{item.description}[/]")
        if item.on_use_affixes:
            for affix in item.on_use_affixes:
                lines.append(f"  [dim]词缀(使用时) {affix}[/]")

    else:  # MaterialItem
        assert isinstance(item, MaterialItem)
        lines.append(f"[bold]{item.name}[/]{count_str} [dim]【材料】[/]")
        lines.append(f"  [dim]{item.description}[/]")

    return "\n".join(lines)


def render_card(card: Card) -> str:
    """渲染单张卡牌的全部字段（除 uuid 外）。"""
    flags: List[str] = []
    if not card.playable:
        flags.append("[bold orange1]不可出牌[/]")
    if card.exhaust:
        flags.append("[bold orange1]消耗牌[/]")
    flag_mark = "  " + " ".join(flags) if flags else ""

    target_label = (
        "自身"
        if card.self_target
        else TARGET_MAP.get(card.target_type.value, card.target_type.value)
    )

    lines = [
        f"    [bold]{card.name}[/]{flag_mark}",
        f"      [dim]{card.description}[/]",
    ]

    stat_parts = [
        f"费用:{card.cost}",
        f"伤害:{card.damage}",
        f"连击:{card.hit_count}",
        f"格挡:{card.block}",
        f"目标:{target_label}",
    ]
    lines.append("      " + "  ".join(stat_parts))

    if card.on_play_affixes:
        lines.append(f"      [yellow]即时词缀: {'、'.join(card.on_play_affixes)}[/]")
    if card.source:
        lines.append(f"      [dim]来源: {card.source}[/]")

    return "\n".join(lines)


def format_agent_event(event: AnyAgentEvent) -> str:
    """将 AnyAgentEvent 渲染为 Rich markup 字符串，尽量完整展示各字段（含 stage/combat_log 等）。"""
    match event:
        case SpeakEvent():
            return (
                f"[bold yellow]{event.actor}[/] [dim]@{event.stage}[/] "
                f"对 [yellow]{event.target}[/] 说：\n"
                f"  「{event.content}」"
            )
        case WhisperEvent():
            return (
                f"[dim]{event.actor} @{event.stage} 悄悄向 {event.target} 耳语：\n"
                f"  「{event.content}」[/]"
            )
        case AnnounceEvent():
            return (
                f"[bold magenta]【{event.actor}】[/] [dim]@{event.stage}[/] 宣告：\n"
                f"  {event.content}"
            )
        case MindEvent():
            return (
                f"[dim italic]{event.actor} @{event.stage} 心想：\n"
                f"  （{event.content}）[/]"
            )
        case QueryEvent():
            return (
                f"[dim]{event.actor} @{event.stage} 询问：\n" f"  {event.question}[/]"
            )
        case TransStageEvent():
            return f"[cyan]▶ {event.actor}  {event.stage} → {event.target}[/]"
        case CombatInitiationEvent():
            return f"[bold red]⚔ {event.actor}[/] [dim]@{event.stage}[/] 发起战斗！"
        case CombatArbitrationEvent():
            return (
                f"[bold yellow]── 战斗裁决 @{event.stage} ──[/]\n"
                f"[dim]{event.combat_log}[/]\n"
                f"[bold]{event.narrative}[/]"
            )
        case CombatArchiveEvent():
            return (
                f"[dim]{event.actor} @{event.stage} 战斗归档：\n"
                f"  {event.summary}[/]"
            )
        case AppearanceUpdateEvent():
            return (
                f"[bold green]✨ {event.actor}[/] [dim]@{event.stage}[/] 外观已更新：\n"
                f"  [dim]{event.appearance}[/]"
            )
        case _:
            return f"[dim cyan]{event.message}[/]"
