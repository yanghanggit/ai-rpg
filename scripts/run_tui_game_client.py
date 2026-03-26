"""AI RPG 游戏客户端（Textual TUI）

临时 Hello World 版本，用于验证 Textual 环境正常运行。

终端本地启动：
    uv run python scripts/run_tui_game_client.py

浏览器访问模式（供局域网/公网访问）：
    uv run python scripts/run_tui_game_client.py --web
    uv run python scripts/run_tui_game_client.py --web --port 8080
    然后在浏览器打开 http://localhost:8080

局域网模式（同事可通过你的 IP 访问）：
    # 先查询本机局域网 IP：
    ipconfig getifaddr en0           # 例如得到 192.168.1.100
    # 然后用实际 IP 启动（--public-url 告诉客户端用哪个地址连 WebSocket）：
    uv run python scripts/run_tui_game_client.py --web --host 0.0.0.0 --port 8080 --public-url http://192.168.1.100:8080
    # 同事浏览器打开 http://192.168.1.100:8080
"""

import sys
import os

import click
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Static, Input, RichLog
from textual.containers import Vertical, Horizontal
from textual import on


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


@click.command()
@click.option(
    "--web",
    is_flag=True,
    default=False,
    help="以浏览器模式启动（通过 textual-serve 提供 Web 访问）",
)
@click.option("--port", default=8080, show_default=True, help="浏览器模式监听端口")
@click.option(
    "--host",
    default="localhost",
    show_default=True,
    help="浏览器模式监听地址（局域网用 0.0.0.0）",
)
@click.option(
    "--public-url",
    default=None,
    help="WebSocket 公开地址，局域网模式必填，例如 http://192.168.1.100:8080",
)
def main(web: bool, port: int, host: str, public_url: str | None) -> None:
    if web:
        from textual_serve.server import Server

        command = f"{sys.executable} {os.path.abspath(__file__)}"
        server = Server(command, host=host, port=port, public_url=public_url)
        display_url = public_url or f"http://{host}:{port}"
        click.echo(f"启动 Web 模式，请在浏览器打开: {display_url}")
        server.serve()
    else:
        app = GameClient()
        app.run()


if __name__ == "__main__":
    main()
