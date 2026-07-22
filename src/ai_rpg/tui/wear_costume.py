"""穿戴时装 Screen：指令驱动。

重写说明（进行中）：本页正从「两步选择式交互」迁移为「指令驱动展示」。
当前仅接入以下指令，后续会逐步补充穿戴 / 移除时装等写操作指令：
  1 - 获取当前外观：列出全部场景下全部角色的 AppearanceComponent
      （base_body / appearance）与 EquippedCostumeComponent（如果持有）信息。
  0 - 清屏。

兼容 mock 与正式服务器数据：复用 `combat_data_access` 中已封装的
「session is None → mock 固定数据 / 否则 → 真实 fetch_* 调用」判断逻辑，
使本页可通过 `scripts/run_tui_client.py --dev-screen wear-costume` 在无服务器时
直接调试（mock 数据见 `mock_data.py`）。
"""

from typing import List, Optional

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from .base import BaseGameScreen
from .combat_data_access import get_entities_details, get_stages_state
from .utils import display_name
from ..models import (
    AppearanceComponent,
    ComponentSerialization,
    EquippedCostumeComponent,
)

WEAR_COSTUME_HEADER = """\
[bold cyan]── 穿戴时装 ──────────────────────────────────────[/]

指令驱动页面（开发中，逐步补充），[bold]Escape[/] 返回。
"""

COMMANDS_MENU = """\
[bold yellow]── 可用指令 ─────────[/]
  [bold green]0[/]  清屏
  [bold green]1[/]  获取当前外观（全部场景 · 全部角色）
"""


class WearCostumeScreen(BaseGameScreen):
    """穿戴时装 Screen：指令驱动，输入编号执行对应指令。"""

    CSS = """
    WearCostumeScreen {
        align: center middle;
    }

    #costume-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #costume-input-row {
        height: 3;
        dock: bottom;
    }

    #costume-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #costume-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def compose(self) -> ComposeResult:
        yield RichLog(id="costume-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="costume-input-row"):
            yield Static("> ", id="costume-prompt")
            yield Input(placeholder="输入指令编号...", id="costume-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(WEAR_COSTUME_HEADER)
        log.write(COMMANDS_MENU)
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    ########################################################################################################################
    @on(Input.Submitted, "#costume-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if not raw:
            return

        if raw == "0":
            log.clear()
            log.write(WEAR_COSTUME_HEADER)
            log.write(COMMANDS_MENU)
            return

        if raw == "1":
            self._cmd_show_appearances()
            return

        log.write(f"[red]未知指令：{raw}，请输入 0 或 1。[/]")

    ########################################################################################################################
    def _render_actor_appearance(
        self, log: RichLog, actor_name: str, components: List[ComponentSerialization]
    ) -> None:
        """从实体组件列表中提取并渲染 AppearanceComponent + EquippedCostumeComponent（如有）"""
        appearance_comp: Optional[AppearanceComponent] = None
        costume_comp: Optional[EquippedCostumeComponent] = None
        for comp in components:
            if comp.name == AppearanceComponent.__name__:
                appearance_comp = AppearanceComponent(**comp.data)
            elif comp.name == EquippedCostumeComponent.__name__:
                costume_comp = EquippedCostumeComponent(**comp.data)

        log.write(f"  [bold cyan]{display_name(actor_name)}[/]")

        if appearance_comp is not None:
            log.write(f"    [dim]基础体型:[/] {appearance_comp.base_body}")
            log.write(f"    [dim]当前外观:[/] {appearance_comp.appearance}")
        else:
            log.write("    [dim]（未持有 AppearanceComponent）[/]")

        if costume_comp is not None:
            item = costume_comp.item
            log.write(f"    [magenta]时装:[/] {item.name} — {item.description}")
        else:
            log.write("    [dim]（未持有 EquippedCostumeComponent，即未穿戴时装）[/]")

    ########################################################################################################################
    @work
    async def _cmd_show_appearances(self) -> None:
        """指令 1：获取全部场景 · 全部角色的当前外观（AppearanceComponent + CostumeComponent）。"""
        log = self.query_one(RichLog)
        log.write(
            "[bold yellow]── 当前外观（全部场景） ──────────────────────────────────────[/]"
        )

        try:
            stages_resp = await get_stages_state(self.game_client)
        except Exception as e:
            logger.error(
                f"WearCostumeScreen._cmd_show_appearances: 获取场景列表失败 error={e}"
            )
            log.write(f"[bold red]❌ 获取场景列表失败: {e}[/]")
            return

        if not stages_resp.mapping:
            log.write("[yellow]当前没有可查询的场景。[/]")
            return

        all_actor_names = [
            name for actors in stages_resp.mapping.values() for name in actors
        ]

        try:
            details_resp = await get_entities_details(self.game_client, all_actor_names)
        except Exception as e:
            logger.error(
                f"WearCostumeScreen._cmd_show_appearances: 获取角色详情失败 error={e}"
            )
            log.write(f"[bold red]❌ 获取角色详情失败: {e}[/]")
            return

        components_by_actor = {
            entity.name: entity.components
            for entity in details_resp.entities_serialization
        }

        for stage_name, actor_names in stages_resp.mapping.items():
            log.write(f"[bold yellow]场景：{display_name(stage_name)}[/]")
            if not actor_names:
                log.write("  [dim]（场景内暂无角色）[/]")
                continue
            for actor_name in actor_names:
                self._render_actor_appearance(
                    log, actor_name, components_by_actor.get(actor_name, [])
                )
            log.write("")
