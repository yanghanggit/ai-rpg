"""主菜单 Screen"""

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Input, RichLog, Static

MENU_TEXT = """\
[bold cyan]╔══════════════════════════════════════════════════╗[/]
[bold cyan]║        AI RPG TCG  游戏客户端  v0.0.1           ║[/]
[bold cyan]╚══════════════════════════════════════════════════╝[/]
"""

MENU_OPTIONS = """\
[bold yellow]请选择操作：[/]

  [bold green]1[/]  开始新游戏
  [bold red]q[/]  退出

"""


class MainMenuScreen(Screen[None]):
    """主菜单 Screen，显示服务器连接状态和操作选项。"""

    CSS = """
    MainMenuScreen {
        align: center middle;
    }

    #menu-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #menu-input-row {
        height: 3;
        dock: bottom;
    }

    #menu-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #menu-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "app.quit", "退出"),
    ]

    def __init__(self, server_info_msg: str = "") -> None:
        super().__init__()
        self._server_info_msg = server_info_msg

    def compose(self) -> ComposeResult:
        yield RichLog(id="menu-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="menu-input-row"):
            yield Static("> ", id="menu-prompt")
            yield Input(placeholder="输入选项编号...", id="menu-input")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(MENU_TEXT)
        if self._server_info_msg:
            log.write(self._server_info_msg)
        log.write(MENU_OPTIONS)
        self.query_one(Input).focus()

    @on(Input.Submitted, "#menu-input")
    def handle_menu_input(self, event: Input.Submitted) -> None:
        choice = event.value.strip().lower()
        event.input.clear()

        if choice == "1":
            from .new_game import NewGameScreen

            self.app.push_screen(NewGameScreen())
        elif choice in ("q", "quit", "exit", "退出"):
            self.app.exit()
        else:
            log = self.query_one(RichLog)
            log.write(f"[dim]未知选项：{choice}，请输入 1 或 q[/]")
