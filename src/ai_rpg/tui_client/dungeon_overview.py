"""地下城总览 Screen"""

from typing import List

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Input, RichLog, Static

from ..models import Dungeon
from .server_client import fetch_dungeon_list

OVERVIEW_HEADER = """\
[bold cyan]── 地下城总览 ──────────────────────────────────────[/]

输入编号查看副本详情，[bold]/list[/] 返回列表，[bold]Escape[/] 返回。
"""


class DungeonOverviewScreen(Screen[None]):
    """地下城总览 Screen：列出全部地下城副本，按编号查看详情。"""

    CSS = """
    DungeonOverviewScreen {
        align: center middle;
    }

    #dungeon-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #dungeon-input-row {
        height: 3;
        dock: bottom;
    }

    #dungeon-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #dungeon-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    def __init__(self, user_name: str, game_name: str) -> None:
        super().__init__()
        self._user_name = user_name
        self._game_name = game_name
        self._dungeons: List[Dungeon] = []

    def compose(self) -> ComposeResult:
        yield RichLog(id="dungeon-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="dungeon-input-row"):
            yield Static("> ", id="dungeon-prompt")
            yield Input(placeholder="输入编号查看副本详情...", id="dungeon-input")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(OVERVIEW_HEADER)
        self._load_dungeons()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Input.Submitted, "#dungeon-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if not raw:
            return

        if raw.lower() == "/list":
            log.clear()
            log.write(OVERVIEW_HEADER)
            self._render_list(log)
            return

        if not self._dungeons:
            log.write("[yellow]地下城列表尚未加载，请稍候...[/]")
            return

        if not raw.isdigit():
            log.write("[red]请输入有效编号（数字）或 /list 返回列表[/]")
            return

        idx = int(raw) - 1
        if idx < 0 or idx >= len(self._dungeons):
            log.write(
                f"[red]编号超出范围，请输入 1–{len(self._dungeons)} 之间的数字[/]"
            )
            return

        dungeon = self._dungeons[idx]
        log.write(f"[dim]> 查看副本：{dungeon.name}[/]")
        self._show_dungeon(dungeon, log)

    def _render_list(self, log: RichLog) -> None:
        """将已缓存的地下城列表渲染到 log。"""
        if not self._dungeons:
            log.write("[yellow]地下城列表尚未加载，请稍候...[/]")
            return
        log.write("[bold yellow]── 可用副本 ──────────────────────────────────────[/]")
        for i, dungeon in enumerate(self._dungeons, start=1):
            preview = dungeon.ecology[:40].replace("\n", " ")
            room_count = len(dungeon.rooms)
            log.write(
                f"  [bold]{i}.[/] [bold cyan]{dungeon.name}[/]"
                f"  [dim]{preview}…  ({room_count} 个房间)[/]"
            )
        log.write("")

    def _show_dungeon(self, dungeon: Dungeon, log: RichLog) -> None:
        """内联渲染地下城详情（纯同步，数据已在内存中）。"""
        log.write(
            f"[bold yellow]── 副本：{dungeon.name} ──────────────────────────────────────[/]"
        )
        log.write(f"  [bold]生态环境：[/] {dungeon.ecology}")
        log.write(f"  [bold]房间数：[/]   {len(dungeon.rooms)}")
        log.write("")

        for i, room in enumerate(dungeon.rooms, start=1):
            stage = room.stage
            log.write(f"  [bold cyan]房间 {i}：[/][green]{stage.name}[/]")
            if stage.actors:
                for actor in stage.actors:
                    stats = actor.character_stats
                    log.write(
                        f"    · [bold]{actor.name}[/]"
                        f"  HP:[yellow]{stats.max_hp}[/]"
                        f"  ATK:[red]{stats.attack}[/]"
                        f"  DEF:[blue]{stats.defense}[/]"
                    )
            else:
                log.write("    [dim]（无敌人）[/]")
        log.write("")

    @work
    async def _load_dungeons(self) -> None:
        log = self.query_one(RichLog)
        logger.info("_load_dungeons: 正在获取地下城列表...")
        try:
            resp = await fetch_dungeon_list()
            self._dungeons = resp.dungeons
            if self._dungeons:
                self._render_list(log)
            else:
                log.write("[yellow]服务器暂无可用地下城。[/]")
            logger.info(f"_load_dungeons: 获取成功，共 {len(self._dungeons)} 个地下城")
        except Exception as e:
            logger.error(f"_load_dungeons: 获取失败 error={e}")
            log.write(f"[bold red]❌ 地下城列表加载失败: {e}[/]")
