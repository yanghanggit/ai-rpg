"""玩家当前状态 Screen"""

from typing import Any, Dict

from loguru import logger
from ..models import (
    IdentityComponent,
    NPCComponent,
    AppearanceComponent,
    ActorComponent,
    CharacterStatsComponent,
    InventoryComponent,
    PlayerComponent,
    PartyRosterComponent,
    KeywordComponent,
    DrawPileComponent,
    ExhaustPileComponent,
    DiscardPileComponent,
    StorageComponent,
)
from textual import work
from textual.app import ComposeResult
from textual.widgets import RichLog

from .base import BaseGameScreen
from .server_client import fetch_entities_details
from .utils import display_name, render_item


# 组件渲染顺序（靠前的优先展示）
_COMPONENT_ORDER: list[str] = [
    ActorComponent.__name__,
    CharacterStatsComponent.__name__,
    AppearanceComponent.__name__,
    InventoryComponent.__name__,
    StorageComponent.__name__,
    KeywordComponent.__name__,
    DrawPileComponent.__name__,
    ExhaustPileComponent.__name__,
    DiscardPileComponent.__name__,
]


def _render_component(name: str, data: Dict[str, Any], context: Dict[str, Any]) -> str:
    """将组件 data 渲染为可读的 Rich markup 字符串。返回空字符串表示跳过此组件。"""
    # 过滤掉纯冗余组件
    if name in (
        IdentityComponent.__name__,
        NPCComponent.__name__,
        PlayerComponent.__name__,
        PartyRosterComponent.__name__,
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

    elif name == InventoryComponent.__name__:
        inv = InventoryComponent(**data)
        if not inv.items:
            lines.append("    [dim]（背包为空）[/]")
        else:
            lines.append(f"    共 [bold]{len(inv.items)}[/] 件道具：")
            for item in inv.items:
                lines.append(
                    "    "
                    + render_item(item if isinstance(item, dict) else item.model_dump())
                )

    elif name == StorageComponent.__name__:
        storage = StorageComponent(**data)
        if not storage.items:
            lines.append("    [dim]（储物箱为空）[/]")
        else:
            lines.append(f"    共 [bold]{len(storage.items)}[/] 件道具：")
            for item in storage.items:
                lines.append(
                    "    "
                    + render_item(item if isinstance(item, dict) else item.model_dump())
                )

    elif name == KeywordComponent.__name__:
        keyword_comp = KeywordComponent(**data)
        if not keyword_comp.keywords:
            lines.append("    [dim]（暂无关键词约束）[/]")
        else:
            for i, kw in enumerate(keyword_comp.keywords, 1):
                lines.append(f"    [dim]{i}.[/] {kw.description}")

    elif name == DrawPileComponent.__name__:
        ddc = DrawPileComponent(**data)
        if not ddc.cards:
            lines.append("    [dim]（空）[/]")
        else:
            lines.append(f"    共 [bold]{len(ddc.cards)}[/] 张")

    elif name == ExhaustPileComponent.__name__:
        disc = ExhaustPileComponent(**data)
        if not disc.cards:
            lines.append("    [dim]（空）[/]")
        else:
            lines.append(f"    共 [bold]{len(disc.cards)}[/] 张已消耗")
    elif name == DiscardPileComponent.__name__:
        played = DiscardPileComponent(**data)
        if not played.cards:
            lines.append("    [dim](空)[/]")
        else:
            lines.append(f"    共 [bold]{len(played.cards)}[/] 张已弃置")
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


class PlayerStatusScreen(BaseGameScreen):
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
        app = self.game_client
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
                    # 按预定义顺序渲染组件
                    render_context: Dict[str, Any] = {"equipped": set()}
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
