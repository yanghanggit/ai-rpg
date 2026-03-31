"""AI RPG 游戏客户端主应用（Textual TUI）"""

from typing import Optional

from textual.app import App, ComposeResult

from ..models import Blueprint


class GameClient(App[None]):
    """游戏客户端主应用。启动后推入 ConnectingScreen，由各 Screen 承载具体 UI。"""

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
    ]

    # ── 会话状态：登录后写入，登出后清空 ──
    session_user_name: Optional[str] = None
    session_game_name: Optional[str] = None
    session_blueprint: Optional[Blueprint] = None

    def compose(self) -> ComposeResult:
        # 保留 App 默认空 Screen 作为栈底，防止 switch_screen 时栈清空
        yield from []

    def on_mount(self) -> None:
        from .connecting import ConnectingScreen

        self.push_screen(ConnectingScreen())

    def clear_session(self) -> None:
        """登出时清空会话状态。"""
        self.session_user_name = None
        self.session_game_name = None
        self.session_blueprint = None
