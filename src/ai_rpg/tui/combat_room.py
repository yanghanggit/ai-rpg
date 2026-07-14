"""战斗房间 Screen（CombatRoomScreen）"""

from typing import final
from textual.app import ComposeResult
from textual.widgets import Static
from .base import BaseGameScreen


@final
class CombatRoomScreen(BaseGameScreen):
    """战斗房间 Screen：精简占位页面，仅用于开发中的布局占位。"""

    BINDINGS = [
        ("escape", "app.quit", "退出"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(
            "[bold cyan]战斗房间[/]\n\n[dim]页面重构中，敬请期待。[/]",
            id="combat-room-placeholder",
        )
