"""开始战斗 Screen（CombatStartActionScreen）

INITIALIZATION 阶段命令 1）的详情页：确认后触发战斗初始化。
Mock 模式（session is None）下仅做界面演示，不调用真实接口。
"""

from typing import final

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from .base import BaseGameScreen
from .combat_data_access import is_mock_mode, resolve_identity
from .server_client import TaskFailedError, dungeon_combat_init, watch_task_until_done

HEADER = """\
[bold cyan]── 开始战斗 ──────────────────────────────────────[/]

即将触发战斗初始化（DungeonCombatInitAction）。
输入 [bold]y[/] 确认开始，[bold]Escape[/] 返回。
"""


@final
class CombatStartActionScreen(BaseGameScreen):
    """开始战斗确认页：确认后调用 dungeon_combat_init 并等待任务完成。"""

    CSS = """
    CombatStartActionScreen {
        align: center middle;
    }

    #combat-start-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #combat-start-input-row {
        height: 3;
        dock: bottom;
    }

    #combat-start-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #combat-start-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    def compose(self) -> ComposeResult:
        yield RichLog(id="combat-start-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="combat-start-input-row"):
            yield Static("> ", id="combat-start-prompt")
            yield Input(placeholder="输入 y 确认开始战斗...", id="combat-start-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(HEADER)
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    ########################################################################################################################
    @on(Input.Submitted, "#combat-start-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip().lower()
        event.input.clear()
        log = self.query_one(RichLog)

        if raw != "y":
            log.write("[yellow]未确认，输入 y 以开始战斗，或 Escape 返回。[/]")
            return

        self._start_combat()

    ########################################################################################################################
    @work
    async def _start_combat(self) -> None:
        log = self.query_one(RichLog)
        logger.info("CombatStartActionScreen._start_combat: 触发战斗初始化")

        if is_mock_mode(self.game_client):
            log.write(
                "[bold yellow]\\[mock][/] 已模拟触发战斗初始化（未调用真实接口）。"
            )
            return

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)
            resp = await dungeon_combat_init(user_name, game_name)
            log.write(f"[dim]任务已提交：{resp.task_id}，等待完成...[/]")
            record = await watch_task_until_done(resp.task_id)
            log.write(f"[bold green]✅ 战斗初始化完成：{record.status}[/]")
        except TaskFailedError as e:
            logger.error(f"CombatStartActionScreen._start_combat: 任务失败 error={e}")
            log.write(f"[bold red]❌ 战斗初始化失败：{e}[/]")
        except Exception as e:
            logger.error(f"CombatStartActionScreen._start_combat: 请求失败 error={e}")
            log.write(f"[bold red]❌ 请求失败：{e}[/]")
