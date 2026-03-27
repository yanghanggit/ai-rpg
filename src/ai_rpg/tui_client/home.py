"""游戏主场景 Screen（Home 状态）"""

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, RichLog, Static

from .server_client import fetch_stages_state

HOME_HEADER = """\
[bold cyan]╔══════════════════════════════════════════════════╗[/]
[bold cyan]║        AI RPG TCG  游戏主场景                   ║[/]
[bold cyan]╚══════════════════════════════════════════════════╝[/]
"""

HELP_TEXT = """\
[bold yellow]可用命令：[/]

  [bold green]/help  [/]   显示此帮助信息
  [bold green]/status[/]   显示当前玩家与游戏状态
  [bold green]/stages[/]   查询全部场景与角色分布

"""


class HomeScreen(Screen[None]):
    """游戏主场景 Screen（Screen 3）。新游戏创建成功后进入此界面。"""

    CSS = """
    HomeScreen {
        align: center middle;
    }

    #home-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #home-input-row {
        height: 3;
        dock: bottom;
    }

    #home-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #home-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("ctrl+c", "app.quit", "退出"),
    ]

    def __init__(self, user_name: str, game_name: str) -> None:
        super().__init__()
        self._user_name = user_name
        self._game_name = game_name

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="home-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="home-input-row"):
            yield Static("> ", id="home-prompt")
            yield Input(placeholder="输入命令...", id="home-input")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(HOME_HEADER)
        log.write(
            f"[bold green]✅ 欢迎，{self._user_name}！游戏 [{self._game_name}] 已就绪。[/]"
        )
        log.write(HELP_TEXT)
        self.query_one(Input).focus()

    @on(Input.Submitted, "#home-input")
    def handle_command(self, event: Input.Submitted) -> None:
        cmd = event.value.strip().lower()
        event.input.clear()
        log = self.query_one(RichLog)

        if not cmd:
            return

        log.write(f"[dim]> {cmd}[/]")

        if cmd == "/help":
            log.write(HELP_TEXT)
        elif cmd == "/status":
            log.write(
                f"[bold yellow]── 当前状态 ──────────────────────────────────────[/]\n"
                f"  玩家：[bold]{self._user_name}[/]\n"
                f"  游戏：[bold]{self._game_name}[/]\n"
            )
        elif cmd == "/stages":
            self._fetch_stages()
        else:
            log.write(f"[red]未知命令：{cmd}，输入 /help 查看可用命令。[/]")

    @work
    async def _fetch_stages(self) -> None:
        log = self.query_one(RichLog)
        log.write("[dim]正在查询场景状态...[/]")
        try:
            resp = await fetch_stages_state(self._user_name, self._game_name)
            log.write("[bold yellow]── 场景与角色分布 ────────────────────────────────[/]")
            if not resp.mapping:
                log.write("  [dim]（暂无场景数据）[/]")
            else:
                for stage, actors in resp.mapping.items():
                    actors_str = "、".join(actors) if actors else "[dim]（空）[/]"
                    log.write(f"  [bold cyan]{stage}[/] → {actors_str}")
            log.write("")
        except Exception as e:
            log.write(f"[bold red]❌ 查询失败: {e}[/]")
