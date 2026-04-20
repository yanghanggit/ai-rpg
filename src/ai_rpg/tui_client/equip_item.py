"""装备管理 Screen（EQUIP_ITEM 玩家动作）"""

import asyncio
from typing import Dict, List, Literal, Optional

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Input, RichLog, Static

from .server_client import (
    fetch_entities_details,
    fetch_tasks_status,
    home_player_action as server_home_player_action,
)
from .utils import display_name
from ..models import EquipmentComponent, InventoryComponent
from ..models.api import HomePlayerActionType
from ..models.task import TaskStatus

EQUIP_ITEM_HEADER = """\
[bold cyan]── 装备管理 ──────────────────────────────────────[/]

选择要操作的槽位，[bold]Escape[/] 取消返回。
"""

_SLOT_LABELS = {
    "weapon": "武器",
    "armor": "套装",
    "accessory": "饰品",
}

_SLOT_KEYS = ["weapon", "armor", "accessory"]


class EquipItemScreen(Screen[None]):
    """装备管理 Screen：展示当前装备与背包物品，选槽位后更换或卸下装备。"""

    CSS = """
    EquipItemScreen {
        align: center middle;
    }

    #equip-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #equip-input-row {
        height: 3;
        dock: bottom;
    }

    #equip-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #equip-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Cancel"),
    ]

    def __init__(self) -> None:
        super().__init__()
        # 当前状态：选槽位 or 选物品
        self._state: Literal["select_slot", "select_item"] = "select_slot"
        # 当前选中的槽位 key（"weapon" / "armor" / "accessory"）
        self._selected_slot: str = ""
        # 当前槽位可选的物品名列表（不含"脱掉"选项）
        self._item_list: List[str] = []
        # 玩家当前装备状态 {slot: item_name_or_empty}
        self._equip_data: Dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield RichLog(id="equip-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="equip-input-row"):
            yield Static("> ", id="equip-prompt")
            yield Input(placeholder="输入编号选择槽位...", id="equip-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(EQUIP_ITEM_HEADER)
        self._load_equip_status()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        if self._state == "select_item":
            # 返回到选槽位状态
            self._state = "select_slot"
            log = self.query_one(RichLog)
            log.write("[dim]已返回槽位选择。[/]")
            self._render_slot_menu(log)
            inp = self.query_one(Input)
            inp.placeholder = "输入编号选择槽位..."
        else:
            self.app.pop_screen()

    @on(Input.Submitted, "#equip-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if not raw:
            return

        if self._state == "select_slot":
            self._handle_select_slot(raw, log)
        else:
            self._handle_select_item(raw, log)

    # ──────────────────────────────────────────────────
    # 内部：选槽阶段
    # ──────────────────────────────────────────────────

    def _handle_select_slot(self, raw: str, log: RichLog) -> None:
        if not raw.isdigit():
            log.write("[red]请输入有效的编号。[/]")
            return

        idx = int(raw) - 1
        if idx < 0 or idx >= len(_SLOT_KEYS):
            log.write(f"[red]编号超出范围，请输入 1 ~ {len(_SLOT_KEYS)}。[/]")
            return

        slot_key = _SLOT_KEYS[idx]
        self._selected_slot = slot_key
        self._enter_select_item(slot_key, log)

    def _enter_select_item(self, slot_key: str, log: RichLog) -> None:
        """切换到选物品状态，展示该槽位的可用背包物品。"""
        slot_label = _SLOT_LABELS[slot_key]
        current = self._equip_data.get(slot_key, "")
        current_display = display_name(current) if current else "[dim]（未装备）[/]"

        if not self._item_list_for_slot(slot_key):
            log.write(f"[yellow]槽位「{slot_label}」背包中没有可用物品。[/]")
            return

        self._state = "select_item"
        self._item_list = self._item_list_for_slot(slot_key)

        log.write(
            f"[bold yellow]槽位：[bold cyan]{slot_label}[/][bold yellow]  "
            f"当前：{current_display}[/]"
        )
        log.write("[bold yellow]可选物品：[/]")
        for i, item_name in enumerate(self._item_list, 1):
            marker = " [bold green]◀ 当前[/]" if item_name == current else ""
            log.write(f"  [bold green]{i}.[/] {display_name(item_name)}{marker}")
        if current:
            log.write(f"  [bold red]0.[/] 脱掉当前装备（{display_name(current)}）")
        log.write("")
        log.write("[dim]输入编号装备，0 脱掉，Escape 返回选槽：[/]")

        inp = self.query_one(Input)
        inp.placeholder = "输入编号选择物品..."

    def _item_list_for_slot(self, slot_key: str) -> List[str]:
        """返回该槽位在背包中可用的物品名列表。"""
        return self._available_items.get(slot_key, [])

    # ──────────────────────────────────────────────────
    # 内部：选物品阶段
    # ──────────────────────────────────────────────────

    def _handle_select_item(self, raw: str, log: RichLog) -> None:
        current = self._equip_data.get(self._selected_slot, "")

        if raw == "0":
            if not current:
                log.write("[yellow]当前槽位没有装备可以脱掉。[/]")
                return
            # 脱掉：传空字符串
            self._do_equip(self._selected_slot, "")
            return

        if not raw.isdigit():
            log.write("[red]请输入有效的编号。[/]")
            return

        idx = int(raw) - 1
        if idx < 0 or idx >= len(self._item_list):
            log.write(f"[red]编号超出范围，请输入 0 ~ {len(self._item_list)}。[/]")
            return

        target_item = self._item_list[idx]
        self._do_equip(self._selected_slot, target_item)

    # ──────────────────────────────────────────────────
    # 数据加载
    # ──────────────────────────────────────────────────

    @work
    async def _load_equip_status(self) -> None:
        """加载玩家装备与背包状态。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在加载装备信息...[/]")
        logger.info("EquipItemScreen._load_equip_status")

        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        if app.session is None:
            return
        user_name = app.session.user_name
        game_name = app.session.game_name
        bp = app.session.blueprint
        player_actor = bp.player_actor

        if not player_actor:
            log.write("[yellow]无法获取玩家角色信息。[/]")
            return

        try:
            resp = await fetch_entities_details(user_name, game_name, [player_actor])
            if not resp.entities_serialization:
                log.write(f"[yellow]未找到玩家角色实体：{player_actor}[/]")
                return

            entity = resp.entities_serialization[0]

            # 解析 EquipmentComponent
            equip_data: Dict[str, str] = {}
            for comp in entity.components:
                if comp.name == EquipmentComponent.__name__:
                    equip_data = {
                        "weapon": comp.data.get("weapon", ""),
                        "armor": comp.data.get("armor", ""),
                        "accessory": comp.data.get("accessory", ""),
                    }
                    break
            self._equip_data = equip_data

            # 解析 InventoryComponent，按槽位分组
            available: Dict[str, List[str]] = {
                "weapon": [],
                "armor": [],
                "accessory": [],
            }
            for comp in entity.components:
                if comp.name == InventoryComponent.__name__:
                    for item in comp.data.get("items", []):
                        item_type = item.get("type", "")
                        equipment_type = item.get("equipment_type", "")
                        name = item.get("name", "")
                        if not name:
                            continue
                        if item_type == "WeaponItem":
                            available["weapon"].append(name)
                        elif item_type == "EquipmentItem" and equipment_type == "Armor":
                            available["armor"].append(name)
                        elif (
                            item_type == "EquipmentItem"
                            and equipment_type == "Accessory"
                        ):
                            available["accessory"].append(name)
                    break
            self._available_items = available

            self._render_slot_menu(log)
            logger.info(
                f"EquipItemScreen._load_equip_status: 加载完成 equip={equip_data}"
            )
        except Exception as e:
            logger.error(f"EquipItemScreen._load_equip_status: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载装备信息失败: {e}[/]")

    def _render_slot_menu(self, log: RichLog) -> None:
        """渲染槽位选择菜单。"""
        log.write("[bold yellow]当前装备状态：[/]")
        for i, slot_key in enumerate(_SLOT_KEYS, 1):
            label = _SLOT_LABELS[slot_key]
            current = self._equip_data.get(slot_key, "")
            current_display = display_name(current) if current else "[dim]（未装备）[/]"
            avail_count = len(self._available_items.get(slot_key, []))
            avail_hint = (
                f"[dim]背包: {avail_count} 件可用[/]"
                if avail_count
                else "[dim]背包: 无可用物品[/]"
            )
            log.write(
                f"  [bold green]{i}.[/] [cyan]{label}[/]  {current_display}  {avail_hint}"
            )
        log.write("")
        log.write("[dim]输入编号选择槽位：[/]")

    # ──────────────────────────────────────────────────
    # 发送装备动作
    # ──────────────────────────────────────────────────

    @work
    async def _do_equip(self, slot_key: str, item_name: Optional[str]) -> None:
        """发送装备动作，等待 pipeline 完成后返回 HomeScreen。"""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        slot_label = _SLOT_LABELS[slot_key]
        if item_name:
            action_desc = f"装备「{display_name(item_name)}」到 {slot_label} 槽"
        else:
            action_desc = f"卸下 {slot_label} 槽装备"

        log.write(f"[dim]▶ 正在执行：{action_desc}...[/]")
        logger.info(f"EquipItemScreen._do_equip: slot={slot_key} item={item_name!r}")

        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        if app.session is None:
            inp.disabled = False
            inp.focus()
            return
        user_name = app.session.user_name
        game_name = app.session.game_name

        # arguments 只传被操作的槽，其余槽不传（server 端 .get() 返回 None = 保持不变）
        arguments: Dict[str, str] = {
            slot_key: item_name if item_name is not None else ""
        }

        task_id: str = ""
        success = False
        try:
            resp = await server_home_player_action(
                user_name,
                game_name,
                HomePlayerActionType.EQUIP_ITEM,
                arguments,
            )
            task_id = resp.task_id
            log.write(f"[dim]任务已创建：{task_id}[/]")
            logger.info(f"EquipItemScreen._do_equip: 任务已创建 task_id={task_id}")
        except Exception as e:
            logger.error(f"EquipItemScreen._do_equip: 发送失败 error={e}")
            log.write(f"[bold red]❌ 装备请求失败: {e}[/]")
            inp.disabled = False
            inp.focus()
            return

        # 轮询任务状态（最多 120 秒）
        _POLL_INTERVAL = 1.0
        _MAX_POLLS = 120
        for _ in range(_MAX_POLLS):
            await asyncio.sleep(_POLL_INTERVAL)
            try:
                status_resp = await fetch_tasks_status([task_id])
                if not status_resp.tasks:
                    continue
                task_record = status_resp.tasks[0]
                if task_record.status == TaskStatus.COMPLETED:
                    log.write(
                        f"[bold green]✅ {action_desc} 完成，正在返回主场景...[/]"
                    )
                    logger.info(
                        f"EquipItemScreen._do_equip: 任务完成 task_id={task_id}"
                    )
                    success = True
                    break
                elif task_record.status == TaskStatus.FAILED:
                    error_msg = task_record.error or "未知错误"
                    log.write(f"[bold red]❌ 装备操作失败: {error_msg}[/]")
                    logger.error(
                        f"EquipItemScreen._do_equip: 任务失败 task_id={task_id} error={error_msg}"
                    )
                    break
            except Exception as e:
                logger.warning(f"EquipItemScreen._do_equip: 轮询失败 error={e}")
        else:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(f"EquipItemScreen._do_equip: 轮询超时 task_id={task_id}")

        if success:
            await asyncio.sleep(0.5)
            self.app.pop_screen()
        else:
            inp.disabled = False
            inp.focus()
