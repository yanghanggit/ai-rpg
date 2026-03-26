"""AI RPG 游戏客户端主应用（Textual TUI）"""

from textual.app import App, ComposeResult


class GameClient(App[None]):
    """游戏客户端主应用。启动后推入 ConnectingScreen，由各 Screen 承载具体 UI。"""

    BINDINGS = [
        ("ctrl+c", "quit", "退出"),
    ]

    def compose(self) -> ComposeResult:
        # 保留 App 默认空 Screen 作为栈底，防止 switch_screen 时栈清空
        yield from []

    def on_mount(self) -> None:
        from .screens.connecting import ConnectingScreen

        self.push_screen(ConnectingScreen())
