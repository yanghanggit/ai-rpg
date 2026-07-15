"""历史回合详情 Screen（CombatRoundHistoryScreen）

CombatOngoingScreen 命令入口：以列表方式展示 Combat.rounds 完整历史（含最新一局），
每局展示 Round 的全部字段。
"""

from itertools import zip_longest
from typing import List, final

from textual.app import ComposeResult
from textual.widgets import RichLog

from ..models import Round
from .base import BaseGameScreen
from .utils import display_name

HEADER = """\
[bold cyan]── 历史回合详情 ──────────────────────────────────────[/]

[dim]按出手顺序列出所有回合（最新回合在最后）。Escape 返回。[/]
"""


def _render_round(log: RichLog, index: int, round_: Round, is_latest: bool) -> None:
    """渲染单局 Round 的完整数据。"""
    prefix = "[bold magenta]▶ [/]" if is_latest else "  "
    completed_mark = (
        "[green]✓ 已完成[/]" if round_.is_completed else "[yellow]进行中[/]"
    )
    draw_mark = "[green]是[/]" if round_.draw_completed else "[yellow]否[/]"

    log.write(f"{prefix}[bold cyan]第 {index} 局[/]  {completed_mark}")

    order_str = (
        "  →  ".join(round_.action_order) if round_.action_order else "[dim]（无）[/]"
    )
    completed_str = (
        "、".join(round_.completed_actors)
        if round_.completed_actors
        else "[dim]（无）[/]"
    )
    log.write(f"    行动顺序：   {order_str}")
    log.write(f"    已出手角色： {completed_str}")
    if round_.current_actor is not None:
        log.write(
            f"    当前 turn：  [bold yellow]{display_name(round_.current_actor)}[/]"
        )
    log.write(f"    抽牌已完成： {draw_mark}")
    log.write(f"    消耗品使用次数： [bold]{round_.consumable_use_count}[/]")
    log.write(f"    装备使用次数：   [bold]{round_.gear_use_count}[/]")

    if round_.cards_combat_log or round_.cards_narrative:
        log.write("    [bold]出牌记录：[/]")
        for i, (combat_log, narrative) in enumerate(
            zip_longest(round_.cards_combat_log, round_.cards_narrative), start=1
        ):
            log.write(f"      [{i}] [dim]战斗：[/] {combat_log or '[dim]（无）[/]'}")
            log.write(f"          [dim]叙事：[/] {narrative or '[dim]（无）[/]'}")

    if round_.consumable_combat_log or round_.consumable_narrative:
        log.write("    [bold]消耗品记录：[/]")
        for i, (combat_log, narrative) in enumerate(
            zip_longest(round_.consumable_combat_log, round_.consumable_narrative),
            start=1,
        ):
            log.write(f"      [{i}] [dim]战斗：[/] {combat_log or '[dim]（无）[/]'}")
            log.write(f"          [dim]叙事：[/] {narrative or '[dim]（无）[/]'}")

    if round_.gear_combat_log or round_.gear_narrative:
        log.write("    [bold]装备记录：[/]")
        for i, (combat_log, narrative) in enumerate(
            zip_longest(round_.gear_combat_log, round_.gear_narrative), start=1
        ):
            log.write(f"      [{i}] [dim]战斗：[/] {combat_log or '[dim]（无）[/]'}")
            log.write(f"          [dim]叙事：[/] {narrative or '[dim]（无）[/]'}")

    log.write("")


@final
class CombatRoundHistoryScreen(BaseGameScreen):
    """以列表形式展示 Combat.rounds 完整历史（含最新一局）。"""

    CSS = """
    CombatRoundHistoryScreen {
        align: center middle;
    }

    #combat-round-history-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    def __init__(self, rounds: List[Round]) -> None:
        super().__init__()
        self._rounds = rounds

    def compose(self) -> ComposeResult:
        yield RichLog(
            id="combat-round-history-log", highlight=True, markup=True, wrap=True
        )

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(HEADER)

        if not self._rounds:
            log.write("  [dim]（尚无回合数据）[/]")
            return

        last_index = len(self._rounds)
        for i, round_ in enumerate(self._rounds, start=1):
            _render_round(log, i, round_, is_latest=(i == last_index))

    def action_go_back(self) -> None:
        self.app.pop_screen()
