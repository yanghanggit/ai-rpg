"""玩家当前状态 Screen"""

from typing import Any, Dict, Set

from loguru import logger
from ..models import (
    IdentityComponent,
    AllyComponent,
    AppearanceComponent,
    ActorComponent,
    CharacterStatsComponent,
    EquipmentComponent,
    InventoryComponent,
    PlayerComponent,
    ExpeditionRosterComponent,
    ArchetypeComponent,
    DrawDeckComponent,
    DiscardDeckComponent,
    AnyItem,
    EquipmentItem,
    CharacterStats,
)
from textual import work
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import RichLog

from .server_client import fetch_entities_details
from .utils import display_name


# 物品类型 → 中文标签
_ITEM_TYPE_LABELS: Dict[str, str] = {
    "WeaponItem": "武器",
    "EquipmentItem": "装备",
    "ConsumableItem": "消耗品",
    "MaterialItem": "材料",
    "UniqueItem": "特殊",
}

# EquipmentItem 子类型 → 中文标签
_EQUIPMENT_TYPE_LABELS: Dict[str, str] = {
    "Armor": "防具",
    "Accessory": "饰品",
}

# stat_bonuses 字段 → 中文标签（按展示顺序）
_STAT_LABELS: list[tuple[str, str]] = [
    ("hp", "HP"),
    ("max_hp", "最大HP"),
    ("attack", "攻击"),
    ("defense", "防御"),
    ("energy", "行动"),
    ("speed", "速度"),
]

# 组件渲染顺序（靠前的优先展示）
_COMPONENT_ORDER: list[str] = [
    ActorComponent.__name__,
    CharacterStatsComponent.__name__,
    EquipmentComponent.__name__,
    InventoryComponent.__name__,
    AppearanceComponent.__name__,
    ArchetypeComponent.__name__,
    DrawDeckComponent.__name__,
    DiscardDeckComponent.__name__,
]


def _stat_bonuses_str(stats: CharacterStats) -> str:
    """将 CharacterStats 属性加成转为可读字符串，只展示非零项。"""
    parts = []
    for attr, label in _STAT_LABELS:
        val: int = getattr(stats, attr, 0)
        if val != 0:
            sign = "+" if val > 0 else ""
            parts.append(f"{label}{sign}{val}")
    return "  ".join(parts)


def _render_item(item: AnyItem, equipped: Set[str]) -> str:
    """将单个 AnyItem 渲染为多行 Rich markup 字符串。"""
    type_label = _ITEM_TYPE_LABELS.get(item.type, str(item.type))
    if isinstance(item, EquipmentItem):
        type_label = _EQUIPMENT_TYPE_LABELS.get(
            item.equipment_type, str(item.equipment_type)
        )

    equipped_tag = "  [bold green]\[装备中][/]" if item.name in equipped else ""
    lines = [f"      [yellow]◦ {item.name}[/]{equipped_tag}"]
    lines.append(f"        [dim]类型：{type_label}[/]")
    if item.description:
        lines.append(f"        [dim]{item.description}[/]")
    stat_bonuses = getattr(item, "stat_bonuses", None)
    if stat_bonuses is not None:
        bonus_str = _stat_bonuses_str(stat_bonuses)
        if bonus_str:
            lines.append(f"        [cyan]属性加成：{bonus_str}[/]")
    return "\n".join(lines)


def _render_component(name: str, data: Dict[str, Any], context: Dict[str, Any]) -> str:
    """将组件 data 渲染为可读的 Rich markup 字符串。返回空字符串表示跳过此组件。"""
    # 过滤掉纯冗余组件
    if name in (
        IdentityComponent.__name__,
        AllyComponent.__name__,
        PlayerComponent.__name__,
        ExpeditionRosterComponent.__name__,
    ):
        return ""

    lines: list[str] = [f"  [bold cyan]◆ {name}[/]"]

    if name == ActorComponent.__name__:
        ac = ActorComponent(**data)
        if ac.character_sheet_name:
            lines.append(f"    职业模板：[green]{ac.character_sheet_name}[/]")
        if ac.current_stage:
            lines.append(f"    当前场景：[yellow]{ac.current_stage}[/]")

    elif name == AppearanceComponent.__name__:
        app_comp = AppearanceComponent(**data)
        if app_comp.base_body:
            lines.append("    [bold]基础体型：[/]")
            lines.append(f"    [dim]{app_comp.base_body}[/]")
        if app_comp.appearance:
            lines.append("    [bold]当前外观：[/]")
            lines.append(f"    [dim]{app_comp.appearance}[/]")
        if not app_comp.base_body and not app_comp.appearance:
            lines.append("    [dim]（暂无描述）[/]")

    elif name == CharacterStatsComponent.__name__:
        sc = CharacterStatsComponent(**data)
        s = sc.stats
        lines.append(
            f"    HP [bold green]{s.hp}[/] / [green]{s.max_hp}[/]"
            f"   攻击 [bold red]{s.attack}[/]"
            f"   防御 [bold blue]{s.defense}[/]"
            f"   行动 [bold]{s.energy}[/]"
            f"   速度 [bold]{s.speed}[/]"
        )

    elif name == EquipmentComponent.__name__:
        ec = EquipmentComponent(**data)
        lines.append(f"    武器：[yellow]{ec.weapon or '（空）'}[/]")
        lines.append(f"    防具：[yellow]{ec.armor or '（空）'}[/]")
        lines.append(f"    饰品：[yellow]{ec.accessory or '（空）'}[/]")

    elif name == InventoryComponent.__name__:
        ic = InventoryComponent(**data)
        equipped: Set[str] = context.get("equipped", set())
        if not ic.items:
            lines.append("    [dim]（空）[/]")
        else:
            for item in ic.items:
                lines.append(_render_item(item, equipped))

    elif name == ArchetypeComponent.__name__:
        arc_comp = ArchetypeComponent(**data)
        if not arc_comp.archetypes:
            lines.append("    [dim]（暂无原型约束）[/]")
        else:
            for i, archetype in enumerate(arc_comp.archetypes, 1):
                lines.append(f"    [dim]{i}.[/] {archetype.description}")

    elif name == DrawDeckComponent.__name__:
        ddc = DrawDeckComponent(**data)
        if not ddc.cards:
            lines.append("    [dim]（空）[/]")
        else:
            lines.append(f"    共 [bold]{len(ddc.cards)}[/] 张")

    elif name == DiscardDeckComponent.__name__:
        disc = DiscardDeckComponent(**data)
        if not disc.cards:
            lines.append("    [dim]（空）[/]")
        else:
            lines.append(f"    共 [bold]{len(disc.cards)}[/] 张已打出")

    else:
        # 通用展示：key-value，跳过 name 字段
        for k, v in data.items():
            if k == "name":
                continue
            lines.append(f"    [dim]{k}：[/]{v}")

    return "\n".join(lines)


STATUS_HEADER = """\
[bold cyan]╔══════════════════════════════════════════════════╗[/]
[bold cyan]║              当前状态                           ║[/]
[bold cyan]╚══════════════════════════════════════════════════╝[/]

[dim]按 Escape 返回主场景。[/]
"""


class PlayerStatusScreen(Screen[None]):
    """当前状态 Screen：显示玩家/世界设定/角色实体组件详情。"""

    CSS = """
    PlayerStatusScreen {
        align: center middle;
    }

    #status-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    def __init__(self) -> None:
        super().__init__()

    def compose(self) -> ComposeResult:
        yield RichLog(id="status-log", highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(STATUS_HEADER)
        self._load_status()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @work
    async def _load_status(self) -> None:
        log = self.query_one(RichLog)
        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        if app.session is None:
            return
        user_name = app.session.user_name
        game_name = app.session.game_name
        bp = app.session.blueprint
        player_actor = bp.player_actor

        # 基础信息
        log.write(
            f"[bold yellow]── 基本信息 ──────────────────────────────────────[/]\n"
            f"  玩家：[bold]{user_name}[/]\n"
            f"  游戏：[bold]{game_name}[/]\n"
            f"  玩家角色：[bold cyan]{display_name(player_actor) if player_actor else '（未知）'}[/]\n"
        )

        # 世界设定
        if bp:
            log.write(
                f"[bold yellow]── 游戏世界设定 ──────────────────────────────────────[/]\n"
                f"{bp.campaign_setting}\n"
            )

        # 玩家角色实体详情
        if not player_actor:
            return

        log.write(f"[dim]正在查询玩家角色实体：{player_actor} ...[/]")
        logger.info(f"PlayerStatusScreen: 查询玩家角色实体 player_actor={player_actor}")
        try:
            resp = await fetch_entities_details(user_name, game_name, [player_actor])
            if not resp.entities_serialization:
                log.write(f"[yellow]未找到玩家角色实体：{player_actor}[/]")
            else:
                for entity in resp.entities_serialization:
                    log.write(
                        f"[bold yellow]── {display_name(entity.name)} ──────────────────────────────────────[/]"
                    )
                    # 收集装备槽上下文，供 InventoryComponent 标注「装备中」
                    comp_map = {comp.name: comp.data for comp in entity.components}
                    equip_data = comp_map.get(EquipmentComponent.__name__, {})
                    equipped_names: Set[str] = set()
                    if equip_data:
                        ec = EquipmentComponent(**equip_data)
                        equipped_names = {
                            v for v in (ec.weapon, ec.armor, ec.accessory) if v
                        }
                    render_context: Dict[str, Any] = {"equipped": equipped_names}
                    # 按预定义顺序渲染组件
                    sorted_comps = sorted(
                        entity.components,
                        key=lambda c: (
                            _COMPONENT_ORDER.index(c.name)
                            if c.name in _COMPONENT_ORDER
                            else len(_COMPONENT_ORDER)
                        ),
                    )
                    for comp in sorted_comps:
                        rendered = _render_component(
                            comp.name, comp.data, render_context
                        )
                        if rendered:
                            log.write(rendered)
                    log.write("")
            logger.info(f"PlayerStatusScreen: 查询成功 player_actor={player_actor}")
        except Exception as e:
            logger.error(
                f"PlayerStatusScreen: 查询失败 player_actor={player_actor} error={e}"
            )
            log.write(f"[bold red]❌ 玩家角色实体查询失败: {e}[/]")
