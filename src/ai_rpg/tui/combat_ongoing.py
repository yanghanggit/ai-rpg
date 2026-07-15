"""战斗进行中 Screen（CombatOngoingScreen）

CombatState.ONGOING 阶段的专属页面：战斗核心状态，逻辑复杂（出牌/抽牌/使用道具/
装备/回合推进等），单独开发。目前仅为占位页面，由 CombatRoomScreen 在战斗初始化
成功后跳转至此。
"""

from typing import final

from textual.app import ComposeResult
from textual.widgets import Static

from .base import BaseGameScreen

PLACEHOLDER = """\
[bold cyan]── 战斗进行中（ONGOING） ──────────────────────────────────────[/]

[dim]页面开发中：出牌 / 抽牌 / 使用道具与装备 / 回合推进等核心战斗交互将在此页面实现。[/]
"""


@final
class CombatOngoingScreen(BaseGameScreen):
    """战斗 ONGOING 阶段占位页面。"""

    BINDINGS = [
        ("escape", "app.quit", "退出"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(PLACEHOLDER, id="combat-ongoing-placeholder")
