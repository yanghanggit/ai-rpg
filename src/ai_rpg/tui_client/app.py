"""AI RPG 游戏客户端主应用（Textual TUI）"""

from typing import Optional

from textual.app import App, ComposeResult

from .session import GameSession


class GameClient(App[None]):
    """游戏客户端主应用。启动后推入 ConnectingScreen，由各 Screen 承载具体 UI。"""

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
    ]

    # ── 会话状态：登录后写入，登出后清空 ──
    session: Optional[GameSession] = None

    def compose(self) -> ComposeResult:
        # 保留 App 默认空 Screen 作为栈底，防止 switch_screen 时栈清空
        yield from []

    def on_mount(self) -> None:
        from .connecting import ConnectingScreen

        self.push_screen(ConnectingScreen())

    def clear_session(self) -> None:
        """登出时清空会话状态。"""
        self.session = None
