"""穿戴时装 Screen：指令驱动。"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional, Tuple

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
    submit_wear_costume,
    submit_remove_costume,
)
from .utils import display_name
from ..models import (
    AppearanceComponent,
    ComponentSerialization,
    CostumeItem,
    WornCostumeComponent,
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
  [bold green]3[/]  穿戴 / 移除时装
"""


###################################################################################################################################################################
@dataclass
class _WearFlowState:
    """指令 3（穿戴 / 移除时装）多步交互（选择角色 → 选择操作 → 确认）的临时状态。"""

    step: Literal["menu", "select_actor", "select_choice", "confirm"] = "menu"
    actor_names: List[str] = field(default_factory=list)
    selected_actor: Optional[str] = None
    costume_items: List[CostumeItem] = field(default_factory=list)
    selected_item_name: Optional[str] = None  # "" 表示脱时装，否则为时装名称


class HomeWearCostumeScreen(BaseGameScreen):
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

    def __init__(self) -> None:
        super().__init__()
        self._flow = _WearFlowState()

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

        if self._flow.step == "select_actor":
            self._handle_select_actor_command(raw)
            return

        if self._flow.step == "select_choice":
            self._handle_select_choice_command(raw)
            return

        if self._flow.step == "confirm":
            self._handle_confirm_command(raw)
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

        if raw == "3":
            self._cmd_wear_costume()
            return

        log.write(f"[red]未知指令：{raw}，请输入 0 ~ 3。[/]")

    ########################################################################################################################
    def _render_actor_appearance(
        self, log: RichLog, actor_name: str, components: List[ComponentSerialization]
    ) -> None:
        """从实体组件列表中提取并渲染 AppearanceComponent + WornCostumeComponent（如有）"""
        appearance_comp: Optional[AppearanceComponent] = None
        costume_comp: Optional[WornCostumeComponent] = None
        for comp in components:
            if comp.name == AppearanceComponent.__name__:
                appearance_comp = AppearanceComponent(**comp.data)
            elif comp.name == WornCostumeComponent.__name__:
                costume_comp = WornCostumeComponent(**comp.data)

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
            log.write("    [dim]（未持有 WornCostumeComponent，即未穿戴时装）[/]")

    ########################################################################################################################
    async def _fetch_and_render_all_appearances(
        self, log: RichLog
    ) -> Optional[Tuple[List[str], Dict[str, List[ComponentSerialization]]]]:
        """一次性临时 GET：获取并渲染全部场景 · 全部角色的当前外观，同时返回
        （按渲染顺序展开的全部角色实体名列表, {角色实体名: 组件列表}）供调用方进一步
        筛选/复用（如指令 3 的可选角色过滤）。失败时返回 None（错误信息已写入 log）。"""
        log.write(
            "[bold yellow]── 当前外观（全部场景） ──────────────────────────────────────[/]"
        )

        try:
            stages_resp = await get_stages_state(self.game_client)
        except Exception as e:
            logger.error(
                f"WearCostumeScreen._fetch_and_render_all_appearances: 获取场景列表失败 error={e}"
            )
            log.write(f"[bold red]❌ 获取场景列表失败: {e}[/]")
            return None

        if not stages_resp.mapping:
            log.write("[yellow]当前没有可查询的场景。[/]")
            return [], {}

        all_actor_names = [
            name for actors in stages_resp.mapping.values() for name in actors
        ]

        try:
            details_resp = await get_entities_details(self.game_client, all_actor_names)
        except Exception as e:
            logger.error(
                f"WearCostumeScreen._fetch_and_render_all_appearances: 获取角色详情失败 error={e}"
            )
            log.write(f"[bold red]❌ 获取角色详情失败: {e}[/]")
            return None

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

        return all_actor_names, components_by_actor

    ########################################################################################################################
    @work
    async def _cmd_show_appearances(self) -> None:
        """指令 1：获取全部场景 · 全部角色的当前外观（AppearanceComponent + WornCostumeComponent）。"""
        log = self.query_one(RichLog)
        await self._fetch_and_render_all_appearances(log)

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
        """一次性临时 GET：重新拉取全部场景 · 全部角色的 WornCostumeComponent，
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
                if comp.name == WornCostumeComponent.__name__:
                    equipped = WornCostumeComponent(**comp.data)
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

    ########################################################################################################################
    @work
    async def _cmd_wear_costume(self) -> None:
        """指令 3 入口：复用指令 1 的数据获取逻辑，筛选出持有 AppearanceComponent 的角色，
        进入「选择角色」步骤。"""
        log = self.query_one(RichLog)
        log.write(
            "[bold yellow]── 穿戴 / 移除时装 ──────────────────────────────────────────[/]"
        )

        result = await self._fetch_and_render_all_appearances(log)
        if result is None:
            return
        all_actor_names, components_by_actor = result

        wearable_actor_names = [
            name
            for name in all_actor_names
            if any(
                comp.name == AppearanceComponent.__name__
                for comp in components_by_actor.get(name, [])
            )
        ]

        if not wearable_actor_names:
            log.write(
                "[yellow]当前没有可更换外观的角色（均无 AppearanceComponent）。[/]"
            )
            return

        self._flow = _WearFlowState(
            step="select_actor", actor_names=wearable_actor_names
        )

        log.write(
            "[bold yellow]── 请选择角色 ──────────────────────────────────────────[/]"
        )
        log.write("  [bold green]0[/]  取消，返回菜单")
        for idx, name in enumerate(wearable_actor_names, start=1):
            log.write(f"  [bold green]{idx}[/]  {display_name(name)}")

    ########################################################################################################################
    def _handle_select_actor_command(self, raw: str) -> None:
        log = self.query_one(RichLog)

        if raw == "0":
            self._flow = _WearFlowState()
            log.clear()
            log.write(WEAR_COSTUME_HEADER)
            log.write(COMMANDS_MENU)
            return

        if not raw.isdigit():
            log.write(f"[red]请输入编号（0 ~ {len(self._flow.actor_names)}）。[/]")
            return

        idx = int(raw)
        if idx < 1 or idx > len(self._flow.actor_names):
            log.write(f"[red]编号超出范围（0 ~ {len(self._flow.actor_names)}）。[/]")
            return

        self._flow.selected_actor = self._flow.actor_names[idx - 1]
        self._enter_select_choice()

    ########################################################################################################################
    @work
    async def _enter_select_choice(self) -> None:
        """拉取储物箱时装列表与所选角色当前穿戴信息，进入「选择操作」步骤。"""
        log = self.query_one(RichLog)
        actor_name = self._flow.selected_actor
        assert actor_name is not None

        storage_entity_name = get_storage_entity_name(self.game_client)
        costume_items = await self._fetch_storage_costume_items(
            log, storage_entity_name
        )
        if costume_items is None:
            self._flow = _WearFlowState()
            return

        try:
            details_resp = await get_entities_details(self.game_client, [actor_name])
        except Exception as e:
            logger.error(
                f"WearCostumeScreen._enter_select_choice: 获取角色详情失败 error={e}"
            )
            log.write(f"[bold red]❌ 获取角色详情失败: {e}[/]")
            self._flow = _WearFlowState()
            return

        current_item_name: Optional[str] = None
        for entity in details_resp.entities_serialization:
            if entity.name != actor_name:
                continue
            for comp in entity.components:
                if comp.name == WornCostumeComponent.__name__:
                    current_item_name = WornCostumeComponent(**comp.data).item.name

        self._flow.costume_items = costume_items
        self._flow.step = "select_choice"

        log.write(
            f"[bold yellow]── {display_name(actor_name)} · 选择操作 ──────────────[/]"
        )
        if current_item_name is not None:
            log.write(f"  [dim]当前穿戴:[/] {current_item_name}")
        else:
            log.write("  [dim]当前穿戴:（未穿戴）[/]")
        log.write("  [bold green]0[/]  脱时装")
        for idx, item in enumerate(costume_items, start=1):
            log.write(f"  [bold green]{idx}[/]  {item.name} — {item.description}")

    ########################################################################################################################
    def _handle_select_choice_command(self, raw: str) -> None:
        log = self.query_one(RichLog)

        if raw == "0":
            self._flow.selected_item_name = ""
            self._enter_confirm("脱时装")
            return

        if not raw.isdigit():
            log.write(f"[red]请输入编号（0 ~ {len(self._flow.costume_items)}）。[/]")
            return

        idx = int(raw)
        if idx < 1 or idx > len(self._flow.costume_items):
            log.write(f"[red]编号超出范围（0 ~ {len(self._flow.costume_items)}）。[/]")
            return

        item = self._flow.costume_items[idx - 1]
        self._flow.selected_item_name = item.name
        self._enter_confirm(f"穿上「{item.name}」")

    ########################################################################################################################
    def _enter_confirm(self, action_label: str) -> None:
        log = self.query_one(RichLog)
        self._flow.step = "confirm"

        actor_name = self._flow.selected_actor
        assert actor_name is not None

        log.write(
            "[bold yellow]── 确认 ─────────────────────────────────────────────────[/]"
        )
        log.write(f"  角色：{display_name(actor_name)}")
        log.write(f"  操作：{action_label}")
        log.write("  [bold green]1[/]  确认执行")
        log.write("  [bold green]0[/]  取消，返回上一步")

    ########################################################################################################################
    def _handle_confirm_command(self, raw: str) -> None:
        if raw == "0":
            self._enter_select_choice()
            return

        if raw == "1":
            self._do_wear_costume()
            return

        log = self.query_one(RichLog)
        log.write("[red]请输入 0 或 1。[/]")

    ########################################################################################################################
    @work
    async def _do_wear_costume(self) -> None:
        """提交穿戴 / 移除时装：mock 模式下本地同步模拟状态转移，真实模式下根据
        是穿装还是脱装分别调用 `home_wear_costume` 或 `home_remove_costume` 并等待
        后台任务完成。"""
        log = self.query_one(RichLog)
        input_widget = self.query_one(Input)

        actor_name = self._flow.selected_actor
        item_name = self._flow.selected_item_name
        assert actor_name is not None
        assert item_name is not None

        input_widget.disabled = True
        try:
            if item_name:
                await submit_wear_costume(self.game_client, item_name, actor_name)
            else:
                await submit_remove_costume(self.game_client, actor_name)
        except Exception as e:
            logger.error(f"WearCostumeScreen._do_wear_costume: 提交失败 error={e}")
            log.write(f"[bold red]❌ 操作失败: {e}[/]")
            self._flow = _WearFlowState()
            return
        finally:
            input_widget.disabled = False

        action_label = "脱时装" if not item_name else f"穿上「{item_name}」"
        log.write(f"[bold green]✅ {display_name(actor_name)} {action_label} 成功。[/]")

        try:
            details_resp = await get_entities_details(self.game_client, [actor_name])
            for entity in details_resp.entities_serialization:
                if entity.name == actor_name:
                    self._render_actor_appearance(log, actor_name, entity.components)
        except Exception as e:
            logger.error(f"WearCostumeScreen._do_wear_costume: 刷新外观失败 error={e}")
            log.write(f"[bold red]❌ 刷新外观失败: {e}[/]")

        self._flow = _WearFlowState()
        log.write("")
        log.write(COMMANDS_MENU)
