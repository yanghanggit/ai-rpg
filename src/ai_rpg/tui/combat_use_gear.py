"""战斗使用装备 Screen（CombatUseGearScreen）"""

from dataclasses import dataclass, field
from itertools import zip_longest
from typing import Dict, List, Optional, Set, Tuple, final

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from ..models import (
    CombatRoom,
    DeathComponent,
    EntitySerialization,
    EquippedGearComponent,
    GearItem,
    InventoryComponent,
    StatusEffectsComponent,
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
    dungeon_combat_use_gear,
    watch_task_until_done,
)
from .utils import display_name, render_item, render_status_effect

BASE_INFO_HEADER = """\
[bold cyan]── 使用装备 ──────────────────────────────────────[/]

[dim]展示装备使用状态 / 场景角色摘要 / 我方装备，选择装备与目标后确认使用。[/]
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
    entities_serialization: List[EntitySerialization] = field(default_factory=list)
    player_name: Optional[str] = None
    current_actor: Optional[str] = None
    current_actor_is_player: bool = False
    draw_completed: bool = False
    gear_use_count: int = 0
    gear_items: List[GearItem] = field(default_factory=list)
    # 当前已被任意实体装备中的装备 uuid 集合；命中的道具服务端会拒绝再次使用
    # （见 activate_use_gear 的“已被装备”前置校验），本页据此提前过滤/提示。
    equipped_uuids: Set[str] = field(default_factory=set)


###############################################################################################################################################
@dataclass
class _GearFlowState:
    """使用装备多步交互（选择装备 → 选择目标 → 确认）的临时状态。"""

    step: str = "menu"
    selected_item: Optional[GearItem] = None
    pending_targets: List[str] = field(default_factory=list)
    target_candidates: List[Tuple[str, EntitySerialization]] = field(
        default_factory=list
    )


###############################################################################################################################################
def _write_indexed_gear(
    log: RichLog, index: int, item: GearItem, equipped_uuids: Set[str]
) -> None:
    """渲染单件装备，并将编号与物品名写在同一行；若该装备当前已被装备中，标注
    「已装备，不可再次使用」提示（而非单独一行编号后换行）。"""
    lines = render_item(item).split("\n")
    if lines:
        marker = (
            "  [red]（已装备，不可再次使用）[/]" if item.uuid in equipped_uuids else ""
        )
        lines[0] = f"  [bold green]{index}[/] {lines[0].strip()}{marker}"
    for line in lines:
        log.write(line)


@final
class CombatUseGearScreen(BaseGameScreen):
    """战斗 ONGOING 阶段的使用装备页面：展示装备使用状态 + 场景内角色有效属性 +
    我方装备列表，并提供使用装备 / 清屏指令入口。

    使用装备为多步交互（选择装备 → 选择目标 → 确认），通过 ``self._flow.step``
    记录当前所处步骤，同一个 Input 在不同步骤下承载不同语义；Escape 在任意步骤
    都会直接返回上一页（CombatOngoingScreen），中断进行中的使用流程。

        装备同样是队伍级行为，始终挂在玩家自身实体上，且必须由玩家本人回合发动；
    与消耗品的关键差异：
        - 目标恒为单一友方（可含玩家自身），服务端要求解析结果恰好 1 个目标；
    - 消耗的是**目标**（而非玩家）本回合剩余 energy（`RoundStatsComponent`），
            目标 energy 不足以支付装备 cost 时无法为其装备；
    - 无「每回合限用一次」的限制，但同一件装备若已被任意实体装备中则不可再次
      使用，直到下一关 / 退出地下城清空。
    """

    CSS = """
    CombatUseGearScreen {
        align: center middle;
    }

    #combat-use-gear-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #combat-use-gear-input-row {
        height: 3;
        dock: bottom;
    }

    #combat-use-gear-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #combat-use-gear-input {
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
        yield RichLog(id="combat-use-gear-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="combat-use-gear-input-row"):
            yield Static("> ", id="combat-use-gear-prompt")
            yield Input(placeholder="输入指令编号...", id="combat-use-gear-input")

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

        使用装备会改变目标实体的 `EquippedGearComponent` 与本回合剩余 energy，
        且装备本身来自玩家背包，因此绝不能复用旧快照；本方法是 `_snapshot` 的
        唯一写入点。
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
            msg = f"加载装备基础信息失败：{e}"
            logger.error(f"CombatUseGearScreen._fetch_state: {msg}")
            return False, msg

        entities_map = {
            e.name: e
            for e in entities_resp.entities_serialization
            if e.name != stage_name
        }

        latest_round = combat.latest_round
        current_actor = latest_round.current_actor if latest_round is not None else None
        current_actor_is_player = current_actor == actor_name
        draw_completed = (
            latest_round.draw_completed if latest_round is not None else False
        )
        gear_use_count = latest_round.gear_use_count if latest_round is not None else 0

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

        equipped_uuids: Set[str] = set()
        for entity in entities_map.values():
            equipped_data = find_component_data(entity, EquippedGearComponent.__name__)
            if equipped_data is not None:
                equipped_uuids.add(EquippedGearComponent(**equipped_data).item.uuid)

        self._snapshot = _GearSnapshot(
            stage_name=stage_name,
            entities_map=entities_map,
            entities_serialization=entities_resp.entities_serialization,
            player_name=actor_name,
            current_actor=current_actor,
            current_actor_is_player=current_actor_is_player,
            draw_completed=draw_completed,
            gear_use_count=gear_use_count,
            gear_items=gear_items,
            equipped_uuids=equipped_uuids,
        )
        return True, ""

    ########################################################################################################################
    async def _load_base_info_impl(self, clear: bool = True) -> None:
        """重新拉取最新数据并渲染装备使用状态 + 场景内角色摘要 + 我方装备列表。

        clear=True（初次进入 / 清屏）：先清空 RichLog 再整体重写；clear=False
        （使用结果反馈之后）：不清空，只在已展示的结果之后追加最新信息。
        加载完成后会把 `self._flow` 重置为新实例（回到 "menu" 步骤）。
        """
        log = self.query_one(RichLog)
        if clear:
            log.clear()
            log.write(BASE_INFO_HEADER)
        logger.info(f"CombatUseGearScreen._load_base_info_impl: 开始加载 clear={clear}")

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
        player_turn_label = (
            "[green]是[/]" if self._snapshot.current_actor_is_player else "[red]否[/]"
        )
        draw_label = (
            "[green]是[/]" if self._snapshot.draw_completed else "[yellow]否[/]"
        )

        log.write("[bold yellow]── 装备使用状态 ─────────────────────────────[/]")
        log.write(
            f"  当前 turn 角色： [bold yellow]{current_actor_label}[/]"
            f"（玩家本人：{player_turn_label}）"
        )
        log.write(f"  抽牌已完成：     {draw_label}")
        log.write(
            f"  本回合已使用：   [bold]{self._snapshot.gear_use_count}[/] 次（无次数上限）"
        )
        log.write("")

        render_stage_actors(
            log, self._snapshot.stage_name, self._snapshot.entities_serialization
        )

        log.write("[bold yellow]── 我方装备 ─────────────────────────────[/]")
        if not self._snapshot.gear_items:
            log.write("  [dim]（背包中没有装备）[/]")
        else:
            for i, item in enumerate(self._snapshot.gear_items, start=1):
                _write_indexed_gear(log, i, item, self._snapshot.equipped_uuids)
        log.write("")

        self._flow = _GearFlowState()
        log.write(COMMANDS_MENU_TEMPLATE)

    ########################################################################################################################
    @on(Input.Submitted, "#combat-use-gear-input")
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
        if not self._snapshot.current_actor_is_player:
            log.write("[yellow]当前不是玩家本人回合，暂时无法使用装备。[/]")
            return
        if not self._snapshot.gear_items:
            log.write("[yellow]背包中没有可用的装备。[/]")
            return

        log.write("[bold yellow]── 选择装备 ─────────────────────────────────[/]")
        for i, item in enumerate(self._snapshot.gear_items, start=1):
            _write_indexed_gear(log, i, item, self._snapshot.equipped_uuids)
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
        if item.uuid in self._snapshot.equipped_uuids:
            log.write(
                f"[red]『{item.name}』当前已被装备中，无法再次使用，请重新选择，或输入 0 取消。[/]"
            )
            return

        self._flow.selected_item = item
        self._enter_select_target(log)

    ########################################################################################################################
    def _enter_select_target(self, log: RichLog) -> None:
        item = self._flow.selected_item
        assert item is not None

        candidates = [
            (name, entity)
            for name, entity in self._snapshot.entities_map.items()
            if classify_faction(entity) == "party" and is_alive(entity)
        ]

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
        assert len(self._flow.pending_targets) == 1, "装备要求恰好 1 个目标"

        target_name = self._flow.pending_targets[0]
        target_entity = self._snapshot.entities_map.get(target_name)
        if target_entity is None:
            log.write(
                f"[red]找不到目标『{display_name(target_name)}』，使用已取消，返回菜单。[/]"
            )
            self._back_to_menu(log)
            return

        effective_stats = compute_effective_stats_for(target_entity)
        current_energy = resolve_current_energy(target_entity, effective_stats)
        if current_energy < item.cost:
            log.write(
                f"[red]目标『{display_name(target_name)}』本回合能量不足"
                f"（需要{item.cost}，剩余{current_energy}），无法为其装备，使用已取消，返回菜单。[/]"
            )
            self._back_to_menu(log)
            return

        log.write("[bold yellow]── 确认使用 ─────────────────────────────────[/]")
        log.write(render_item(item))
        log.write(f"  目标： {display_name(target_name)}")
        log.write(f"  费用： 消耗目标 {item.cost} 点 energy")
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

        self._confirm_and_use_gear()

    ########################################################################################################################
    async def _finish_use_flow(self, inp: Input) -> None:
        """使用流程结束（成功 / 失败 / 中途异常）后的收尾：静默重新拉取最新数据
        替换 `self._snapshot`（不写日志、不追加任何信息），重置 `self._flow` 并重新
        启用输入框，交由玩家自行按 Escape 返回或输入 2 清屏刷新。"""
        ok, err = await self._fetch_state()
        if not ok:
            logger.warning(
                f"CombatUseGearScreen._finish_use_flow: 静默刷新缓存失败（{err}），"
                "建议手动输入 2 清屏重试"
            )
        self._flow = _GearFlowState()
        inp.disabled = False
        inp.focus()

    ########################################################################################################################
    @work
    async def _confirm_and_use_gear(self) -> None:
        """提交使用装备请求并等待后台任务完成，展示本回合新增的 gear_combat_log /
        gear_narrative 作为使用结果。结果展示完毕后不再自动刷新，交由玩家自行按
        Escape 返回或输入 2 清屏。"""
        log = self.query_one(RichLog)
        item = self._flow.selected_item
        assert item is not None, "_confirm_and_use_gear: 未选择装备"
        assert (
            len(self._flow.pending_targets) == 1
        ), "_confirm_and_use_gear: 目标数量应恰为 1"
        targets = list(self._flow.pending_targets)
        target_label = display_name(targets[0])

        inp = self.query_one(Input)
        inp.disabled = True

        log.write(f"[dim]▶ 正在使用：{item.name} → {target_label} ...[/]")

        if is_mock_mode(self.game_client):
            logger.info(
                "CombatUseGearScreen._confirm_and_use_gear: mock 模式，模拟使用结果"
            )
            log.write(
                "[bold yellow]\\[mock][/] 已模拟提交使用装备请求（未调用真实接口）。"
            )
            log.write("[bold green]✅ 使用完成[/]")
            log.write("[bold yellow]── 使用结果 ─────────────────────────────────[/]")
            log.write(f"  [dim]战斗：[/] 为 {target_label} 装备了『{item.name}』。")
            log.write(
                f"  [dim]叙事：[/] {target_label}握紧『{item.name}』，感受到一股全新的力量。"
            )
            log.write("")
            await self._finish_use_flow(inp)
            return

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)

            # 使用前先重新 GET 一次，记录当前回合装备日志/叙事的基线长度，
            # 便于使用完成后精确 diff 出本次新增的条目。
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

            resp = await dungeon_combat_use_gear(
                user_name, game_name, item.name, targets
            )
            log.write(f"[dim]任务已提交：{resp.task_id}，等待完成...[/]")
            await watch_task_until_done(resp.task_id)
        except TaskFailedError as e:
            logger.error(
                f"CombatUseGearScreen._confirm_and_use_gear: 使用任务失败 error={e}"
            )
            log.write(f"[bold red]❌ 使用失败：{e}[/]")
            log.write("")
            await self._finish_use_flow(inp)
            return
        except Exception as e:
            logger.error(
                f"CombatUseGearScreen._confirm_and_use_gear: 使用请求失败 error={e}"
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
                f"CombatUseGearScreen._confirm_and_use_gear: 加载使用结果失败 error={e}"
            )
            log.write(f"[bold red]❌ 加载使用结果失败：{e}[/]")
            log.write("")
            await self._finish_use_flow(inp)
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

        await self._finish_use_flow(inp)
