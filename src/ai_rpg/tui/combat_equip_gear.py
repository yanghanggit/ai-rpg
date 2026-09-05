"""战斗装备 Screen（CombatEquipGearScreen）"""

from dataclasses import dataclass, field
from itertools import zip_longest
from typing import Dict, List, Optional, Tuple, final

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from ..models import (
    CombatRoom,
    EntitySerialization,
    GearItem,
    InventoryComponent,
)
from .base import BaseGameScreen
from .combat_common import (
    classify_faction,
    find_component_data,
    find_stage_of_actor,
    render_stage_actors,
)
from .combat_data_access import (
    get_dungeon_room,
    get_entities_details,
    get_stages_state,
    is_mock_mode,
    resolve_identity,
)
from .server_client import (
    TaskFailedError,
    dungeon_combat_equip_gear,
    watch_task_until_done,
)
from .utils import display_name, render_item

BASE_INFO_HEADER = """\
[bold cyan]── 使用装备 ──────────────────────────────────────[/]

[dim]展示装备使用状态 / 场景角色摘要 / 我方装备，选择装备后转化为当前行动者手牌。[/]
"""

COMMANDS_MENU_TEMPLATE = """\
[bold yellow]── 可用操作 ─────────[/]
  [bold green]1[/]  使用装备
  [bold green]2[/]  清屏（刷新基础信息 + 清除历史信息）"""


###############################################################################################################################################
@dataclass
class _GearSnapshot:
    """使用装备页从服务器拉取到的战斗快照缓存。"""

    stage_name: Optional[str] = None
    entities_map: Dict[str, EntitySerialization] = field(default_factory=dict)
    entities: List[EntitySerialization] = field(default_factory=list)
    player_name: Optional[str] = None
    current_actor: Optional[str] = None
    current_actor_is_party: bool = False
    draw_completed: bool = False
    gear_use_count: int = 0
    gear_items: List[GearItem] = field(default_factory=list)


###############################################################################################################################################
@dataclass
class _GearFlowState:
    """使用装备多步交互（选择装备 → 确认）的临时状态。"""

    step: str = "menu"
    selected_item: Optional[GearItem] = None


###############################################################################################################################################
def _write_indexed_gear(log: RichLog, index: int, item: GearItem) -> None:
    """渲染单件装备，并将编号与物品名写在同一行。"""
    lines = render_item(item).split("\n")
    if lines:
        lines[0] = f"  [bold green]{index}[/] {lines[0].strip()}"
    for line in lines:
        log.write(line)


@final
class CombatEquipGearScreen(BaseGameScreen):
    """战斗 ONGOING 阶段的使用装备页面：展示装备使用状态 + 场景内角色有效属性 +
    我方装备列表，并提供使用装备 / 清屏指令入口。

    使用装备为多步交互（选择装备 → 确认），通过 ``self._flow.step`` 记录当前所处
    步骤；Escape 在任意步骤都会直接返回上一页（CombatOngoingScreen）。

    装备是队伍级行为：GearItem 由当前行动者（我方）转化为一张 Card 进入其手牌，
    无目标选择，也不消耗 energy。
    """

    CSS = """
    CombatEquipGearScreen {
        align: center middle;
    }

    #combat-equip-gear-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #combat-equip-gear-input-row {
        height: 3;
        dock: bottom;
    }

    #combat-equip-gear-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #combat-equip-gear-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._snapshot = _GearSnapshot()
        self._flow = _GearFlowState()

    def compose(self) -> ComposeResult:
        yield RichLog(
            id="combat-equip-gear-log", highlight=True, markup=True, wrap=True
        )
        with Horizontal(id="combat-equip-gear-input-row"):
            yield Static("> ", id="combat-equip-gear-prompt")
            yield Input(placeholder="输入指令编号...", id="combat-equip-gear-input")

    def on_mount(self) -> None:
        self._load_base_info()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    ########################################################################################################################
    @work
    async def _load_base_info(self, clear: bool = True) -> None:
        """`_load_base_info_impl` 的后台 worker 包装（Textual `@work` 会把方法
        调用转换为 `Worker[None]`，无法直接 `await`，故需要这层包装供不需要等待的
        调用点使用）。"""
        await self._load_base_info_impl(clear)

    ########################################################################################################################
    async def _fetch_state(self) -> Tuple[bool, str]:
        """重新从服务器拉取最新数据并整体替换 `self._snapshot`，不写日志、不改变
        `self._flow`。返回 (是否成功, 失败时的错误描述)。"""
        try:
            _, _, actor_name = resolve_identity(self.game_client)

            room_resp = await get_dungeon_room(self.game_client)
            stages_resp = await get_stages_state(self.game_client)

            room = room_resp.room
            assert isinstance(
                room, CombatRoom
            ), f"当前房间不是战斗房间：type={room.type}"
            assert room.type == "combat"
            combat = room.combat

            stage_name = find_stage_of_actor(stages_resp.mapping, actor_name)
            assert (
                stage_name is not None
            ), f"未能在场景映射中找到玩家角色所在场景：actor={actor_name}"
            actor_names = stages_resp.mapping[stage_name]
            entity_names = [stage_name, *actor_names]

            entities_resp = await get_entities_details(self.game_client, entity_names)
        except Exception as e:
            msg = f"加载装备基础信息失败：{e}"
            logger.error(f"CombatEquipGearScreen._fetch_state: {msg}")
            return False, msg

        entities_map = {
            e.name: e for e in entities_resp.entities if e.name != stage_name
        }

        latest_round = combat.latest_round
        current_actor = latest_round.current_actor if latest_round is not None else None
        current_actor_entity = (
            entities_map.get(current_actor) if current_actor else None
        )
        current_actor_is_party = classify_faction(current_actor_entity) == "party"
        draw_completed = (
            latest_round.draw_completed if latest_round is not None else False
        )
        gear_use_count = (
            latest_round.gear_equip_count if latest_round is not None else 0
        )

        player_entity = entities_map.get(actor_name)
        inventory_data = (
            find_component_data(player_entity, InventoryComponent.__name__)
            if player_entity is not None
            else None
        )
        gear_items = (
            [
                item
                for item in InventoryComponent(**inventory_data).items
                if isinstance(item, GearItem)
            ]
            if inventory_data is not None
            else []
        )

        self._snapshot = _GearSnapshot(
            stage_name=stage_name,
            entities_map=entities_map,
            entities=entities_resp.entities,
            player_name=actor_name,
            current_actor=current_actor,
            current_actor_is_party=current_actor_is_party,
            draw_completed=draw_completed,
            gear_use_count=gear_use_count,
            gear_items=gear_items,
        )
        return True, ""

    ########################################################################################################################
    async def _load_base_info_impl(self, clear: bool = True) -> None:
        """重新拉取最新数据并渲染装备使用状态 + 场景内角色摘要 + 我方装备列表。"""
        log = self.query_one(RichLog)
        if clear:
            log.clear()
            log.write(BASE_INFO_HEADER)
        logger.info(
            f"CombatEquipGearScreen._load_base_info_impl: 开始加载 clear={clear}"
        )

        ok, err = await self._fetch_state()
        if not ok:
            log.write(f"[bold red]❌ {err}[/]")
            return

        assert self._snapshot.stage_name is not None
        current_actor_label = (
            display_name(self._snapshot.current_actor)
            if self._snapshot.current_actor
            else "（无）"
        )
        party_label = (
            "[green]是[/]" if self._snapshot.current_actor_is_party else "[red]否[/]"
        )
        draw_label = (
            "[green]是[/]" if self._snapshot.draw_completed else "[yellow]否[/]"
        )

        log.write("[bold yellow]── 装备使用状态 ─────────────────────────────[/]")
        log.write(
            f"  当前 turn 角色： [bold yellow]{current_actor_label}[/]"
            f"（我方：{party_label}）"
        )
        log.write(f"  抽牌已完成：     {draw_label}")
        log.write(
            f"  本回合已使用：   [bold]{self._snapshot.gear_use_count}[/] 次（无次数上限）"
        )
        log.write("")

        render_stage_actors(log, self._snapshot.stage_name, self._snapshot.entities)

        log.write("[bold yellow]── 我方装备 ─────────────────────────────[/]")
        if not self._snapshot.gear_items:
            log.write("  [dim]（背包中没有装备）[/]")
        else:
            for i, item in enumerate(self._snapshot.gear_items, start=1):
                _write_indexed_gear(log, i, item)
        log.write("")

        self._flow = _GearFlowState()
        log.write(COMMANDS_MENU_TEMPLATE)

    ########################################################################################################################
    @on(Input.Submitted, "#combat-equip-gear-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        if not raw:
            return
        self._dispatch_command(raw)

    ########################################################################################################################
    def _dispatch_command(self, raw: str) -> None:
        """按当前所处步骤（menu / select_item / confirm）分发输入。"""
        if self._flow.step == "menu":
            self._handle_menu_command(raw)
        elif self._flow.step == "select_item":
            self._handle_select_item_command(raw)
        elif self._flow.step == "confirm":
            self._handle_confirm_command(raw)

    ########################################################################################################################
    def _back_to_menu(self, log: RichLog) -> None:
        self._flow = _GearFlowState()
        log.write(COMMANDS_MENU_TEMPLATE)

    ########################################################################################################################
    def _handle_menu_command(self, raw: str) -> None:
        log = self.query_one(RichLog)
        if raw == "1":
            self._enter_select_item(log)
        elif raw == "2":
            self._load_base_info(clear=True)
        else:
            log.write("[red]无效指令，请输入 1 或 2[/]")

    ########################################################################################################################
    def _enter_select_item(self, log: RichLog) -> None:
        if not self._snapshot.draw_completed:
            log.write("[yellow]本回合抽牌阶段尚未完成，暂时无法使用装备。[/]")
            return
        if not self._snapshot.current_actor_is_party:
            log.write("[yellow]当前行动者不是我方角色，暂时无法使用装备。[/]")
            return
        if not self._snapshot.gear_items:
            log.write("[yellow]背包中没有可用的装备。[/]")
            return

        log.write("[bold yellow]── 选择装备 ─────────────────────────────────[/]")
        for i, item in enumerate(self._snapshot.gear_items, start=1):
            _write_indexed_gear(log, i, item)
        log.write("")
        log.write("[dim]输入编号选择要使用的装备；输入 0 取消，返回菜单。[/]")
        self._flow.step = "select_item"

    ########################################################################################################################
    def _handle_select_item_command(self, raw: str) -> None:
        log = self.query_one(RichLog)
        if raw == "0":
            log.write("[dim]已取消使用，返回菜单。[/]")
            self._back_to_menu(log)
            return
        if not raw.isdigit():
            log.write("[red]请输入装备编号，或输入 0 取消。[/]")
            return

        idx = int(raw)
        items = self._snapshot.gear_items
        if idx < 1 or idx > len(items):
            log.write(
                f"[red]编号超出范围（1-{len(items)}），请重新输入，或输入 0 取消。[/]"
            )
            return

        item = items[idx - 1]
        self._flow.selected_item = item
        self._enter_confirm(log)

    ########################################################################################################################
    def _enter_confirm(self, log: RichLog) -> None:
        item = self._flow.selected_item
        assert item is not None

        current_actor_label = display_name(self._snapshot.current_actor or "当前行动者")
        log.write("[bold yellow]── 确认使用 ─────────────────────────────────[/]")
        log.write(render_item(item))
        log.write(f"  装备到： {current_actor_label}")
        log.write("")
        log.write("  [bold green]1[/]  确认使用")
        log.write("  [bold green]0[/]  取消，返回菜单")
        self._flow.step = "confirm"

    ########################################################################################################################
    def _handle_confirm_command(self, raw: str) -> None:
        log = self.query_one(RichLog)
        if raw == "0":
            log.write("[dim]已取消使用，返回菜单。[/]")
            self._back_to_menu(log)
            return
        if raw != "1":
            log.write("[red]请输入 1 确认使用，或输入 0 取消。[/]")
            return

        self._confirm_and_equip_gear()

    ########################################################################################################################
    async def _finish_equip_flow(self, inp: Input) -> None:
        """使用流程结束后的收尾：静默重新拉取最新数据，重置 `self._flow` 并重新启用输入框。"""
        ok, err = await self._fetch_state()
        if not ok:
            logger.warning(
                f"CombatEquipGearScreen._finish_equip_flow: 静默刷新缓存失败（{err}），"
                "建议手动输入 2 清屏重试"
            )
        self._flow = _GearFlowState()
        inp.disabled = False
        inp.focus()

    ########################################################################################################################
    @work
    async def _confirm_and_equip_gear(self) -> None:
        """提交使用装备请求并等待后台任务完成，展示本回合新增的 gear_combat_log /
        gear_narrative 作为使用结果。"""
        log = self.query_one(RichLog)
        item = self._flow.selected_item
        assert item is not None, "_confirm_and_equip_gear: 未选择装备"

        inp = self.query_one(Input)
        inp.disabled = True

        log.write(f"[dim]▶ 正在使用：{item.name} ...[/]")

        if is_mock_mode(self.game_client):
            logger.info(
                "CombatEquipGearScreen._confirm_and_equip_gear: mock 模式，模拟使用结果"
            )
            log.write(
                "[bold yellow]\\[mock][/] 已模拟提交使用装备请求（未调用真实接口）。"
            )
            log.write("[bold green]✅ 使用完成[/]")
            log.write("[bold yellow]── 使用结果 ─────────────────────────────────[/]")
            log.write(f"  [dim]战斗：[/] 将『{item.name}』转化为手牌。")
            log.write(f"  [dim]叙事：[/] {item.description}")
            log.write("")
            await self._finish_equip_flow(inp)
            return

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)

            baseline_room_resp = await get_dungeon_room(self.game_client)
            baseline_room = baseline_room_resp.room
            assert isinstance(baseline_room, CombatRoom)
            baseline_round = baseline_room.combat.latest_round
            baseline_log_count = (
                len(baseline_round.gear_combat_log) if baseline_round else 0
            )
            baseline_narrative_count = (
                len(baseline_round.gear_narrative) if baseline_round else 0
            )

            resp = await dungeon_combat_equip_gear(user_name, game_name, item.name)
            log.write(f"[dim]任务已提交：{resp.job_id}，等待完成...[/]")
            await watch_task_until_done(resp.job_id)
        except TaskFailedError as e:
            logger.error(
                f"CombatEquipGearScreen._confirm_and_equip_gear: 使用任务失败 error={e}"
            )
            log.write(f"[bold red]❌ 使用失败：{e}[/]")
            log.write("")
            await self._finish_equip_flow(inp)
            return
        except Exception as e:
            logger.error(
                f"CombatEquipGearScreen._confirm_and_equip_gear: 使用请求失败 error={e}"
            )
            log.write(f"[bold red]❌ 使用请求失败：{e}[/]")
            log.write("")
            await self._finish_equip_flow(inp)
            return

        log.write("[bold green]✅ 使用完成[/]")

        try:
            result_room_resp = await get_dungeon_room(self.game_client)
            result_room = result_room_resp.room
            assert isinstance(result_room, CombatRoom)
            latest_round = result_room.combat.latest_round
        except Exception as e:
            logger.error(
                f"CombatEquipGearScreen._confirm_and_equip_gear: 加载使用结果失败 error={e}"
            )
            log.write(f"[bold red]❌ 加载使用结果失败：{e}[/]")
            log.write("")
            await self._finish_equip_flow(inp)
            return

        if latest_round is not None:
            new_logs = latest_round.gear_combat_log[baseline_log_count:]
            new_narratives = latest_round.gear_narrative[baseline_narrative_count:]
            if new_logs or new_narratives:
                log.write(
                    "[bold yellow]── 使用结果 ─────────────────────────────────[/]"
                )
                for combat_log, narrative in zip_longest(new_logs, new_narratives):
                    log.write(f"  [dim]战斗：[/] {combat_log or '[dim]（无）[/]'}")
                    log.write(f"  [dim]叙事：[/] {narrative or '[dim]（无）[/]'}")
        log.write("")

        await self._finish_equip_flow(inp)
