"""玩家当前状态 Screen"""

from typing import Any, Dict

from loguru import logger
from textual import work
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import RichLog

from .server_client import fetch_entities_details


def _render_component(name: str, data: Dict[str, Any]) -> str:
    """将组件 data 渲染为可读的 Rich markup 字符串。返回空字符串表示跳过此组件。"""
    # 过滤掉纯冗余组件
    if name in ("IdentityComponent", "AllyComponent"):
        return ""

    lines: list[str] = [f"  [bold cyan]◆ {name}[/]"]

    if name == "ActorComponent":
        sheet = data.get("character_sheet_name", "")
        stage = data.get("current_stage", "")
        if sheet:
            lines.append(f"    职业模板：[green]{sheet}[/]")
        if stage:
            lines.append(f"    当前场景：[yellow]{stage}[/]")

    elif name == "AppearanceComponent":
        base_body = data.get("base_body", "")
        appearance = data.get("appearance", "")
        # 两者内容通常相近，优先显示 appearance；若为空则 base_body
        text = appearance or base_body
        if text:
            lines.append(f"    [dim]{text}[/]")
        else:
            lines.append("    [dim]（暂无描述）[/]")

    elif name == "CharacterStatsComponent":
        stats = data.get("stats", {})
        hp = stats.get("hp", "?")
        max_hp = stats.get("max_hp", "?")
        atk = stats.get("attack", "?")
        defense = stats.get("defense", "?")
        lines.append(
            f"    HP [bold green]{hp}[/] / [green]{max_hp}[/]"
            f"   攻击 [bold red]{atk}[/]"
            f"   防御 [bold blue]{defense}[/]"
        )

    elif name == "InventoryComponent":
        items = data.get("items", [])
        if not items:
            lines.append("    物品栏：[dim]（空）[/]")
        else:
            lines.append("    物品栏：")
            for item in items:
                lines.append(f"      [yellow]• {item}[/]")

    elif name == "PlayerComponent":
        player_name = data.get("player_name", "")
        if player_name:
            lines.append(f"    玩家账号：[dim]{player_name}[/]")

    elif name == "ExpeditionRosterComponent":
        members = data.get("members", [])
        if not members:
            lines.append("    远征队：[dim]（空）[/]")
        else:
            lines.append("    远征队成员：")
            for m in members:
                lines.append(f"      [cyan]• {m}[/]")

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

    def __init__(self, user_name: str, game_name: str) -> None:
        super().__init__()
        self._user_name = user_name
        self._game_name = game_name

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
        bp = app.session_blueprint
        player_actor = bp.player_actor if bp else None

        # 基础信息
        log.write(
            f"[bold yellow]── 基本信息 ──────────────────────────────────────[/]\n"
            f"  玩家：[bold]{self._user_name}[/]\n"
            f"  游戏：[bold]{self._game_name}[/]\n"
            f"  玩家角色：[bold cyan]{player_actor or '（未知）'}[/]\n"
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
            resp = await fetch_entities_details(
                self._user_name, self._game_name, [player_actor]
            )
            if not resp.entities_serialization:
                log.write(f"[yellow]未找到玩家角色实体：{player_actor}[/]")
            else:
                for entity in resp.entities_serialization:
                    log.write(
                        f"[bold yellow]── {entity.name} ──────────────────────────────────────[/]"
                    )
                    for comp in entity.components:
                        rendered = _render_component(comp.name, comp.data)
                        if rendered:
                            log.write(rendered)
                    log.write("")
            logger.info(f"PlayerStatusScreen: 查询成功 player_actor={player_actor}")
        except Exception as e:
            logger.error(
                f"PlayerStatusScreen: 查询失败 player_actor={player_actor} error={e}"
            )
            log.write(f"[bold red]❌ 玩家角色实体查询失败: {e}[/]")
