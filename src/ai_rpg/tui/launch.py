"""启动 Screen：合并原 ConnectingScreen 与 MainMenuScreen，显示基础信息与命令列表。"""

import json

from loguru import logger
from rich.syntax import Syntax
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Input, RichLog, Static

from .config import server_config
from .server_client import fetch_server_info

LAUNCH_TEXT = """\
[bold cyan]╔══════════════════════════════════════════════════╗[/]
[bold cyan]║        AI RPG DBG  游戏客户端  v0.0.1           ║[/]
[bold cyan]╚══════════════════════════════════════════════════╝[/]
"""

COMMANDS_TEXT = """\
[bold yellow]请输入命令：[/]

  [bold green]1[/]  获取服务器信息
  [bold green]2[/]  开始新游戏
  [bold green]0[/]  清除屏幕

[dim]  Escape  退出游戏[/]

"""


class LaunchScreen(Screen[None]):
    """启动 Screen：展示服务器地址等基础信息，并通过命令列表触发操作。"""

    CSS = """
    LaunchScreen {
        align: center middle;
    }

    #launch-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #launch-input-row {
        height: 3;
        dock: bottom;
    }

    #launch-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #launch-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "app.quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        yield RichLog(id="launch-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="launch-input-row"):
            yield Static("> ", id="launch-prompt")
            yield Input(placeholder="输入命令编号...", id="launch-input")

    def on_mount(self) -> None:
        self._write_banner()
        self.query_one(Input).focus()

    def _write_banner(self) -> None:
        log = self.query_one(RichLog)
        log.write(LAUNCH_TEXT)
        log.write(f"[dim]服务器地址: {server_config.base_url}[/]")
        log.write(COMMANDS_TEXT)

    @on(Input.Submitted, "#launch-input")
    def handle_command_input(self, event: Input.Submitted) -> None:
        choice = event.value.strip().lower()
        event.input.clear()

        if choice == "1":
            self._fetch_server_info()
        elif choice == "2":
            from .new_game import NewGameScreen

            self.app.push_screen(NewGameScreen())
        elif choice == "0":
            self.query_one(RichLog).clear()
            self._write_banner()
        else:
            log = self.query_one(RichLog)
            log.write(f"[dim]未知命令：{choice}，请输入 0/1/2[/]")

    @work
    async def _fetch_server_info(self) -> None:
        log = self.query_one(RichLog)
        log.write(f"[dim]正在获取服务器信息 {server_config.base_url} ...[/]")
        logger.info(f"fetch_server_info: 请求 url={server_config.base_url}")
        try:
            info = await fetch_server_info()
            logger.info(f"fetch_server_info: 成功 url={server_config.base_url}")
            log.write("[bold green]✅ 服务器信息：[/]")
            info_json = json.dumps(info, indent=2, ensure_ascii=False)
            log.write(Syntax(info_json, "json", theme="ansi_dark", word_wrap=True))
        except Exception as e:
            logger.error(
                f"fetch_server_info: 失败 url={server_config.base_url} error={e}"
            )
            log.write(f"[bold red]❌ 获取失败: {e}[/]")
            log.write("[dim]请确认游戏服务器已启动。[/]")
