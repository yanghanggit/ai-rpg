"""时装工坊 Screen：从储物箱材料制作时装。"""

from typing import Dict, List, Literal, Set

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from .base import BaseGameScreen
from .combat_data_access import get_storage_component
from .server_client import (
    TaskFailedError,
    home_craft_costume_item,
    watch_task_until_done,
)
from .utils import display_name
from ..models import CostumeItem, MaterialItem

CRAFT_COSTUME_HEADER = """\
[bold cyan]── 时装工坊 ──────────────────────────────────────[/]

在时装工坊中将储物箱内的材料制作成时装。[bold]Escape[/] 返回。
  • 输入材料编号逐一添加，输入 [bold green]0[/] 提交制作，输入 [bold red]r[/] 清空已选。
"""


class CraftCostumeItemScreen(BaseGameScreen):
    """时装工坊 Screen：多选材料后提交制作时装。"""

    CSS = """
    CraftCostumeItemScreen {
        align: center middle;
    }

    #craft-costume-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #craft-costume-input-row {
        height: 3;
        dock: bottom;
    }

    #craft-costume-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #craft-costume-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._material_list: List[Dict[str, object]] = []
        self._selected: List[str] = []
        self._step: Literal["selecting", "confirming"] = "selecting"
        self._known_costume_names: Set[str] = set()

    def compose(self) -> ComposeResult:
        yield RichLog(id="craft-costume-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="craft-costume-input-row"):
            yield Static("> ", id="craft-costume-prompt")
            yield Input(placeholder="输入编号...", id="craft-costume-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(CRAFT_COSTUME_HEADER)
        self._load_data()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Input.Submitted, "#craft-costume-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if not raw:
            return

        if self._step == "confirming":
            self._handle_confirming(raw)
            return

        if raw.lower() == "r":
            self._selected.clear()
            log.write("[dim]已清空已选材料列表。[/]")
            self._show_material_list()
            return

        if not raw.isdigit():
            log.write("[red]请输入有效编号（数字），或输入 r 清空已选。[/]")
            return

        self._handle_selecting(int(raw))

    def _handle_selecting(self, idx: int) -> None:
        log = self.query_one(RichLog)

        if not self._material_list and idx != 0:
            log.write("[yellow]材料列表尚未加载，请稍候...[/]")
            return

        if idx == 0:
            if not self._selected:
                log.write("[red]尚未选择任何材料，无法提交制作。[/]")
                return
            self._step = "confirming"
            self._show_confirm_prompt()
            return

        max_idx = len(self._material_list)
        if idx < 1 or idx > max_idx:
            log.write(f"[red]编号超出范围，请输入 1 ~ {max_idx}（0 提交）。[/]")
            return

        mat = self._material_list[idx - 1]
        name = str(mat["name"])
        self._selected.append(name)
        log.write(
            f"[dim]✓ 已加入：[bold magenta]{display_name(name)}[/]（当前已选 {len(self._selected)} 个）[/]"
        )
        self._show_selection_summary()

    def _handle_confirming(self, raw: str) -> None:
        log = self.query_one(RichLog)

        if raw == "1":
            self._do_craft()
        elif raw == "0":
            self._step = "selecting"
            self._selected.clear()
            log.write("[dim]已取消，重新选择材料。[/]")
            self._show_material_list()
        else:
            log.write("[red]请输入 1 确认制作 / 0 取消。[/]")

    def _show_material_list(self) -> None:
        log = self.query_one(RichLog)
        log.write("[bold yellow]── 储物箱可用材料 ─────────────────────────────────[/]")
        if self._material_list:
            for i, mat in enumerate(self._material_list, 1):
                name = str(mat["name"])
                count = mat.get("count", 1)
                log.write(
                    f"  [bold green]{i}.[/] [magenta]{display_name(name)}[/] "
                    f"[dim]×{count}[/]"
                )
        else:
            log.write("  [dim]（储物箱中暂无材料）[/]")
        log.write("")
        log.write(
            "[dim]输入编号添加材料（可重复选取同一材料），输入 0 提交制作，输入 r 清空已选：[/]"
        )

    def _show_selection_summary(self) -> None:
        log = self.query_one(RichLog)
        if not self._selected:
            return
        from collections import Counter

        counts = Counter(self._selected)
        parts = [f"[magenta]{display_name(n)}[/] ×{c}" for n, c in counts.items()]
        log.write(f"[dim]  当前已选：{', '.join(parts)}[/]")

    def _show_confirm_prompt(self) -> None:
        log = self.query_one(RichLog)
        from collections import Counter

        counts = Counter(self._selected)
        parts = [f"[bold magenta]{display_name(n)}[/] ×{c}" for n, c in counts.items()]
        log.write("[bold yellow]── 确认制作 ───────────────────────────────────────[/]")
        log.write(f"  使用材料：{', '.join(parts)}")
        log.write("")
        log.write("[dim]输入 [bold green]1[/] 确认制作 / [bold red]0[/] 取消：[/]")

    @work
    async def _load_data(self) -> None:
        """加载储物箱内的材料列表。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在加载储物箱材料...[/]")

        app = self.game_client
        if app.session is None:
            log.write("[red]⚠ 无法取得会话信息。[/]")
            return

        try:
            storage_component = await get_storage_component(app)
            materials: List[Dict[str, object]] = []
            known: Set[str] = set()
            for item in storage_component.items:
                if isinstance(item, MaterialItem):
                    materials.append({"name": item.name, "count": item.count})
                elif isinstance(item, CostumeItem):
                    known.add(item.name)
            self._material_list = materials
            self._known_costume_names = known
        except Exception as e:
            logger.warning(f"CraftCostumeItemScreen._load_data: 加载材料失败 error={e}")
            log.write(f"[yellow]⚠ 加载材料列表失败: {e}[/]")
            return

        logger.info(
            f"CraftCostumeItemScreen._load_data: materials={self._material_list}"
        )
        self._show_material_list()

    @work
    async def _do_craft(self) -> None:
        """提交制作请求并等待任务完成。"""
        app = self.game_client
        if app.session is None:
            return

        user_name = app.session.user_name
        game_name = app.session.game_name
        materials = list(self._selected)

        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        from collections import Counter

        counts = Counter(materials)
        parts = [f"{display_name(n)} ×{c}" for n, c in counts.items()]
        log.write("[bold yellow]── 时装工坊 ───────────────────────────────────────[/]")
        log.write(f"[dim]▶ 制作中（材料：{', '.join(parts)}）...[/]")
        logger.info(
            f"CraftCostumeItemScreen._do_craft: user={user_name} materials={materials}"
        )

        try:
            resp = await home_craft_costume_item(user_name, game_name, materials)
            task_id = resp.task_id
            log.write(f"[dim]任务已创建：{task_id}[/]")
        except Exception as e:
            logger.error(f"CraftCostumeItemScreen._do_craft: 请求失败 error={e}")
            log.write(f"[bold red]❌ 请求失败: {e}[/]")
            inp.disabled = False
            inp.focus()
            return

        try:
            await watch_task_until_done(task_id)
            log.write("[bold green]✅ 制作完成[/]")
            logger.info(f"CraftCostumeItemScreen._do_craft: 任务完成 task_id={task_id}")
            await self._show_craft_result(log)
        except TaskFailedError as e:
            log.write(f"[bold red]❌ 制作失败: {e}[/]")
            logger.error(
                f"CraftCostumeItemScreen._do_craft: 任务失败 task_id={task_id} error={e}"
            )
        except TimeoutError:
            log.write("[bold yellow]⚠️ 制作超时，请检查服务器状态[/]")
            logger.warning(
                f"CraftCostumeItemScreen._do_craft: 任务轮询超时 task_id={task_id}"
            )

        inp.disabled = False
        inp.focus()

    async def _show_craft_result(self, log: RichLog) -> None:
        """重新加载储物箱，展示本次新制作的时装详情。"""
        try:
            storage_component = await get_storage_component(self.game_client)
        except Exception as e:
            logger.warning(
                f"CraftCostumeItemScreen._show_craft_result: 获取储物箱失败 error={e}"
            )
            log.write("[dim]（无法获取制作结果详情，请手动查看储物箱）[/]")
            return

        shown = False
        for item in storage_component.items:
            if not isinstance(item, CostumeItem):
                continue
            name = item.name
            if name in self._known_costume_names:
                continue
            if not shown:
                log.write(
                    "[bold yellow]── 制作结果 ──────────────────────────────────────────────[/]"
                )
                shown = True
            log.write(f"  [bold magenta]时装[/]：{display_name(name)}")
            if item.description:
                log.write(f"  [dim]{item.description}[/]")
            log.write("  [dim]（时装不改变战斗属性，可通过「穿戴时装」功能穿上）[/]")
            log.write("")

        if not shown:
            log.write("[dim]（已入库储物箱，请查看时装列表）[/]")
