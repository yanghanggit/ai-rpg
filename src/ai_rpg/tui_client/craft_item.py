"""物品制造 Screen（CRAFT_ITEM 玩家动作）"""

import asyncio
from typing import List, Literal

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Input, RichLog, Static

from .server_client import (
    fetch_entities_details,
    fetch_tasks_status,
    home_craft_item as server_home_craft_item,
)
from .utils import display_name
from ..models import InventoryComponent, ItemType
from ..models.task import TaskStatus

CRAFT_ITEM_HEADER = """\
[bold cyan]── 物品制造 ──────────────────────────────────────[/]

从背包中选择材料，[bold]Escape[/] 取消返回。
"""

_POLL_INTERVAL = 1.0
_MAX_POLLS = 120


class CraftItemScreen(Screen[None]):
    """物品制造 Screen：列出背包中的 MaterialItem，玩家选择后确认提交 LLM 制造。

    状态机：
      select   — 列出材料，输入编号追加到已选列表，输入 0 进入确认阶段
      confirm  — 显示已选材料，输入 y 确认 / n 重选
    """

    CSS = """
    CraftItemScreen {
        align: center middle;
    }

    #craft-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #craft-input-row {
        height: 3;
        dock: bottom;
    }

    #craft-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #craft-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Cancel"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._state: Literal["select", "confirm"] = "select"
        self._material_list: List[str] = []  # 背包中可选材料名称（含重复）
        self._selected: List[str] = []  # 已选材料名称列表（按选择顺序）

    def compose(self) -> ComposeResult:
        yield RichLog(id="craft-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="craft-input-row"):
            yield Static("> ", id="craft-prompt")
            yield Input(placeholder="输入编号选择材料...", id="craft-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(CRAFT_ITEM_HEADER)
        self._load_materials()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        if self._state == "confirm":
            self._state = "select"
            self._selected.clear()
            self._render_material_menu()
        else:
            self.app.pop_screen()

    @on(Input.Submitted, "#craft-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if not raw:
            return

        if self._state == "select":
            self._handle_select(raw, log)
        else:
            self._handle_confirm(raw, log)

    # ------------------------------------------------------------------
    # select 阶段
    # ------------------------------------------------------------------

    def _handle_select(self, raw: str, log: RichLog) -> None:
        # 输入 0 → 进入确认阶段
        if raw == "0":
            if not self._selected:
                log.write("[yellow]请至少选择一种材料再确认。[/]")
                return
            self._state = "confirm"
            self._render_confirm_menu(log)
            return

        if not raw.isdigit():
            log.write("[red]请输入有效的编号，或输入 0 确认当前选择。[/]")
            return

        idx = int(raw) - 1
        if idx < 0 or idx >= len(self._material_list):
            log.write(f"[red]编号超出范围，请输入 1 ~ {len(self._material_list)}。[/]")
            return

        chosen = self._material_list[idx]
        self._selected.append(chosen)
        log.write(
            f"[bold green]✔ 已添加：[bold cyan]{display_name(chosen)}[/]"
            f"  [dim]（已选 {len(self._selected)} 种，输入 0 确认）[/]"
        )

    def _render_material_menu(self) -> None:
        log = self.query_one(RichLog)
        log.write(CRAFT_ITEM_HEADER)
        if not self._material_list:
            log.write("[yellow]背包中没有可用的材料。[/]")
            return
        log.write("[bold yellow]可用材料（可重复选取）：[/]")
        for i, name in enumerate(self._material_list, 1):
            log.write(f"  [bold green]{i}.[/] {display_name(name)}")
        log.write("")
        log.write("[dim]输入编号追加材料，输入 [bold]0[/] 进入确认。[/]")
        inp = self.query_one(Input)
        inp.placeholder = "输入编号选择材料..."

    # ------------------------------------------------------------------
    # confirm 阶段
    # ------------------------------------------------------------------

    def _render_confirm_menu(self, log: RichLog) -> None:
        log.write("")
        log.write("[bold yellow]── 确认制造 ────────────────────────[/]")
        log.write("[bold]已选材料：[/]")
        for name in self._selected:
            log.write(f"  [bold cyan]· {display_name(name)}[/]")
        log.write("")
        log.write("[dim]输入 [bold green]y[/] 确认制造 / [bold red]n[/] 重新选择[/]")
        inp = self.query_one(Input)
        inp.placeholder = "y 确认 / n 重新选择..."

    def _handle_confirm(self, raw: str, log: RichLog) -> None:
        if raw.lower() == "n":
            self._state = "select"
            self._selected.clear()
            self._render_material_menu()
        elif raw.lower() == "y":
            self._do_craft(list(self._selected))
        else:
            log.write("[red]请输入 y 确认或 n 重新选择。[/]")

    # ------------------------------------------------------------------
    # 异步 workers
    # ------------------------------------------------------------------

    @work
    async def _load_materials(self) -> None:
        """从服务器加载玩家背包，提取 MaterialItem 列表。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在加载背包材料...[/]")

        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        if app.session is None:
            return
        user_name = app.session.user_name
        game_name = app.session.game_name
        player_actor = app.session.blueprint.player_actor

        try:
            resp = await fetch_entities_details(user_name, game_name, [player_actor])
            entity = resp.entities_serialization[0]

            materials: List[str] = []
            for comp in entity.components:
                if comp.name == InventoryComponent.__name__:
                    inv_comp = InventoryComponent(**comp.data)
                    for item in inv_comp.items:
                        if item.type == ItemType.MATERIAL_ITEM and item.count > 0:
                            # 按 count 展开：count=2 → 列出两次，让玩家能选两次
                            for _ in range(item.count):
                                materials.append(item.name)
                    break

            materials = [m for m in materials if m]
            self._material_list = materials

            if not materials:
                log.write("[yellow]背包中没有可用的材料。[/]")
                return

            log.write("[bold yellow]可用材料（可重复选取）：[/]")
            for i, name in enumerate(materials, 1):
                log.write(f"  [bold green]{i}.[/] {display_name(name)}")
            log.write("")
            log.write("[dim]输入编号追加材料，输入 [bold]0[/] 进入确认。[/]")
        except Exception as e:
            logger.error(f"CraftItemScreen._load_materials: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载材料列表失败: {e}[/]")

    @work
    async def _do_craft(self, materials: List[str]) -> None:
        """提交制造请求并轮询任务状态，完成后返回主场景。"""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        if app.session is None:
            inp.disabled = False
            inp.focus()
            return
        user_name = app.session.user_name
        game_name = app.session.game_name

        material_display = "、".join(display_name(m) for m in materials)
        log.write(f"[dim]▶ 正在提交制造请求：{material_display}...[/]")
        logger.info(
            f"CraftItemScreen._do_craft: user={user_name} materials={materials}"
        )

        try:
            resp = await server_home_craft_item(user_name, game_name, materials)
            task_id = resp.task_id
            log.write(f"[dim]任务已创建：{task_id}[/]")
        except Exception as e:
            logger.error(f"CraftItemScreen._do_craft: 请求失败 error={e}")
            log.write(f"[bold red]❌ 制造请求失败: {e}[/]")
            inp.disabled = False
            inp.focus()
            return

        # 轮询任务状态
        for _ in range(_MAX_POLLS):
            await asyncio.sleep(_POLL_INTERVAL)
            try:
                status_resp = await fetch_tasks_status([task_id])
                if not status_resp.tasks:
                    continue
                task_record = status_resp.tasks[0]
                if task_record.status == TaskStatus.COMPLETED:
                    log.write("[bold green]✅ 制造完成，正在返回主场景...[/]")
                    logger.info(f"CraftItemScreen._do_craft: 完成 task_id={task_id}")
                    await asyncio.sleep(0.5)
                    self.app.pop_screen()
                    return
                elif task_record.status == TaskStatus.FAILED:
                    error_msg = task_record.error or "未知错误"
                    log.write(f"[bold red]❌ 制造失败: {error_msg}[/]")
                    logger.error(
                        f"CraftItemScreen._do_craft: 任务失败 task_id={task_id} error={error_msg}"
                    )
                    break
            except Exception as e:
                logger.warning(f"CraftItemScreen._do_craft: 轮询失败 error={e}")
        else:
            log.write("[bold yellow]⚠️ 制造超时，请检查服务器状态[/]")
            logger.warning(f"CraftItemScreen._do_craft: 轮询超时 task_id={task_id}")

        inp.disabled = False
        inp.focus()
