"""穿戴时装 Screen：指令驱动。

重写说明（进行中）：本页正从「两步选择式交互」迁移为「指令驱动展示」。
当前仅接入以下指令，后续会逐步补充穿戴 / 移除时装等写操作指令：
  1 - 获取当前外观：列出全部场景下全部角色的 AppearanceComponent
      （base_body / appearance）与 EquippedCostumeComponent（如果持有）信息。
  2 - 获取储物箱时装：列出全局储物箱内全部 CostumeItem，若已被某角色穿戴则标注穿戴者。
  0 - 清屏。

每条指令均为一次性临时 GET：不缓存任何跨指令状态，每次执行都重新从
（mock 或真实）服务端拉取最新数据。

兼容 mock 与正式服务器数据：复用 `combat_data_access` 中已封装的
「session is None → mock 固定数据 / 否则 → 真实 fetch_* 调用」判断逻辑，
使本页可通过 `scripts/run_tui_client.py --dev-screen wear-costume` 在无服务器时
直接调试（mock 数据见 `mock_data.py`）。
"""

from typing import Any, Dict, List, Optional

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from .base import BaseGameScreen
from .combat_data_access import (
    get_entities_details,
    get_stages_state,
    get_storage_entity_name,
)
from .utils import display_name
from ..models import (
    AppearanceComponent,
    ComponentSerialization,
    CostumeItem,
    EquippedCostumeComponent,
    StorageComponent,
)

WEAR_COSTUME_HEADER = """\
[bold cyan]── 穿戴时装 ──────────────────────────────────────[/]

指令驱动页面（开发中，逐步补充），[bold]Escape[/] 返回。
"""

COMMANDS_MENU = """\
[bold yellow]── 可用指令 ─────────[/]
  [bold green]0[/]  清屏
  [bold green]1[/]  获取当前外观（全部场景 · 全部角色）
  [bold green]2[/]  获取储物箱时装（标注穿戴者）
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

        if raw == "2":
            self._cmd_show_storage_costumes()
            return

        log.write(f"[red]未知指令：{raw}，请输入 0 ~ 2。[/]")

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
        """指令 1：获取全部场景 · 全部角色的当前外观（AppearanceComponent + EquippedCostumeComponent）。"""
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

    ########################################################################################################################
    async def _fetch_storage_costume_items(
        self, log: RichLog, storage_entity_name: str
    ) -> Optional[List[CostumeItem]]:
        """一次性临时 GET：拉取储物箱实体的 StorageComponent，提取其中全部 CostumeItem。

        失败或找不到 StorageComponent 时返回 None（错误信息已写入 log）；
        储物箱中没有时装时返回空列表。"""
        try:
            storage_details_resp = await get_entities_details(
                self.game_client, [storage_entity_name]
            )
        except Exception as e:
            logger.error(
                f"WearCostumeScreen._fetch_storage_costume_items: 获取储物箱失败 error={e}"
            )
            log.write(f"[bold red]❌ 获取储物箱失败: {e}[/]")
            return None

        storage_data: Optional[Dict[str, Any]] = None
        for entity in storage_details_resp.entities_serialization:
            if entity.name != storage_entity_name:
                continue
            for comp in entity.components:
                if comp.name == StorageComponent.__name__:
                    storage_data = comp.data

        if storage_data is None:
            log.write(
                f"[yellow]未找到储物箱实体或其 StorageComponent: {storage_entity_name}[/]"
            )
            return None

        storage_comp = StorageComponent(**storage_data)
        return [item for item in storage_comp.items if isinstance(item, CostumeItem)]

    ########################################################################################################################
    async def _fetch_costume_wearer_map(self, log: RichLog) -> Optional[Dict[str, str]]:
        """一次性临时 GET：重新拉取全部场景 · 全部角色的 EquippedCostumeComponent，
        构建 {时装名称: 穿戴者实体名} 映射，不复用任何其他指令已拉取的数据。

        失败时返回 None（错误信息已写入 log）。"""
        try:
            stages_resp = await get_stages_state(self.game_client)
        except Exception as e:
            logger.error(
                f"WearCostumeScreen._fetch_costume_wearer_map: 获取场景列表失败 error={e}"
            )
            log.write(f"[bold red]❌ 获取场景列表失败: {e}[/]")
            return None

        all_actor_names = [
            name for actors in stages_resp.mapping.values() for name in actors
        ]

        wearer_by_item_name: Dict[str, str] = {}
        if not all_actor_names:
            return wearer_by_item_name

        try:
            actors_details_resp = await get_entities_details(
                self.game_client, all_actor_names
            )
        except Exception as e:
            logger.error(
                f"WearCostumeScreen._fetch_costume_wearer_map: 获取角色详情失败 error={e}"
            )
            log.write(f"[bold red]❌ 获取角色详情失败: {e}[/]")
            return None

        for entity in actors_details_resp.entities_serialization:
            for comp in entity.components:
                if comp.name == EquippedCostumeComponent.__name__:
                    equipped = EquippedCostumeComponent(**comp.data)
                    wearer_by_item_name[equipped.item.name] = entity.name

        return wearer_by_item_name

    ########################################################################################################################
    @work
    async def _cmd_show_storage_costumes(self) -> None:
        """指令 2：获取全局储物箱内全部 CostumeItem，并标注其中已被某角色穿戴的项。

        一次性临时 GET：本方法不读写任何 self._xxx 缓存字段，每次执行都重新从
        （mock 或真实）服务端拉取储物箱与全部角色的最新数据。"""
        log = self.query_one(RichLog)
        log.write(
            "[bold yellow]── 储物箱时装 ───────────────────────────────────────────────[/]"
        )

        storage_entity_name = get_storage_entity_name(self.game_client)

        costume_items = await self._fetch_storage_costume_items(
            log, storage_entity_name
        )
        if costume_items is None:
            return
        if not costume_items:
            log.write("[dim]（储物箱中暂无时装）[/]")
            return

        wearer_by_item_name = await self._fetch_costume_wearer_map(log)
        if wearer_by_item_name is None:
            return

        log.write(f"[bold yellow]储物箱：{display_name(storage_entity_name)}[/]")
        for item in costume_items:
            wearer = wearer_by_item_name.get(item.name)
            log.write(f"  [magenta]{item.name}[/] — {item.description}")
            if wearer is not None:
                log.write(f"    [bold green]已穿戴者:[/] {display_name(wearer)}")
            else:
                log.write("    [dim]（未被任何角色穿戴）[/]")
        log.write("")
