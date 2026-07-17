"""战斗出牌 Screen（CombatPlayCardsScreen）"""

from dataclasses import dataclass, field
from itertools import zip_longest
from typing import Dict, List, Optional, Tuple, final

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from ..models import (
    Card,
    CombatRoom,
    DeathComponent,
    EntitySerialization,
    HandComponent,
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
    dungeon_combat_play_cards,
    watch_task_until_done,
)
from .utils import display_name, render_card, render_status_effect

BASE_INFO_HEADER = """\
[bold cyan]── 出牌 ──────────────────────────────────────[/]

[dim]显示当前 turn 角色的属性 / 手牌 / 状态效果，选择手牌与目标后确认出牌。[/]
"""

COMMANDS_MENU_TEMPLATE = """\
[bold yellow]── 可用操作 ─────────[/]
  [bold green]1[/]  {current_actor_label} 出牌
  [bold green]2[/]  清屏（刷新基础信息 + 清除历史信息）"""


###############################################################################################################################################
@dataclass
class _CombatSnapshot:
    """出牌页从服务器拉取到的战斗快照缓存。"""

    stage_name: Optional[str] = None
    entities_map: Dict[str, EntitySerialization] = field(default_factory=dict)
    entities_serialization: List[EntitySerialization] = field(default_factory=list)
    current_actor: Optional[str] = None
    current_actor_energy: int = 0
    hand_cards: List[Card] = field(default_factory=list)


###############################################################################################################################################
@dataclass
class _PlayFlowState:
    """出牌多步交互（选择手牌 → 选择目标 → 确认）的临时状态。"""

    step: str = "menu"
    selected_card: Optional[Card] = None
    pending_targets: List[str] = field(default_factory=list)
    target_candidates: List[Tuple[str, EntitySerialization]] = field(
        default_factory=list
    )


###############################################################################################################################################
def _write_indexed_card(log: RichLog, index: int, card: Card) -> None:
    """渲染单张卡牌，并将编号与卡牌名写在同一行（而非单独一行编号后换行），
    避免编号与内容断行显得突兀。"""
    lines = render_card(card).split("\n")
    if lines:
        lines[0] = f"  [bold green]{index}[/] {lines[0].strip()}"
    for line in lines:
        log.write(line)


@final
class CombatPlayCardsScreen(BaseGameScreen):
    """战斗 ONGOING 阶段、抽牌已完成后的出牌页面：展示当前 turn 角色 + 场景内角色
    有效属性，并提供出牌 / 清屏指令入口。
    """

    CSS = """
    CombatPlayCardsScreen {
        align: center middle;
    }

    #combat-play-cards-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #combat-play-cards-input-row {
        height: 3;
        dock: bottom;
    }

    #combat-play-cards-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #combat-play-cards-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._snapshot = _CombatSnapshot()
        self._flow = _PlayFlowState()

    def compose(self) -> ComposeResult:
        yield RichLog(
            id="combat-play-cards-log", highlight=True, markup=True, wrap=True
        )
        with Horizontal(id="combat-play-cards-input-row"):
            yield Static("> ", id="combat-play-cards-prompt")
            yield Input(placeholder="输入指令编号...", id="combat-play-cards-input")

    def on_mount(self) -> None:
        self._load_base_info()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    ########################################################################################################################
    def _render_menu_text(self) -> str:
        current_actor_label = (
            display_name(self._snapshot.current_actor)
            if self._snapshot.current_actor
            else "（无）"
        )
        return COMMANDS_MENU_TEMPLATE.format(current_actor_label=current_actor_label)

    ########################################################################################################################
    def _write_actor_detail(
        self, log: RichLog, entity: EntitySerialization, index_label: str = ""
    ) -> None:
        """渲染单个角色的有效属性 + 状态效果 + 手牌完整详情。

        index_label: 非空时与角色名写在同一行前面（如目标候选列表的编号）。
        """
        effective_stats = compute_effective_stats_for(entity)
        if effective_stats is None:
            log.write(
                f"  {index_label}[yellow]{display_name(entity.name)} 缺少属性组件，跳过[/]"
            )
            return

        status_data = find_component_data(entity, StatusEffectsComponent.__name__)
        hand_data = find_component_data(entity, HandComponent.__name__)

        status_comp = (
            StatusEffectsComponent(**status_data) if status_data is not None else None
        )
        hand_comp = HandComponent(**hand_data) if hand_data is not None else None
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

        if hand_comp is not None and hand_comp.cards:
            log.write(f"    手牌（{len(hand_comp.cards)}）：")
            for card in hand_comp.cards:
                log.write(render_card(card))
        else:
            log.write("    手牌： [dim]（无）[/]")

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

        出牌会改变场景内任意实体（含自身）的属性/状态/手牌，因此绝不能复用旧
        快照；本方法是 `_snapshot` 的唯一写入点。
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
            msg = f"加载出牌基础信息失败：{e}"
            logger.error(f"CombatPlayCardsScreen._fetch_state: {msg}")
            return False, msg

        entities_map = {
            e.name: e
            for e in entities_resp.entities_serialization
            if e.name != stage_name
        }

        latest_round = combat.latest_round
        current_actor = latest_round.current_actor if latest_round is not None else None
        current_entity = entities_map.get(current_actor) if current_actor else None
        hand_data = (
            find_component_data(current_entity, HandComponent.__name__)
            if current_entity is not None
            else None
        )
        hand_cards = HandComponent(**hand_data).cards if hand_data is not None else []
        effective_stats = (
            compute_effective_stats_for(current_entity)
            if current_entity is not None
            else None
        )
        current_actor_energy = (
            resolve_current_energy(current_entity, effective_stats)
            if current_entity is not None
            else 0
        )

        self._snapshot = _CombatSnapshot(
            stage_name=stage_name,
            entities_map=entities_map,
            entities_serialization=entities_resp.entities_serialization,
            current_actor=current_actor,
            current_actor_energy=current_actor_energy,
            hand_cards=hand_cards,
        )
        return True, ""

    ########################################################################################################################
    async def _load_base_info_impl(self, clear: bool = True) -> None:
        """重新拉取最新数据并渲染当前 turn 角色详情 + 场景内角色摘要。

        clear=True（初次进入 / 清屏）：先清空 RichLog 再整体重写；clear=False
        （出牌结果反馈之后）：不清空，只在已展示的结果之后追加最新信息。
        加载完成后会把 `self._flow` 重置为新实例（回到 "menu" 步骤）。
        """
        log = self.query_one(RichLog)
        if clear:
            log.clear()
            log.write(BASE_INFO_HEADER)
        logger.info(
            f"CombatPlayCardsScreen._load_base_info_impl: 开始加载 clear={clear}"
        )

        ok, err = await self._fetch_state()
        if not ok:
            log.write(f"[bold red]❌ {err}[/]")
            return

        assert self._snapshot.stage_name is not None
        current_entity = (
            self._snapshot.entities_map.get(self._snapshot.current_actor)
            if self._snapshot.current_actor
            else None
        )

        log.write("[bold yellow]── 当前 turn ─────────────────────────────────[/]")
        if current_entity is not None:
            self._write_actor_detail(log, current_entity)
        else:
            log.write("  [dim]（无当前出牌角色）[/]")
        log.write("")

        render_stage_actors(
            log, self._snapshot.stage_name, self._snapshot.entities_serialization
        )

        self._flow = _PlayFlowState()
        log.write(self._render_menu_text())

    ########################################################################################################################
    @on(Input.Submitted, "#combat-play-cards-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        if not raw:
            return
        self._dispatch_command(raw)

    ########################################################################################################################
    def _dispatch_command(self, raw: str) -> None:
        """按当前所处步骤（menu / select_card / select_target / confirm）分发输入。"""
        if self._flow.step == "menu":
            self._handle_menu_command(raw)
        elif self._flow.step == "select_card":
            self._handle_select_card_command(raw)
        elif self._flow.step == "select_target":
            self._handle_select_target_command(raw)
        elif self._flow.step == "confirm":
            self._handle_confirm_command(raw)

    ########################################################################################################################
    def _back_to_menu(self, log: RichLog) -> None:
        self._flow = _PlayFlowState()
        log.write(self._render_menu_text())

    ########################################################################################################################
    def _handle_menu_command(self, raw: str) -> None:
        log = self.query_one(RichLog)
        if raw == "1":
            self._enter_select_card(log)
        elif raw == "2":
            self._load_base_info(clear=True)
        else:
            log.write("[red]无效指令，请输入 1 或 2[/]")

    ########################################################################################################################
    def _enter_select_card(self, log: RichLog) -> None:
        if not self._snapshot.current_actor:
            log.write("[yellow]当前没有可出牌的角色。[/]")
            return
        if not self._snapshot.hand_cards:
            log.write(
                f"[yellow]{display_name(self._snapshot.current_actor)} 当前手牌为空，无法出牌。[/]"
            )
            return

        log.write("[bold yellow]── 选择手牌 ─────────────────────────────────[/]")
        for i, card in enumerate(self._snapshot.hand_cards, start=1):
            _write_indexed_card(log, i, card)
        log.write("")
        log.write("[dim]输入编号选择要打出的卡牌；输入 0 取消，返回菜单。[/]")
        self._flow.step = "select_card"

    ########################################################################################################################
    def _handle_select_card_command(self, raw: str) -> None:
        log = self.query_one(RichLog)
        if raw == "0":
            log.write("[dim]已取消出牌，返回菜单。[/]")
            self._back_to_menu(log)
            return
        if not raw.isdigit():
            log.write("[red]请输入手牌编号，或输入 0 取消。[/]")
            return

        idx = int(raw)
        hand_cards = self._snapshot.hand_cards
        if idx < 1 or idx > len(hand_cards):
            log.write(
                f"[red]编号超出范围（1-{len(hand_cards)}），请重新输入，或输入 0 取消。[/]"
            )
            return

        card = hand_cards[idx - 1]
        if not card.playable:
            log.write(f"[red]『{card.name}』不可出牌，请重新选择，或输入 0 取消。[/]")
            return
        if self._snapshot.current_actor_energy < card.cost:
            log.write(
                f"[red]能量不足，无法出牌『{card.name}』（需要{card.cost}点，"
                f"当前剩余{self._snapshot.current_actor_energy}点），请重新选择，或输入 0 取消。[/]"
            )
            return

        self._flow.selected_card = card
        self._enter_select_target(log)

    ########################################################################################################################
    def _enter_select_target(self, log: RichLog) -> None:
        card = self._flow.selected_card
        assert card is not None

        current_actor = self._snapshot.current_actor
        actor_entity = (
            self._snapshot.entities_map.get(current_actor) if current_actor else None
        )
        actor_faction = classify_faction(actor_entity)

        if card.target_type == TargetType.SELF_ONLY:
            self._flow.pending_targets = [current_actor] if current_actor else []
            self._enter_confirm(log)
            return

        if card.target_type in (TargetType.ENEMY_ALL, TargetType.ENEMY_RANDOM_MULTI):
            # 由服务端按 target_type 自动解析目标，客户端传空列表即可。
            self._flow.pending_targets = []
            self._enter_confirm(log)
            return

        if card.target_type == TargetType.ALLY_ALL:
            self._flow.pending_targets = [
                name
                for name, entity in self._snapshot.entities_map.items()
                if name != current_actor
                and classify_faction(entity) == actor_faction
                and is_alive(entity)
            ]
            self._enter_confirm(log)
            return

        if card.target_type == TargetType.ENEMY_SINGLE:
            candidates = [
                (name, entity)
                for name, entity in self._snapshot.entities_map.items()
                if classify_faction(entity) not in ("unknown", actor_faction)
                and is_alive(entity)
            ]
        elif card.target_type == TargetType.ALLY_SINGLE:
            candidates = [
                (name, entity)
                for name, entity in self._snapshot.entities_map.items()
                if name != current_actor
                and classify_faction(entity) == actor_faction
                and is_alive(entity)
            ]
        else:
            # TargetType.CARD 等暂不在本页支持选择目标，直接以空目标出牌，交由服务端处理。
            log.write(
                f"[yellow]目标类型 {card.target_type.value} 暂不支持在本页选择目标，出牌时将不指定目标。[/]"
            )
            self._flow.pending_targets = []
            self._enter_confirm(log)
            return

        if not candidates:
            log.write("[red]当前没有可选的目标，出牌已取消，返回菜单。[/]")
            self._back_to_menu(log)
            return

        self._flow.target_candidates = candidates
        log.write("[bold yellow]── 选择目标 ─────────────────────────────────[/]")
        log.write(render_card(card))
        log.write("")
        for i, (_, entity) in enumerate(candidates, start=1):
            log.write("[dim]────────────────────────────[/]")
            self._write_actor_detail(log, entity, index_label=f"[bold green]{i}[/] ")

        log.write("")
        log.write("[dim]输入编号选择目标；输入 0 取消，返回菜单。[/]")
        self._flow.step = "select_target"

    ########################################################################################################################
    def _handle_select_target_command(self, raw: str) -> None:
        log = self.query_one(RichLog)
        if raw == "0":
            log.write("[dim]已取消出牌，返回菜单。[/]")
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
        card = self._flow.selected_card
        assert card is not None

        targets_label = (
            "、".join(display_name(t) for t in self._flow.pending_targets)
            if self._flow.pending_targets
            else "（由服务端自动指定）"
        )

        log.write("[bold yellow]── 确认出牌 ─────────────────────────────────[/]")
        log.write(render_card(card))
        log.write(f"  目标： {targets_label}")
        log.write("")
        log.write("  [bold green]1[/]  确认出牌")
        log.write("  [bold green]0[/]  取消，返回菜单")
        self._flow.step = "confirm"

    ########################################################################################################################
    def _handle_confirm_command(self, raw: str) -> None:
        log = self.query_one(RichLog)
        if raw == "0":
            log.write("[dim]已取消出牌，返回菜单。[/]")
            self._back_to_menu(log)
            return
        if raw != "1":
            log.write("[red]请输入 1 确认出牌，或输入 0 取消。[/]")
            return

        self._confirm_and_play()

    ########################################################################################################################
    async def _finish_play_flow(self, inp: Input) -> None:
        """出牌流程结束（成功 / 失败 / 中途异常）后的收尾：静默重新拉取最新数据
        替换 `self._snapshot`（不写日志、不追加任何信息），重置 `self._flow` 并重新
        启用输入框，交由玩家自行按 Escape 返回或输入 2 清屏刷新。"""
        ok, err = await self._fetch_state()
        if not ok:
            logger.warning(
                f"CombatPlayCardsScreen._finish_play_flow: 静默刷新缓存失败（{err}），"
                "建议手动输入 2 清屏重试"
            )
        self._flow = _PlayFlowState()
        inp.disabled = False
        inp.focus()

    ########################################################################################################################
    @work
    async def _confirm_and_play(self) -> None:
        """提交出牌请求并等待后台任务完成，展示本回合新增的 cards_combat_log /
        cards_narrative 作为出牌结果。结果展示完毕后不再自动刷新，交由玩家自行按
        Escape 返回或输入 2 清屏。"""
        log = self.query_one(RichLog)
        card = self._flow.selected_card
        actor_name = self._snapshot.current_actor
        assert card is not None, "_confirm_and_play: 未选择卡牌"
        assert actor_name is not None, "_confirm_and_play: 当前无出牌角色"
        targets = list(self._flow.pending_targets)

        inp = self.query_one(Input)
        inp.disabled = True

        targets_label = (
            "、".join(display_name(t) for t in targets) if targets else "（自动目标）"
        )
        log.write(f"[dim]▶ 正在出牌：{card.name} → {targets_label} ...[/]")

        if is_mock_mode(self.game_client):
            logger.info(
                "CombatPlayCardsScreen._confirm_and_play: mock 模式，模拟出牌结果"
            )
            log.write("[bold yellow]\\[mock][/] 已模拟提交出牌请求（未调用真实接口）。")
            log.write("[bold green]✅ 出牌完成[/]")
            log.write("[bold yellow]── 出牌结果 ─────────────────────────────────[/]")
            log.write(
                f"  [dim]战斗：[/] {actor_name} 使用『{card.name}』对 "
                f"{targets_label} 造成 {card.damage_dealt} 点伤害。"
            )
            log.write(
                f"  [dim]叙事：[/] {display_name(actor_name)}挥出『{card.name}』，一击命中！"
            )
            log.write("")
            await self._finish_play_flow(inp)
            return

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)

            # 出牌前先重新 GET 一次，记录当前回合出牌日志/叙事的基线长度，
            # 便于出牌完成后精确 diff 出本次新增的条目。
            baseline_room_resp = await get_dungeon_room(self.game_client)
            baseline_room = baseline_room_resp.room
            assert isinstance(baseline_room, CombatRoom)
            baseline_round = baseline_room.combat.latest_round
            baseline_log_count = (
                len(baseline_round.cards_combat_log) if baseline_round else 0
            )
            baseline_narrative_count = (
                len(baseline_round.cards_narrative) if baseline_round else 0
            )

            resp = await dungeon_combat_play_cards(
                user_name, game_name, actor_name, card.name, targets
            )
            log.write(f"[dim]任务已提交：{resp.task_id}，等待完成...[/]")
            await watch_task_until_done(resp.task_id)
        except TaskFailedError as e:
            logger.error(
                f"CombatPlayCardsScreen._confirm_and_play: 出牌任务失败 error={e}"
            )
            log.write(f"[bold red]❌ 出牌失败：{e}[/]")
            log.write("")
            await self._finish_play_flow(inp)
            return
        except Exception as e:
            logger.error(
                f"CombatPlayCardsScreen._confirm_and_play: 出牌请求失败 error={e}"
            )
            log.write(f"[bold red]❌ 出牌请求失败：{e}[/]")
            log.write("")
            await self._finish_play_flow(inp)
            return

        log.write("[bold green]✅ 出牌完成[/]")

        try:
            result_room_resp = await get_dungeon_room(self.game_client)
            result_room = result_room_resp.room
            assert isinstance(result_room, CombatRoom)
            latest_round = result_room.combat.latest_round
        except Exception as e:
            logger.error(
                f"CombatPlayCardsScreen._confirm_and_play: 加载出牌结果失败 error={e}"
            )
            log.write(f"[bold red]❌ 加载出牌结果失败：{e}[/]")
            log.write("")
            await self._finish_play_flow(inp)
            return

        if latest_round is not None:
            new_logs = latest_round.cards_combat_log[baseline_log_count:]
            new_narratives = latest_round.cards_narrative[baseline_narrative_count:]
            if new_logs or new_narratives:
                log.write(
                    "[bold yellow]── 出牌结果 ─────────────────────────────────[/]"
                )
                for combat_log, narrative in zip_longest(new_logs, new_narratives):
                    log.write(f"  [dim]战斗：[/] {combat_log or '[dim]（无）[/]'}")
                    log.write(f"  [dim]叙事：[/] {narrative or '[dim]（无）[/]'}")
        log.write("")

        await self._finish_play_flow(inp)
