"""AI RPG 游戏客户端主应用（Textual TUI）"""

from typing import Callable, Optional
from textual.app import App, ComposeResult
from textual.screen import Screen
from .session import GameSession
from .connecting import ConnectingScreen


class GameClient(App[None]):
    """游戏客户端主应用。启动后推入 launch_screen 指定的 Screen（由调用方决定）。"""

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
    ]

    # ── 会话状态：登录后写入，登出后清空 ──
    session: Optional[GameSession] = None

    def __init__(
        self, *, launch_screen: Callable[[], "Screen[None]"] = ConnectingScreen
    ) -> None:
        """launch_screen：启动时 push 的初始 Screen 工厂函数，默认 ConnectingScreen
        （正常登录流程）。由调用方（如 scripts/run_tui_client.py）根据命令行参数决定
        传入哪个 Screen，方便开发时跳过登录流程直接进入指定页面调试。"""
        super().__init__()
        self._launch_screen = launch_screen

    def compose(self) -> ComposeResult:
        # 保留 App 默认空 Screen 作为栈底，防止 switch_screen 时栈清空
        yield from []

    def on_mount(self) -> None:
        self.push_screen(self._launch_screen())

    def clear_session(self) -> None:
        """登出时清空会话状态。"""
        self.session = None
