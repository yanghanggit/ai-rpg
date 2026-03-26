"""AI RPG 游戏客户端主应用（Textual TUI）"""

import json

from textual import on, work
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input, RichLog
from textual.containers import Vertical, Horizontal

from .server_client import GAME_SERVER_BASE_URL, fetch_server_info


WELCOME_TEXT = """\
[bold cyan]╔══════════════════════════════════════════════════╗[/]
[bold cyan]║        AI RPG TCG  游戏客户端  v0.0.1           ║[/]
[bold cyan]╚══════════════════════════════════════════════════╝[/]

欢迎！这是基于 [bold green]Textual[/] 构建的游戏客户端。

当前为 [bold yellow]Hello World 测试版[/]，用于验证 TUI 环境正常。

[dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/]
在下方输入框中输入任意内容，按 Enter 发送。
按 [bold]Ctrl+C[/] 或 [bold]Q[/] 退出。
"""


class GameClient(App[None]):
    """AI RPG 游戏客户端主应用"""

    CSS = """
    Screen {
        background: $surface;
    }

    #main-layout {
        height: 1fr;
    }

    #log-panel {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #input-row {
        height: 3;
        padding: 0 1;
    }

    #prompt-label {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #cmd-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "退出"),
        ("q", "quit", "退出"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main-layout"):
            yield RichLog(id="log-panel", highlight=True, markup=True, wrap=True)
            with Horizontal(id="input-row"):
                yield Static("> ", id="prompt-label")
                yield Input(placeholder="输入指令...", id="cmd-input")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(WELCOME_TEXT)
        log.write(f"[dim]Textual 版本: {self._get_textual_version()}[/]")
        self.query_one(Input).focus()
        self.connect_to_server()

    @work
    async def connect_to_server(self) -> None:
        log = self.query_one(RichLog)
        log.write(f"[dim]正在连接服务器 {GAME_SERVER_BASE_URL} ...[/]")
        try:
            data = await fetch_server_info()
            formatted = json.dumps(data, ensure_ascii=False, indent=2)
            log.write(f"[bold green]✅ 服务器已连接[/]")
            log.write(formatted)
        except Exception as e:
            log.write(f"[bold red]❌ 连接失败: {e}[/]")
        log.scroll_end(animate=False)

    def _get_textual_version(self) -> str:
        try:
            import textual

            return textual.__version__
        except Exception:
            return "unknown"

    @on(Input.Submitted)
    def handle_input(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return

        log = self.query_one(RichLog)
        log.write(f"[bold green]>[/] {text}")

        # 简单的回显逻辑（占位，后续替换为真实 API 调用）
        if text.lower() in ("help", "帮助", "?"):
            log.write(
                "[yellow]可用命令（开发中）：[/]\n"
                "  help      — 显示帮助\n"
                "  login     — 登录服务器\n"
                "  new       — 创建新游戏\n"
                "  advance   — 推进剧情\n"
                "  q / quit  — 退出"
            )
        elif text.lower() in ("q", "quit", "exit", "退出"):
            self.exit()
        else:
            log.write(f"[dim]（服务器连接尚未实现，回显：{text}）[/]")

        event.input.clear()
