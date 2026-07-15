"""查阅指定实体信息 Screen（CombatEntityInspectScreen）

INITIALIZATION 阶段命令 4）的详情页：在当前战斗涉及的实体（场景 / 角色）中选择编号，
查看该实体全部组件的原始序列化数据。
"""

import json
from typing import List, Tuple, final

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from .base import BaseGameScreen
from .combat_data_access import get_entities_details
from .utils import display_name

HEADER = """\
[bold cyan]── 查阅指定实体信息 ──────────────────────────────────────[/]

输入编号查看实体组件详情，[bold]Escape[/] 返回。
"""


@final
class CombatEntityInspectScreen(BaseGameScreen):
    """在当前战斗涉及的实体（场景 / 角色）范围内按编号查看组件详情。"""

    CSS = """
    CombatEntityInspectScreen {
        align: center middle;
    }

    #combat-inspect-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #combat-inspect-input-row {
        height: 3;
        dock: bottom;
    }

    #combat-inspect-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #combat-inspect-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    def __init__(self, candidates: List[Tuple[str, str]]) -> None:
        """candidates: [(entity_name, label)]，label 为「场景」或「角色」。"""
        super().__init__()
        self._candidates = candidates

    def compose(self) -> ComposeResult:
        yield RichLog(id="combat-inspect-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="combat-inspect-input-row"):
            yield Static("> ", id="combat-inspect-prompt")
            yield Input(placeholder="输入编号查看详情...", id="combat-inspect-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(HEADER)
        self._render_list(log)
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def _render_list(self, log: RichLog) -> None:
        log.write("  [bold]0.[/] 清屏（清除已查询的实体详情，保留本指令列表）")
        if not self._candidates:
            log.write("[yellow]当前战斗暂无可查询实体。[/]")
            return
        for i, (name, label) in enumerate(self._candidates, start=1):
            log.write(f"  [bold]{i}.[/] [{label}] {display_name(name)}")
        log.write("")

    ########################################################################################################################
    @on(Input.Submitted, "#combat-inspect-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if not raw:
            return

        if raw == "0":
            log.clear()
            log.write(HEADER)
            self._render_list(log)
            return

        if not raw.isdigit():
            log.write("[red]请输入有效编号（数字）[/]")
            return

        idx = int(raw) - 1
        if idx < 0 or idx >= len(self._candidates):
            log.write(
                f"[red]编号超出范围，请输入 1–{len(self._candidates)} 之间的数字[/]"
            )
            return

        entity_name, label = self._candidates[idx]
        log.write(f"[dim]> 查看 {label}：{entity_name}[/]")
        self._show_entity(entity_name)

    ########################################################################################################################
    @work
    async def _show_entity(self, entity_name: str) -> None:
        log = self.query_one(RichLog)
        logger.info(
            f"CombatEntityInspectScreen._show_entity: entity_name={entity_name}"
        )
        try:
            resp = await get_entities_details(self.game_client, [entity_name])
            if not resp.entities_serialization:
                log.write(f"[yellow]未找到实体：{entity_name}[/]")
                return
            for entity in resp.entities_serialization:
                log.write(f"[bold yellow]── 实体：{display_name(entity.name)} ──[/]")
                for comp in entity.components:
                    data_str = json.dumps(comp.data, ensure_ascii=False, indent=2)
                    log.write(f"  [bold cyan][组件][/] [green]{comp.name}[/]")
                    log.write(f"[dim]{data_str}[/]")
                log.write("")
        except Exception as e:
            logger.error(
                f"CombatEntityInspectScreen._show_entity: 查询失败 entity_name={entity_name} error={e}"
            )
            log.write(f"[bold red]❌ 查询失败: {e}[/]")
