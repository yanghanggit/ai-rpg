"""道具管理 Screen：显示背包与储物箱道具，并支持在两者之间移动。"""

from typing import Any, Dict, List, Literal, Tuple

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Input, RichLog, Static

from .server_client import (
    fetch_entities_details,
    home_item_move_to_inventory,
    home_item_move_to_storage,
)
from ..models import CostumeComponent, InventoryComponent, StorageComponent
from ..models.items import CostumeItem
from .utils import display_name, render_item

ITEM_MGMT_HEADER = """\
[bold cyan]── 道具管理 ──────────────────────────────────────[/]

[dim]背包（随身携带） vs 储物箱（备用库存）[/]
输入编号将该道具移到另一侧，[bold]Escape[/] 返回。
"""

# (location, item_dict)
_ItemEntry = Tuple[Literal["inventory", "storage", "equipped"], Dict[str, Any]]


class ItemManagementScreen(Screen[None]):
    """道具管理 Screen：列出全部道具并支持在背包与储物箱之间移动。"""

    CSS = """
    ItemManagementScreen {
        align: center middle;
    }

    #item-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #item-input-row {
        height: 3;
        dock: bottom;
    }

    #item-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #item-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._all_items: List[_ItemEntry] = []

    def compose(self) -> ComposeResult:
        yield RichLog(id="item-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="item-input-row"):
            yield Static("> ", id="item-prompt")
            yield Input(placeholder="输入编号移动道具...", id="item-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(ITEM_MGMT_HEADER)
        self._load_items()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def _render_list(self) -> None:
        log = self.query_one(RichLog)
        log.write("[bold yellow]── 道具列表 ──────────────────────────────────────[/]")

        inventory_items = [
            (i, item)
            for i, (loc, item) in enumerate(self._all_items)
            if loc == "inventory"
        ]
        storage_items = [
            (i, item)
            for i, (loc, item) in enumerate(self._all_items)
            if loc == "storage" and item.get("type") != CostumeItem.__name__
        ]
        costume_items = [
            (i, item)
            for i, (loc, item) in enumerate(self._all_items)
            if loc == "storage" and item.get("type") == CostumeItem.__name__
        ]
        equipped_items = [
            (i, item)
            for i, (loc, item) in enumerate(self._all_items)
            if loc == "equipped"
        ]

        if inventory_items:
            log.write("[bold green]  ▍随身背包[/]")
            for global_idx, item in inventory_items:
                log.write(
                    f"  [bold green]{global_idx + 1}.[/] [cyan]【背包】[/] {render_item(item)}"
                )
        else:
            log.write("[bold green]  ▍随身背包[/] [dim]（空）[/]")

        log.write("")

        if storage_items:
            log.write("[bold blue]  ▍储物箱[/]")
            for global_idx, item in storage_items:
                log.write(
                    f"  [bold blue]{global_idx + 1}.[/] [dim]【储物】[/] {render_item(item)}"
                )
        else:
            log.write("[bold blue]  ▍储物箱[/] [dim]（空）[/]")

        log.write("")

        if equipped_items:
            log.write(
                "[bold magenta]  ▍穿戴中[/] [dim]（移除时装请使用外观更新功能）[/]"
            )
            for global_idx, item in equipped_items:
                log.write(
                    f"  [bold magenta]{global_idx + 1}.[/] [magenta]【穿戴】[/] {render_item(item)}"
                )
            log.write("")

        if costume_items:
            log.write(
                "[bold magenta]  ▍时装收藏[/] [dim]（只读，无法移动，通过外观更新功能使用）[/]"
            )
            for global_idx, item in costume_items:
                log.write(
                    f"  [bold magenta]{global_idx + 1}.[/] [magenta]【时装】[/] {render_item(item)}"
                )
            log.write("")

        log.write("[dim]输入编号移动道具（背包 ↔ 储物箱）：[/]")

    @on(Input.Submitted, "#item-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if not raw:
            return

        if not self._all_items:
            log.write("[yellow]道具列表尚未加载，请稍候...[/]")
            return

        if not raw.isdigit():
            log.write("[red]请输入有效的编号。[/]")
            return

        idx = int(raw) - 1
        if idx < 0 or idx >= len(self._all_items):
            log.write(f"[red]编号超出范围，请输入 1 ~ {len(self._all_items)}。[/]")
            return

        location, item_dict = self._all_items[idx]
        item_name = item_dict.get("name", "?")

        if location == "equipped" or item_dict.get("type") == CostumeItem.__name__:
            log.write(
                f"[yellow]⚠ 时装「{item_name}」不可移动，请通过外观更新功能使用。[/]"
            )
            return

        if location == "inventory":
            self._do_move_to_storage(item_name)
        else:
            self._do_move_to_inventory(item_name)

    @work
    async def _load_items(self) -> None:
        """从服务器获取玩家实体，解析背包与储物箱道具列表。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在加载道具信息...[/]")

        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        if app.session is None:
            log.write("[red]⚠ 无法取得会话信息。[/]")
            return

        user_name = app.session.user_name
        game_name = app.session.game_name
        player_actor = app.session.blueprint.player_actor

        try:
            resp = await fetch_entities_details(user_name, game_name, [player_actor])
        except Exception as e:
            logger.error(f"ItemManagementScreen._load_items: 查询失败 error={e}")
            log.write(f"[bold red]❌ 读取道具列表失败: {e}[/]")
            return

        inventory_items: List[Dict[str, Any]] = []
        storage_items: List[Dict[str, Any]] = []
        equipped_item: Dict[str, Any] = {}

        for entity in resp.entities_serialization:
            for comp in entity.components:
                if comp.name == InventoryComponent.__name__:
                    inventory_items = comp.data.get("items", [])
                elif comp.name == StorageComponent.__name__:
                    storage_items = comp.data.get("items", [])
                elif comp.name == CostumeComponent.__name__:
                    equipped_item = comp.data.get("item", {})

        self._all_items = (
            [("inventory", item) for item in inventory_items]
            + [("storage", item) for item in storage_items]
            + ([("equipped", equipped_item)] if equipped_item else [])
        )

        logger.info(
            f"ItemManagementScreen._load_items: inventory={len(inventory_items)}"
            f" storage={len(storage_items)}"
        )
        self._render_list()

    @work
    async def _do_move_to_inventory(self, item_name: str) -> None:
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True
        log.write(f"[dim]▶ 正在将 {display_name(item_name)} 移入背包...[/]")
        logger.info(f"ItemManagementScreen._do_move_to_inventory: item={item_name}")

        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        if app.session is None:
            inp.disabled = False
            return
        try:
            await home_item_move_to_inventory(
                app.session.user_name, app.session.game_name, [item_name]
            )
            log.write(f"[bold green]✅ {display_name(item_name)} 已移入随身背包[/]")
            logger.info(
                f"ItemManagementScreen._do_move_to_inventory: 成功 item={item_name}"
            )
        except Exception as e:
            logger.error(
                f"ItemManagementScreen._do_move_to_inventory: 失败 item={item_name} error={e}"
            )
            log.write(f"[bold red]❌ 移动失败: {e}[/]")
        finally:
            inp.disabled = False
            inp.focus()
        self._load_items()

    @work
    async def _do_move_to_storage(self, item_name: str) -> None:
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True
        log.write(f"[dim]▶ 正在将 {display_name(item_name)} 移入储物箱...[/]")
        logger.info(f"ItemManagementScreen._do_move_to_storage: item={item_name}")

        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        if app.session is None:
            inp.disabled = False
            return
        try:
            await home_item_move_to_storage(
                app.session.user_name, app.session.game_name, [item_name]
            )
            log.write(f"[bold green]✅ {display_name(item_name)} 已移入储物箱[/]")
            logger.info(
                f"ItemManagementScreen._do_move_to_storage: 成功 item={item_name}"
            )
        except Exception as e:
            logger.error(
                f"ItemManagementScreen._do_move_to_storage: 失败 item={item_name} error={e}"
            )
            log.write(f"[bold red]❌ 移动失败: {e}[/]")
        finally:
            inp.disabled = False
            inp.focus()
        self._load_items()
