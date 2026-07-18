"""战斗使用消耗品 Screen（CombatUseConsumableScreen）"""

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
    ConsumableItem,
    DeathComponent,
    EntitySerialization,
    InventoryComponent,
    StatusEffectsComponent,
    TargetType,
)
from .base import BaseGameScreen
from .combat_common import (
    classify_faction,
    compute_effective_stats_for,
    find_component_data,
    find_stage_of_actor,
    is_alive,
    render_stage_actors,
    resolve_current_energy,
    role_label,
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
    dungeon_combat_use_consumable,
    watch_task_until_done,
)
from .utils import display_name, render_item, render_status_effect

BASE_INFO_HEADER = """\
[bold cyan]── 使用消耗品 ──────────────────────────────────────[/]

[dim]展示消耗品使用状态 / 场景角色摘要 / 我方消耗品，选择消耗品与目标后确认使用。[/]
"""

COMMANDS_MENU_TEMPLATE = """\
[bold yellow]── 可用操作 ─────────[/]
  [bold green]1[/]  使用消耗品
  [bold green]2[/]  清屏（刷新基础信息 + 清除历史信息）"""


###############################################################################################################################################
@dataclass
class _ConsumableSnapshot:
    """使用消耗品页从服务器拉取到的战斗快照缓存。"""

    stage_name: Optional[str] = None
    entities_map: Dict[str, EntitySerialization] = field(default_factory=dict)
    entities_serialization: List[EntitySerialization] = field(default_factory=list)
    player_name: Optional[str] = None
    current_actor: Optional[str] = None
    current_actor_is_party: bool = False
    draw_completed: bool = False
    consumable_use_count: int = 0
    consumable_items: List[ConsumableItem] = field(default_factory=list)


###############################################################################################################################################
@dataclass
class _UseFlowState:
    """使用消耗品多步交互（选择消耗品 → 选择目标 → 确认）的临时状态。"""

    step: str = "menu"
    selected_item: Optional[ConsumableItem] = None
    pending_targets: List[str] = field(default_factory=list)
    target_candidates: List[Tuple[str, EntitySerialization]] = field(
        default_factory=list
    )


###############################################################################################################################################
def _write_indexed_item(log: RichLog, index: int, item: ConsumableItem) -> None:
    """渲染单件消耗品，并将编号与物品名写在同一行（而非单独一行编号后换行）。"""
    lines = render_item(item).split("\n")
    if lines:
        lines[0] = f"  [bold green]{index}[/] {lines[0].strip()}"
    for line in lines:
        log.write(line)


@final
class CombatUseConsumableScreen(BaseGameScreen):
    """战斗 ONGOING 阶段的使用消耗品页面：展示消耗品使用状态 + 场景内角色有效
    属性 + 我方消耗品列表，并提供使用消耗品 / 清屏指令入口。

    使用消耗品为多步交互（选择消耗品 → 选择目标 → 确认），通过 ``self._flow.step``
    记录当前所处步骤，同一个 Input 在不同步骤下承载不同语义；Escape 在任意步骤
    都会直接返回上一页（CombatOngoingScreen），中断进行中的使用流程。

    消耗品是队伍级行为，始终挂在玩家自身实体上（而非当前 turn 角色），因此目标
    解析的阵营锚点固定为玩家；但服务端要求当前 turn 必须是我方角色才允许使用，
    故基础信息里仍会展示当前 turn 角色，便于玩家判断当前是否可用。
    """

    CSS = """
    CombatUseConsumableScreen {
        align: center middle;
    }

    #combat-use-consumable-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #combat-use-consumable-input-row {
        height: 3;
        dock: bottom;
    }

    #combat-use-consumable-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #combat-use-consumable-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._snapshot = _ConsumableSnapshot()
        self._flow = _UseFlowState()

    def compose(self) -> ComposeResult:
        yield RichLog(
            id="combat-use-consumable-log", highlight=True, markup=True, wrap=True
        )
        with Horizontal(id="combat-use-consumable-input-row"):
            yield Static("> ", id="combat-use-consumable-prompt")
            yield Input(placeholder="输入指令编号...", id="combat-use-consumable-input")

    def on_mount(self) -> None:
        self._load_base_info()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    ########################################################################################################################
    def _write_target_detail(
        self, log: RichLog, entity: EntitySerialization, index_label: str = ""
    ) -> None:
        """渲染单个候选目标的有效属性 + 状态效果（不含手牌，目标选择无需关心）。

        index_label: 非空时与角色名写在同一行前面（如目标候选列表的编号）。
        """
        effective_stats = compute_effective_stats_for(entity)
        if effective_stats is None:
            log.write(
                f"  {index_label}[yellow]{display_name(entity.name)} 缺少属性组件，跳过[/]"
            )
            return

        status_data = find_component_data(entity, StatusEffectsComponent.__name__)
        status_comp = (
            StatusEffectsComponent(**status_data) if status_data is not None else None
        )
        death_mark = (
            "  [bold red]（已战死）[/]"
            if find_component_data(entity, DeathComponent.__name__) is not None
            else ""
        )

        log.write(
            f"  {index_label}{role_label(entity)} [bold]{display_name(entity.name)}[/]{death_mark}"
        )
        log.write(
            f"    HP:[yellow]{effective_stats.hp}/{effective_stats.max_hp}[/]  "
            f"攻:{effective_stats.attack}  防:{effective_stats.defense}  "
            f"能量:{resolve_current_energy(entity, effective_stats)}  速度:{effective_stats.speed}"
        )

        if status_comp is not None and status_comp.status_effects:
            log.write(f"    状态效果（{len(status_comp.status_effects)}）：")
            for effect in status_comp.status_effects:
                log.write(render_status_effect(effect, entity.name))
        else:
            log.write("    状态效果： [dim]（无）[/]")

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
        `self._flow`。返回 (是否成功, 失败时的错误描述)。

        使用消耗品会改变场景内任意实体的属性/状态，且消耗品本身来自玩家背包，
        因此绝不能复用旧快照；本方法是 `_snapshot` 的唯一写入点。
        """
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
            msg = f"加载消耗品基础信息失败：{e}"
            logger.error(f"CombatUseConsumableScreen._fetch_state: {msg}")
            return False, msg

        entities_map = {
            e.name: e
            for e in entities_resp.entities_serialization
            if e.name != stage_name
        }

        latest_round = combat.latest_round
        assert latest_round is not None, "当前战斗没有最新回合快照"
        current_actor = latest_round.current_actor
        current_actor_entity = (
            entities_map.get(current_actor) if current_actor else None
        )

        current_actor_is_party = (
            classify_faction(current_actor_entity) == "party"
            if current_actor_entity is not None
            else False
        )

        player_entity = entities_map.get(actor_name)
        inventory_data = (
            find_component_data(player_entity, InventoryComponent.__name__)
            if player_entity is not None
            else None
        )
        consumable_items = (
            [
                item
                for item in InventoryComponent(**inventory_data).items
                if isinstance(item, ConsumableItem)
            ]
            if inventory_data is not None
            else []
        )

        self._snapshot = _ConsumableSnapshot(
            stage_name=stage_name,
            entities_map=entities_map,
            entities_serialization=entities_resp.entities_serialization,
            player_name=actor_name,
            current_actor=current_actor,
            current_actor_is_party=current_actor_is_party,
            draw_completed=latest_round.draw_completed,
            consumable_use_count=latest_round.consumable_use_count,
            consumable_items=consumable_items,
        )
        return True, ""

    ########################################################################################################################
    async def _load_base_info_impl(self, clear: bool = True) -> None:
        """重新拉取最新数据并渲染消耗品使用状态 + 场景内角色摘要 + 我方消耗品列表。

        clear=True（初次进入 / 清屏）：先清空 RichLog 再整体重写；clear=False
        （使用结果反馈之后）：不清空，只在已展示的结果之后追加最新信息。
        加载完成后会把 `self._flow` 重置为新实例（回到 "menu" 步骤）。
        """
        log = self.query_one(RichLog)
        if clear:
            log.clear()
            log.write(BASE_INFO_HEADER)
        logger.info(
            f"CombatUseConsumableScreen._load_base_info_impl: 开始加载 clear={clear}"
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
        used_label = (
            f"[red]是[/]（已用 {self._snapshot.consumable_use_count} 次）"
            if self._snapshot.consumable_use_count > 0
            else "[green]否[/]"
        )

        log.write("[bold yellow]── 消耗品使用状态 ─────────────────────────────[/]")
        log.write(
            f"  当前 turn 角色： [bold yellow]{current_actor_label}[/]"
            f"（我方：{party_label}）"
        )
        log.write(f"  抽牌已完成：     {draw_label}")
        log.write(f"  本回合已使用：   {used_label}")
        log.write("")

        render_stage_actors(
            log, self._snapshot.stage_name, self._snapshot.entities_serialization
        )

        log.write("[bold yellow]── 我方消耗品 ─────────────────────────────[/]")
        if not self._snapshot.consumable_items:
            log.write("  [dim]（背包中没有消耗品）[/]")
        else:
            for i, item in enumerate(self._snapshot.consumable_items, start=1):
                _write_indexed_item(log, i, item)
        log.write("")

        self._flow = _UseFlowState()
        log.write(COMMANDS_MENU_TEMPLATE)

    ########################################################################################################################
    @on(Input.Submitted, "#combat-use-consumable-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        if not raw:
            return
        self._dispatch_command(raw)

    ########################################################################################################################
    def _dispatch_command(self, raw: str) -> None:
        """按当前所处步骤（menu / select_item / select_target / confirm）分发输入。"""
        if self._flow.step == "menu":
            self._handle_menu_command(raw)
        elif self._flow.step == "select_item":
            self._handle_select_item_command(raw)
        elif self._flow.step == "select_target":
            self._handle_select_target_command(raw)
        elif self._flow.step == "confirm":
            self._handle_confirm_command(raw)

    ########################################################################################################################
    def _back_to_menu(self, log: RichLog) -> None:
        self._flow = _UseFlowState()
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
            log.write("[yellow]本回合抽牌阶段尚未完成，暂时无法使用消耗品。[/]")
            return
        if not self._snapshot.current_actor_is_party:
            log.write("[yellow]当前不是我方回合，暂时无法使用消耗品。[/]")
            return
        if self._snapshot.consumable_use_count > 0:
            log.write("[yellow]本回合已使用过消耗品，每回合限用一次。[/]")
            return
        if not self._snapshot.consumable_items:
            log.write("[yellow]背包中没有可用的消耗品。[/]")
            return

        log.write("[bold yellow]── 选择消耗品 ─────────────────────────────────[/]")
        for i, item in enumerate(self._snapshot.consumable_items, start=1):
            _write_indexed_item(log, i, item)
        log.write("")
        log.write("[dim]输入编号选择要使用的消耗品；输入 0 取消，返回菜单。[/]")
        self._flow.step = "select_item"

    ########################################################################################################################
    def _handle_select_item_command(self, raw: str) -> None:
        log = self.query_one(RichLog)
        if raw == "0":
            log.write("[dim]已取消使用，返回菜单。[/]")
            self._back_to_menu(log)
            return
        if not raw.isdigit():
            log.write("[red]请输入消耗品编号，或输入 0 取消。[/]")
            return

        idx = int(raw)
        items = self._snapshot.consumable_items
        if idx < 1 or idx > len(items):
            log.write(
                f"[red]编号超出范围（1-{len(items)}），请重新输入，或输入 0 取消。[/]"
            )
            return

        self._flow.selected_item = items[idx - 1]
        self._enter_select_target(log)

    ########################################################################################################################
    def _enter_select_target(self, log: RichLog) -> None:
        item = self._flow.selected_item
        assert item is not None

        player_name = self._snapshot.player_name
        actor_faction = "party"  # 消耗品固定挂在玩家（我方）实体上，锚点恒为 party

        if item.target_type == TargetType.SELF_ONLY:
            self._flow.pending_targets = [player_name] if player_name else []
            self._enter_confirm(log)
            return

        if item.target_type in (TargetType.ENEMY_ALL, TargetType.ENEMY_SPREAD):
            # 由服务端按 target_type 自动解析目标，客户端传空列表即可。
            self._flow.pending_targets = []
            self._enter_confirm(log)
            return

        if item.target_type == TargetType.ALLY_ALL:
            self._flow.pending_targets = [
                name
                for name, entity in self._snapshot.entities_map.items()
                if name != player_name
                and classify_faction(entity) == actor_faction
                and is_alive(entity)
            ]
            self._enter_confirm(log)
            return

        if item.target_type == TargetType.ENEMY_SINGLE:
            candidates = [
                (name, entity)
                for name, entity in self._snapshot.entities_map.items()
                if classify_faction(entity) not in ("unknown", actor_faction)
                and is_alive(entity)
            ]
        elif item.target_type == TargetType.ALLY_SINGLE:
            candidates = [
                (name, entity)
                for name, entity in self._snapshot.entities_map.items()
                if name != player_name
                and classify_faction(entity) == actor_faction
                and is_alive(entity)
            ]
        else:
            # TargetType.CARD 等暂不在本页支持选择目标，直接以空目标使用，交由服务端处理。
            log.write(
                f"[yellow]目标类型 {item.target_type.value} 暂不支持在本页选择目标，使用时将不指定目标。[/]"
            )
            self._flow.pending_targets = []
            self._enter_confirm(log)
            return

        if not candidates:
            log.write("[red]当前没有可选的目标，使用已取消，返回菜单。[/]")
            self._back_to_menu(log)
            return

        self._flow.target_candidates = candidates
        log.write("[bold yellow]── 选择目标 ─────────────────────────────────[/]")
        log.write(render_item(item))
        log.write("")
        for i, (_, entity) in enumerate(candidates, start=1):
            log.write("[dim]────────────────────────────[/]")
            self._write_target_detail(log, entity, index_label=f"[bold green]{i}[/] ")

        log.write("")
        log.write("[dim]输入编号选择目标；输入 0 取消，返回菜单。[/]")
        self._flow.step = "select_target"

    ########################################################################################################################
    def _handle_select_target_command(self, raw: str) -> None:
        log = self.query_one(RichLog)
        if raw == "0":
            log.write("[dim]已取消使用，返回菜单。[/]")
            self._back_to_menu(log)
            return
        if not raw.isdigit():
            log.write("[red]请输入目标编号，或输入 0 取消。[/]")
            return

        idx = int(raw)
        candidates = self._flow.target_candidates
        if idx < 1 or idx > len(candidates):
            log.write(
                f"[red]编号超出范围（1-{len(candidates)}），请重新输入，或输入 0 取消。[/]"
            )
            return

        target_name, _ = candidates[idx - 1]
        self._flow.pending_targets = [target_name]
        self._enter_confirm(log)

    ########################################################################################################################
    def _enter_confirm(self, log: RichLog) -> None:
        item = self._flow.selected_item
        assert item is not None

        targets_label = (
            "、".join(display_name(t) for t in self._flow.pending_targets)
            if self._flow.pending_targets
            else "（由服务端自动指定）"
        )

        log.write("[bold yellow]── 确认使用 ─────────────────────────────────[/]")
        log.write(render_item(item))
        log.write(f"  目标： {targets_label}")
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

        self._confirm_and_use()

    ########################################################################################################################
    async def _finish_use_flow(self, inp: Input) -> None:
        """使用流程结束（成功 / 失败 / 中途异常）后的收尾：静默重新拉取最新数据
        替换 `self._snapshot`（不写日志、不追加任何信息），重置 `self._flow` 并重新
        启用输入框，交由玩家自行按 Escape 返回或输入 2 清屏刷新。"""
        ok, err = await self._fetch_state()
        if not ok:
            logger.warning(
                f"CombatUseConsumableScreen._finish_use_flow: 静默刷新缓存失败（{err}），"
                "建议手动输入 2 清屏重试"
            )
        self._flow = _UseFlowState()
        inp.disabled = False
        inp.focus()

    ########################################################################################################################
    @work
    async def _confirm_and_use(self) -> None:
        """提交使用消耗品请求并等待后台任务完成，展示本回合新增的
        consumable_combat_log / consumable_narrative 作为使用结果。结果展示完毕后
        不再自动刷新，交由玩家自行按 Escape 返回或输入 2 清屏。"""
        log = self.query_one(RichLog)
        item = self._flow.selected_item
        assert item is not None, "_confirm_and_use: 未选择消耗品"
        targets = list(self._flow.pending_targets)

        inp = self.query_one(Input)
        inp.disabled = True

        targets_label = (
            "、".join(display_name(t) for t in targets) if targets else "（自动目标）"
        )
        log.write(f"[dim]▶ 正在使用：{item.name} → {targets_label} ...[/]")

        if is_mock_mode(self.game_client):
            logger.info(
                "CombatUseConsumableScreen._confirm_and_use: mock 模式，模拟使用结果"
            )
            log.write(
                "[bold yellow]\\[mock][/] 已模拟提交使用消耗品请求（未调用真实接口）。"
            )
            log.write("[bold green]✅ 使用完成[/]")
            log.write("[bold yellow]── 使用结果 ─────────────────────────────────[/]")
            log.write(f"  [dim]战斗：[/] 使用『{item.name}』对 {targets_label} 生效。")
            log.write(
                f"  [dim]叙事：[/] 一股暖流涌入体内，『{item.name}』的效力发挥了作用。"
            )
            log.write("")
            await self._finish_use_flow(inp)
            return

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)

            # 使用前先重新 GET 一次，记录当前回合消耗品日志/叙事的基线长度，
            # 便于使用完成后精确 diff 出本次新增的条目。
            baseline_room_resp = await get_dungeon_room(self.game_client)
            baseline_room = baseline_room_resp.room
            assert isinstance(baseline_room, CombatRoom)
            baseline_round = baseline_room.combat.latest_round
            baseline_log_count = (
                len(baseline_round.consumable_combat_log) if baseline_round else 0
            )
            baseline_narrative_count = (
                len(baseline_round.consumable_narrative) if baseline_round else 0
            )

            resp = await dungeon_combat_use_consumable(
                user_name, game_name, item.name, targets
            )
            log.write(f"[dim]任务已提交：{resp.task_id}，等待完成...[/]")
            await watch_task_until_done(resp.task_id)
        except TaskFailedError as e:
            logger.error(
                f"CombatUseConsumableScreen._confirm_and_use: 使用任务失败 error={e}"
            )
            log.write(f"[bold red]❌ 使用失败：{e}[/]")
            log.write("")
            await self._finish_use_flow(inp)
            return
        except Exception as e:
            logger.error(
                f"CombatUseConsumableScreen._confirm_and_use: 使用请求失败 error={e}"
            )
            log.write(f"[bold red]❌ 使用请求失败：{e}[/]")
            log.write("")
            await self._finish_use_flow(inp)
            return

        log.write("[bold green]✅ 使用完成[/]")

        try:
            result_room_resp = await get_dungeon_room(self.game_client)
            result_room = result_room_resp.room
            assert isinstance(result_room, CombatRoom)
            latest_round = result_room.combat.latest_round
        except Exception as e:
            logger.error(
                f"CombatUseConsumableScreen._confirm_and_use: 加载使用结果失败 error={e}"
            )
            log.write(f"[bold red]❌ 加载使用结果失败：{e}[/]")
            log.write("")
            await self._finish_use_flow(inp)
            return

        if latest_round is not None:
            new_logs = latest_round.consumable_combat_log[baseline_log_count:]
            new_narratives = latest_round.consumable_narrative[
                baseline_narrative_count:
            ]
            if new_logs or new_narratives:
                log.write(
                    "[bold yellow]── 使用结果 ─────────────────────────────────[/]"
                )
                for combat_log, narrative in zip_longest(new_logs, new_narratives):
                    log.write(f"  [dim]战斗：[/] {combat_log or '[dim]（无）[/]'}")
                    log.write(f"  [dim]叙事：[/] {narrative or '[dim]（无）[/]'}")
        log.write("")

        await self._finish_use_flow(inp)
