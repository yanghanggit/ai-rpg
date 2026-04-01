"""远征队管理 Screen"""

from typing import List, Set

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Input, RichLog, Static

from .server_client import (
    fetch_entities_details,
    home_roster_add,
    home_roster_remove,
)

ROSTER_HEADER = """\
[bold cyan]── 远征队管理 ──────────────────────────────────────[/]

输入编号 toggle 成员（未在队 → 加入，在队 → 移除），[bold]Escape[/] 返回。
"""


class RosterScreen(Screen[None]):
    """远征队管理 Screen：列出可加入的盟友，用编号 toggle 加入/移除远征队。"""

    CSS = """
    RosterScreen {
        align: center middle;
    }

    #roster-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #roster-input-row {
        height: 3;
        dock: bottom;
    }

    #roster-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #roster-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def __init__(self, user_name: str, game_name: str) -> None:
        super().__init__()
        self._user_name = user_name
        self._game_name = game_name
        self._ally_list: List[str] = []
        self._current_roster: Set[str] = set()

    def compose(self) -> ComposeResult:
        yield RichLog(id="roster-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="roster-input-row"):
            yield Static("> ", id="roster-prompt")
            yield Input(placeholder="输入编号 toggle ...", id="roster-input")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(ROSTER_HEADER)
        self._load_roster()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def _render_list(self) -> None:
        log = self.query_one(RichLog)
        log.write(
            "[bold yellow]── 当前盟友列表 ──────────────────────────────────────[/]"
        )
        for i, ally in enumerate(self._ally_list, 1):
            in_roster = ally in self._current_roster
            marker = "[bold green][✓][/]" if in_roster else "[ ]"
            log.write(f"  [bold green]{i}.[/] {marker} [cyan]{ally}[/]")
        log.write("")
        log.write("[dim]输入编号切换成员状态：[/]")

    @on(Input.Submitted, "#roster-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if not raw:
            return

        if not self._ally_list:
            log.write("[yellow]盟友列表尚未加载，请稍候...[/]")
            return

        if not raw.isdigit():
            log.write("[red]请输入有效的编号。[/]")
            return

        idx = int(raw) - 1
        if idx < 0 or idx >= len(self._ally_list):
            log.write(f"[red]编号超出范围，请输入 1 ~ {len(self._ally_list)}。[/]")
            return

        ally_name = self._ally_list[idx]
        if ally_name in self._current_roster:
            self._do_remove(ally_name)
        else:
            self._do_add(ally_name)

    @work
    async def _load_roster(self) -> None:
        """从 Blueprint 获取盟友列表，从服务器读取当前远征队名单。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在加载远征队信息...[/]")

        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        bp = app.session_blueprint
        if bp is None:
            log.write("[red]❌ 无法取得蓝图信息。[/]")
            return

        player_actor = bp.player_actor
        self._ally_list = [
            actor.name for actor in bp.actors if actor.name != player_actor
        ]

        if not self._ally_list:
            log.write("[yellow]没有可加入远征队的盟友。[/]")
            return

        # 从服务器读取 player entity，取得 ExpeditionRosterComponent
        try:
            resp = await fetch_entities_details(
                self._user_name, self._game_name, [player_actor]
            )
            for entity in resp.entities_serialization:
                for comp in entity.components:
                    if comp.name == "ExpeditionRosterComponent":
                        members = comp.data.get("members", [])
                        self._current_roster = set(members)
                        break

            logger.info(
                f"RosterScreen._load_roster: 加载完成 ally_list={self._ally_list} roster={self._current_roster}"
            )
        except Exception as e:
            logger.error(
                f"RosterScreen._load_roster: 查询 player entity 失败 error={e}"
            )
            log.write(f"[bold red]❌ 读取当前远征队失败: {e}[/]")
            return

        self._render_list()

    @work
    async def _do_add(self, ally_name: str) -> None:
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True
        log.write(f"[dim]▶ 正在将 {ally_name} 加入远征队...[/]")
        logger.info(f"RosterScreen._do_add: ally_name={ally_name}")
        try:
            await home_roster_add(self._user_name, self._game_name, ally_name)
            self._current_roster.add(ally_name)
            log.write(f"[bold green]✅ {ally_name} 已加入远征队[/]")
            logger.info(f"RosterScreen._do_add: 成功 ally_name={ally_name}")
        except Exception as e:
            logger.error(f"RosterScreen._do_add: 失败 ally_name={ally_name} error={e}")
            log.write(f"[bold red]❌ 加入失败: {e}[/]")
        finally:
            inp.disabled = False
            inp.focus()
        self._render_list()

    @work
    async def _do_remove(self, ally_name: str) -> None:
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True
        log.write(f"[dim]▶ 正在将 {ally_name} 从远征队移除...[/]")
        logger.info(f"RosterScreen._do_remove: ally_name={ally_name}")
        try:
            await home_roster_remove(self._user_name, self._game_name, ally_name)
            self._current_roster.discard(ally_name)
            log.write(f"[bold green]✅ {ally_name} 已从远征队移除[/]")
            logger.info(f"RosterScreen._do_remove: 成功 ally_name={ally_name}")
        except Exception as e:
            logger.error(
                f"RosterScreen._do_remove: 失败 ally_name={ally_name} error={e}"
            )
            log.write(f"[bold red]❌ 移除失败: {e}[/]")
        finally:
            inp.disabled = False
            inp.focus()
        self._render_list()
