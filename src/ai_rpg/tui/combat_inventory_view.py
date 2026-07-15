"""查阅我方背包 Screen（CombatInventoryViewScreen）

INITIALIZATION 阶段命令 3）的详情页：仅展示玩家自身的 InventoryComponent。
"""

from typing import final

from loguru import logger
from textual import work
from textual.app import ComposeResult
from textual.widgets import RichLog

from ..models import InventoryComponent
from .base import BaseGameScreen
from .combat_data_access import get_entities_details, resolve_identity
from .utils import display_name, render_item

HEADER = """\
[bold cyan]── 查阅我方背包 ──────────────────────────────────────[/]

[dim]Escape 返回。[/]
"""


@final
class CombatInventoryViewScreen(BaseGameScreen):
    """展示玩家角色的 InventoryComponent（仅我方，不含队友/怪物）。"""

    CSS = """
    CombatInventoryViewScreen {
        align: center middle;
    }

    #combat-inventory-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    def compose(self) -> ComposeResult:
        yield RichLog(id="combat-inventory-log", highlight=True, markup=True, wrap=True)

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(HEADER)
        self._load_inventory()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    ########################################################################################################################
    @work
    async def _load_inventory(self) -> None:
        log = self.query_one(RichLog)
        _, _, actor_name = resolve_identity(self.game_client)
        logger.info(f"CombatInventoryViewScreen._load_inventory: actor={actor_name}")
        try:
            resp = await get_entities_details(self.game_client, [actor_name])
        except Exception as e:
            logger.error(
                f"CombatInventoryViewScreen._load_inventory: 加载失败 error={e}"
            )
            log.write(f"[bold red]❌ 加载背包失败：{e}[/]")
            return

        if not resp.entities_serialization:
            log.write(f"[yellow]未找到角色：{actor_name}[/]")
            return

        entity = resp.entities_serialization[0]
        inventory_data = next(
            (
                c.data
                for c in entity.components
                if c.name == InventoryComponent.__name__
            ),
            None,
        )
        log.write(f"[bold yellow]── {display_name(entity.name)} 的背包 ──[/]")
        if inventory_data is None:
            log.write("  [dim]（无背包组件）[/]")
            return

        inventory = InventoryComponent(**inventory_data)
        if not inventory.items:
            log.write("  [dim]（背包为空）[/]")
        else:
            log.write(f"  共 [bold]{len(inventory.items)}[/] 件道具：")
            log.write("  " + "-" * 40)
            for item in inventory.items:
                log.write("  " + render_item(item))
                # 写一个分割线
                log.write("  " + "-" * 40)
