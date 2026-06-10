"""tui_client 无状态工具方法"""

from typing import Any, Dict, List, Tuple

# 这些类别前缀保留在显示名中（不剥离首段）
_KEEP_PREFIXES = {"地下城"}


def display_name(full_name: str) -> str:
    """从实体全名中提取 UI 显示名。

    规则：去掉首段类别前缀，但 ``地下城`` 类别保留全名。

    例如：
        ``旅行者.无名氏``    →  ``旅行者.无名氏``
        ``场景.断壁石室``    →  ``断壁石室``
        ``地下城.残柱外沿``  →  ``地下城.残柱外沿``
    """
    first_dot = full_name.find(".")
    if first_dot == -1:
        return full_name
    prefix = full_name[:first_dot]
    if prefix in _KEEP_PREFIXES:
        return full_name
    return full_name[first_dot + 1 :]


_TARGET_MAP = {
    "self_only": "己方",
    "enemy_single": "单体敌方",
    "enemy_all": "全体敌方",
    "ally_single": "单体友方",
    "ally_all": "全体友方",
}

_STAT_LABELS: List[Tuple[str, str]] = [
    ("attack", "攻击+{}"),
    ("defense", "防御+{}"),
    ("hp", "HP+{}"),
    ("max_hp", "MaxHP+{}"),
    ("energy", "行动+{}"),
    ("speed", "速度+{}"),
]


def render_item(item: Dict[str, Any]) -> str:
    """将单件道具 dict 渲染为单行 Rich markup 字符串。

    item 可以是 raw dict（不需要是 pydantic 模型实例）。
    """
    item_name = item.get("name", "?")
    item_type = item.get("type", "")
    count = item.get("count", 1)
    count_str = f" ×{count}" if count != 1 else ""

    if item_type == "GearItem":
        bonuses = item.get("stat_bonuses", {})
        bonus_parts = []
        for key, fmt in _STAT_LABELS:
            val = bonuses.get(key, 0)
            if val:
                bonus_parts.append(fmt.format(val))
        bonus_str = f" [dim]({', '.join(bonus_parts)})[/]" if bonus_parts else ""
        return f"[bold]{item_name}[/]{count_str} [yellow]【装备】[/]{bonus_str}"

    elif item_type == "CostumeItem":
        return f"[bold]{item_name}[/]{count_str} [magenta]【外观】[/]"

    elif item_type == "ConsumableItem":
        target_type = item.get("target_type", "")
        target_str = _TARGET_MAP.get(target_type, target_type)
        return f"[bold]{item_name}[/]{count_str} [green]【消耗品】[/] [dim]({target_str})[/]"

    else:  # MaterialItem 及其他
        return f"[bold]{item_name}[/]{count_str} [dim]【材料】[/]"
