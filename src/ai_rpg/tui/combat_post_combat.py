"""战斗结束处理 Screen（CombatPostCombatScreen）

CombatState.COMPLETE / POST_COMBAT 阶段的专属页面：战斗结算与后续处理
（战利品收取、退出地下城等）。目前仅为占位页面，由 CombatOngoingScreen 在检测到
战斗进入 COMPLETE / POST_COMBAT 阶段后，通过指令 5 跳转至此。
"""

from typing import final

from textual.app import ComposeResult
from textual.widgets import RichLog

from .base import BaseGameScreen

HEADER = """\
[bold cyan]── 结束战斗 ──────────────────────────────────────[/]

[dim]页面开发中：战斗结算（胜负结果 / 战利品收取 / 退出地下城等）将在此页面实现。[/]

[dim]Escape 返回。[/]
"""


@final
class CombatPostCombatScreen(BaseGameScreen):
    """战斗 COMPLETE / POST_COMBAT 阶段占位页面。"""

    CSS = """
    CombatPostCombatScreen {
        align: center middle;
    }

    #combat-post-combat-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    def compose(self) -> ComposeResult:
        yield RichLog(
            id="combat-post-combat-log", highlight=True, markup=True, wrap=True
        )

    def on_mount(self) -> None:
        self.query_one(RichLog).write(HEADER)

    def action_go_back(self) -> None:
        self.app.pop_screen()
