"""服务器连接 Screen"""

from loguru import logger
from textual import work
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer, Header, RichLog

from .config import GAME_SERVER_BASE_URL
from .server_client import fetch_server_info

CONNECTING_TEXT = """\
[bold cyan]╔══════════════════════════════════════════════════╗[/]
[bold cyan]║        AI RPG TCG  游戏客户端  v0.0.1           ║[/]
[bold cyan]╚══════════════════════════════════════════════════╝[/]
"""


class ConnectingScreen(Screen[None]):
    """启动连接 Screen：连接服务器后切换到主菜单。"""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="startup-log", highlight=True, markup=True, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(CONNECTING_TEXT)
        log.write(f"[dim]Textual 版本: {self._get_textual_version()}[/]")
        self.connect_to_server()

    @work
    async def connect_to_server(self) -> None:
        log = self.query_one(RichLog)
        log.write(f"[dim]正在连接服务器 {GAME_SERVER_BASE_URL} ...[/]")
        logger.info(f"connect_to_server: 尝试连接 url={GAME_SERVER_BASE_URL}")
        try:
            await fetch_server_info()
            info_msg = (
                f"[bold green]✅ 服务器已连接，base_url: {GAME_SERVER_BASE_URL}[/]"
            )
            logger.info(f"connect_to_server: 连接成功 url={GAME_SERVER_BASE_URL}")
            from .main_menu import MainMenuScreen

            self.app.switch_screen(MainMenuScreen(server_info_msg=info_msg))
        except Exception as e:
            logger.error(
                f"connect_to_server: 连接失败 url={GAME_SERVER_BASE_URL} error={e}"
            )
            log.write(f"[bold red]❌ 连接失败: {e}[/]")
            log.write("[dim]请确认游戏服务器已启动，然后重新运行客户端。[/]")

    def _get_textual_version(self) -> str:
        try:
            import textual

            return textual.__version__
        except Exception:
            return "unknown"
