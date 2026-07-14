"""无状态工具方法"""

from ..models.items import AnyItem, CostumeItem, ConsumableItem, GearItem, MaterialItem

# 这些类别前缀保留在显示名中（不剥离首段）
# _KEEP_PREFIXES = {"地下城"}


def display_name(full_name: str) -> str:
    return full_name  # 临时处理。
    # """从实体全名中提取 UI 显示名。

    # 规则：去掉首段类别前缀，但 ``地下城`` 类别保留全名。

    # 例如：
    #     ``旅行者.无名氏``    →  ``旅行者.无名氏``
    #     ``场景.断壁石室``    →  ``断壁石室``
    #     ``地下城.残柱外沿``  →  ``地下城.残柱外沿``
    # """
    # first_dot = full_name.find(".")
    #     return full_name
    # prefix = full_name[:first_dot]
    # if prefix in _KEEP_PREFIXES:
    #     return full_name
    # return full_name[first_dot + 1 :]


_TARGET_MAP = {
    "self_only": "己方",
    "enemy_single": "单体敌方",
    "enemy_all": "全体敌方",
    "enemy_random_multi": "随机多体敌方",
    "ally_single": "单体友方",
    "ally_all": "全体友方",
}


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
        target_label = _TARGET_MAP.get(item.target_type.value, item.target_type.value)
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
        target_label = _TARGET_MAP.get(item.target_type.value, item.target_type.value)
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
