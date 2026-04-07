"""战斗回合详情 Screen"""

from itertools import zip_longest

from loguru import logger
from textual import work
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import RichLog

from .server_client import fetch_dungeon_room
from .utils import display_name

ROUND_HEADER = """\
[bold cyan]── 战斗回合详情 ──────────────────────────────────────[/]

显示当前战斗所有回合信息（最新回合在最后）。[bold]Escape[/] 返回。
"""


class RoundDetailScreen(Screen[None]):
    """战斗回合详情 Screen：显示 Combat.rounds 完整信息（只读）。"""

    CSS = """
    RoundDetailScreen {
        align: center middle;
    }

    #round-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def __init__(self, user_name: str, game_name: str) -> None:
        super().__init__()
        self._user_name = user_name
        self._game_name = game_name

    def compose(self) -> ComposeResult:
        yield RichLog(id="round-log", highlight=True, markup=True, wrap=True)
        # yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(ROUND_HEADER)
        self._fetch_rounds()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @work
    async def _fetch_rounds(self) -> None:
        """获取并渲染所有战斗回合信息。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在加载回合信息...[/]")
        logger.info(
            f"RoundDetailScreen._fetch_rounds: user={self._user_name} game={self._game_name}"
        )

        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            combat = room_resp.room.combat
            rounds = combat.rounds

            log.write(
                f"[bold yellow]战斗：{combat.name}  "
                f"状态：{combat.state.name}  "
                f"结果：{combat.result.name}  "
                f"共 {len(rounds)} 局[/]"
            )
            log.write("")

            if not rounds:
                log.write("  [dim]（尚无回合数据）[/]")
                return

            for idx, rnd in enumerate(rounds):
                is_last = idx == len(rounds) - 1
                prefix = "[bold magenta]▶ [/]" if is_last else "  "
                title = f"[bold cyan]第 {idx + 1} 局[/]"
                completed_mark = (
                    "[green]✓ 已完成[/]"
                    if rnd.is_round_completed
                    else "[yellow]进行中[/]"
                )
                log.write(f"{prefix}{title}  {completed_mark}")

                order_str = (
                    "  →  ".join(rnd.action_order)
                    if rnd.action_order
                    else "[dim]（无）[/]"
                )
                done_str = (
                    "、".join(rnd.completed_actors)
                    if rnd.completed_actors
                    else "[dim]（无）[/]"
                )
                log.write(f"    行动顺序：{order_str}")
                log.write(f"    已出手：  {done_str}")
                if rnd.current_actor is not None:
                    log.write(
                        f"    [bold]当前行动：[/] [bold yellow]{display_name(rnd.current_actor)}[/]"
                    )

                if rnd.combat_log or rnd.narrative:
                    log.write("    [bold]出手记录：[/]")
                    for i, (cl, nv) in enumerate(
                        zip_longest(rnd.combat_log, rnd.narrative, fillvalue=None),
                        start=1,
                    ):
                        log.write(
                            f"      [{i}] [dim]战斗：[/] {cl}"
                            if cl
                            else f"      [{i}] [dim]战斗：[/] [dim]（无）[/]"
                        )
                        log.write(
                            f"          [dim]叙事：[/] {nv}"
                            if nv
                            else f"          [dim]叙事：[/] [dim]（无）[/]"
                        )

                log.write("")

            logger.info(
                f"RoundDetailScreen._fetch_rounds: 加载完成 rounds={len(rounds)}"
            )
        except Exception as e:
            logger.error(f"RoundDetailScreen._fetch_rounds: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载回合信息失败: {e}[/]")
