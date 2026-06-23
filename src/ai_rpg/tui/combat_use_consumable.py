"""消耗品流程状态机 Mixin（UseConsumableMixin）。"""

from typing import List, Optional
import httpx
from loguru import logger
from textual import work
from textual.widgets import Input, RichLog
from .combat_use_item import UseItemMixin, _Phase as _Phase
from .server_client import dungeon_combat_use_consumable as server_use_consumable
from .server_client import (
    fetch_dungeon_room,
    fetch_entities_details,
    fetch_stages_state,
    watch_task_until_done,
    TaskFailedError,
)
from ..models import (
    CombatState,
    ConsumableItem,
    InventoryComponent,
    PartyMemberComponent,
    PlayerComponent,
    EntitySerialization,
)
from ..models.target_type import TargetType
from .utils import display_name, render_item


# ─────────────────────────────────────────────────────────────────
def _find_player_consumables(
    entities: List[EntitySerialization],
) -> List[ConsumableItem]:
    """从实体列表中找到 Player 实体并返回其背包中所有消耗品。"""
    for entity in entities:
        if any(c.name == PlayerComponent.__name__ for c in entity.components):
            for comp in entity.components:
                if comp.name == InventoryComponent.__name__:
                    inventory = InventoryComponent(**comp.data)
                    return [
                        item
                        for item in inventory.items
                        if isinstance(item, ConsumableItem)
                    ]
            return []  # 找到 Player 但无 InventoryComponent
    return []  # 未找到 Player


# ─────────────────────────────────────────────────────────────────


class UseConsumableMixin(UseItemMixin):
    """消耗品流程状态机。

    继承 UseItemMixin（→ BaseGameScreen）。
    与 UseGearMixin 平级，均由 PlayCardsMixin 多继承组合。
    """

    # 消耗品流程专用状态
    _consumable_items: List[ConsumableItem]
    _selected_item_name: Optional[str]
    _round_consumable_use_count: int  # 加载背包时快照的本回合使用次数，供选择阶段守卫

    def _init_item_state(self) -> None:
        """初始化消耗品专用状态，并向上链式初始化装备与共享状态。"""
        super()._init_item_state()
        self._consumable_items: List[ConsumableItem] = []
        self._selected_item_name: Optional[str] = None
        self._round_consumable_use_count: int = 0

    # ══════════════════════════════════════════════
    # 结果文本收集
    # ══════════════════════════════════════════════

    async def _collect_consumable_result_text(
        self, prev_round_idx: int, prev_consumable_use_count: int
    ) -> str:
        """获取本次消耗品使用后新增的叙事与战斗日志，返回格式化字符串（供 hint 拼接）。"""
        if prev_round_idx < 0:
            return ""
        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            rounds = room_resp.room.combat.rounds
            if prev_round_idx >= len(rounds):
                return ""
            cur = rounds[prev_round_idx]
            lines: List[str] = []
            for text in cur.consumable_narrative[prev_consumable_use_count:]:
                if text:
                    lines.append(f"  [italic]{text}[/]")
            for text in cur.consumable_combat_log[prev_consumable_use_count:]:
                if text:
                    lines.append(f"  [dim cyan]{text}[/]")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"_collect_consumable_result_text: 加载日志失败 error={e}")
            return ""

    # ══════════════════════════════════════════════
    # 消耗品流程入口
    # ══════════════════════════════════════════════

    def _start_use_consumable(self) -> None:
        """命令 4 入口：清屏并拉取玩家背包，展示消耗品列表，等待用户选择。"""
        log = self._clear_to_play_area("[bold yellow]── 使用消耗品 ──[/]")
        log.write("[dim]正在加载背包...[/]")
        self._phase = _Phase.LOADING
        self.query_one(Input).disabled = True
        self._load_consumables_for_player()

    @work
    async def _load_consumables_for_player(self) -> None:
        """拉取当前玩家实体的背包，展示消耗品列表，进入 SELECT_CONSUMABLE 阶段。"""
        log = self.query_one(RichLog)
        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            combat = room_resp.room.combat
            combat_state = combat.state

            if combat_state in (CombatState.NONE, CombatState.INITIALIZATION):
                self._return_to_menu("[yellow]⚠ 战斗尚未开始，无法使用消耗品。[/]")
                return

            if combat_state in (CombatState.COMPLETE, CombatState.POST_COMBAT):
                self._return_to_menu("[yellow]⚠ 战斗已结束，无法使用消耗品。[/]")
                return

            if not combat.rounds:
                self._return_to_menu(
                    "[yellow]⚠ 当前没有进行中的回合，请先输入 2 抽牌。[/]"
                )
                return

            latest_round = combat.rounds[-1]
            if not latest_round.draw_completed:
                self._return_to_menu("[yellow]⚠ 抽牌阶段尚未完成，请先输入 2 抽牌。[/]")
                return

            if latest_round.current_turn_actor_name is None:
                self._return_to_menu(
                    "[yellow]⚠ 本回合所有角色已出手，无法使用消耗品。[/]"
                )
                return

            stage_name = room_resp.room.stage.name
            stages_resp = await fetch_stages_state(self._user_name, self._game_name)
            actor_names: List[str] = list(stages_resp.mapping.get(stage_name, []))
            all_details = await fetch_entities_details(
                self._user_name, self._game_name, actor_names
            )

            current_actor = latest_round.current_turn_actor_name
            current_actor_is_party_member = any(
                e.name == current_actor
                and any(c.name == PartyMemberComponent.__name__ for c in e.components)
                for e in all_details.entities_serialization
            )
            if not current_actor_is_party_member:
                self._return_to_menu(
                    f"[yellow]⚠ 当前行动角色 {display_name(current_actor)} 不属于玩家阵营，无法使用消耗品。[/]"
                )
                return

            self._round_consumable_use_count = latest_round.consumable_use_count

            player_actor: Optional[str] = next(
                (
                    e.name
                    for e in all_details.entities_serialization
                    if any(c.name == PlayerComponent.__name__ for c in e.components)
                ),
                None,
            )
            consumables = _find_player_consumables(all_details.entities_serialization)

            if player_actor is None:
                self._return_to_menu("[red]❌ 未找到玩家角色。[/]")
                return

            if not consumables:
                self._return_to_menu("[yellow]背包中没有消耗品。[/]")
                return

            self._consumable_items = consumables
            log.write("")
            if self._round_consumable_use_count > 0:
                log.write(
                    f"[yellow]⚠ 本回合已使用消耗品 {self._round_consumable_use_count} 次（每回合限用一次，仅供浏览）[/]"
                )
                log.write("")
            for idx, item in enumerate(consumables, 1):
                rendered = render_item(item)
                first_nl = rendered.find("\n")
                if first_nl >= 0:
                    log.write(f"[bold cyan]{idx}.[/] {rendered[:first_nl]}")
                    log.write(rendered[first_nl + 1 :])
                else:
                    log.write(f"[bold cyan]{idx}.[/] {rendered}")
                log.write("")

            self._target_candidates = [item.name for item in consumables]
            self._phase = _Phase.SELECT_CONSUMABLE
            inp = self.query_one(Input)
            inp.placeholder = f"1-{len(consumables)} 或消耗品名 / q 返回"
            inp.disabled = False
            inp.focus()

        except Exception as e:
            logger.error(f"_load_consumables_for_player: 加载失败 error={e}")
            self._return_to_menu(f"[bold red]❌ 加载背包失败: {e}[/]")

    @work
    async def _handle_consumable_selection(self, raw: str) -> None:
        """用户输入消耗品编号/名称后处理：决定是否需要选择目标。"""
        log = self.query_one(RichLog)
        items: List[ConsumableItem] = self._consumable_items
        candidates: List[str] = self._target_candidates

        if self._round_consumable_use_count > 0:
            self._return_to_menu("[yellow]⚠ 本回合已使用过消耗品，每回合限用一次。[/]")
            return

        selected_item: Optional[ConsumableItem] = None
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(items):
                selected_item = items[idx]
        else:
            for item in items:
                if item.name == raw or display_name(item.name) == raw:
                    selected_item = item
                    break

        if selected_item is None:
            log.write(
                f"[red]无效输入 '{raw}'，请输入 1-{len(candidates)} 的数字或消耗品名称。[/]"
            )
            self._phase = _Phase.SELECT_CONSUMABLE
            inp = self.query_one(Input)
            inp.placeholder = f"1-{len(candidates)} 或消耗品名 / q 返回"
            inp.disabled = False
            inp.focus()
            return

        item_name = selected_item.name
        target_type = selected_item.target_type
        log.write(f"  已选：[bold cyan]{item_name}[/]")
        self._consumable_items = []
        self._target_candidates = []

        # ── 无需选择目标的类型：系统自动处理 ─────────────────────
        if target_type == TargetType.SELF_ONLY:
            log.write("  [dim]目标：自身（系统自动）[/]")
            self._do_use_consumable(item_name, [])
            return

        if target_type == TargetType.ENEMY_ALL:
            log.write("  [dim]目标：全体敌方（系统自动）[/]")
            self._do_use_consumable(item_name, [])
            return

        # ── 不支持的目标类型：报错并返回主菜单 ──────────────────
        if target_type not in (TargetType.ENEMY_SINGLE, TargetType.ALLY_SINGLE):
            log.write(
                f"[bold red]❌ 不支持的目标类型 '{target_type}'，无法使用此消耗品。[/]"
            )
            logger.error(
                f"_handle_consumable_selection: 不支持的目标类型 target_type={target_type} item={item_name}"
            )
            self._return_to_menu("[dim]已返回主菜单。[/]")
            return

        # ── 需要手动选择目标（ENEMY_SINGLE / ALLY_SINGLE）────────
        alive_enemies: List[str]
        alive_allies: List[str]
        try:
            alive_enemies, alive_allies = await self._fetch_alive_actors()
        except Exception as e:
            logger.warning(f"_handle_consumable_selection: 拉取目标列表失败 error={e}")
            log.write(f"[bold red]❌ 拉取目标列表失败: {e}[/]")
            self._return_to_menu("[dim]已返回主菜单。[/]")
            return

        if target_type == TargetType.ALLY_SINGLE:
            if not alive_allies:
                log.write("  [yellow]⚠ 无存活友方，无法使用。[/]")
                self._return_to_menu("[dim]已返回主菜单。[/]")
                return
            log.write("  [bold]可选友方目标：[/]")
            for i, name in enumerate(alive_allies, 1):
                log.write(f"    [bold cyan]{i}.[/] {display_name(name)}")
            self._selected_item_name = item_name
            self._target_candidates = list(alive_allies)
            self._phase = _Phase.SELECT_CONSUMABLE_TARGET
            inp = self.query_one(Input)
            inp.placeholder = f"1-{len(alive_allies)} 或目标名"
            inp.disabled = False
            inp.focus()

        else:  # ENEMY_SINGLE
            if not alive_enemies:
                log.write("  [yellow]⚠ 无存活敌人，无法使用。[/]")
                self._return_to_menu("[dim]已返回主菜单。[/]")
                return
            log.write("  [bold]可选敌方目标：[/]")
            for i, name in enumerate(alive_enemies, 1):
                log.write(f"    [bold cyan]{i}.[/] {display_name(name)}")
            self._selected_item_name = item_name
            self._target_candidates = list(alive_enemies)
            self._phase = _Phase.SELECT_CONSUMABLE_TARGET
            inp = self.query_one(Input)
            inp.placeholder = f"1-{len(alive_enemies)} 或目标名"
            inp.disabled = False
            inp.focus()

    def _handle_consumable_target_selection(self, raw: str) -> None:
        """用户输入消耗品目标编号后处理。"""
        log = self.query_one(RichLog)
        targets: List[str] = []

        if raw == "":
            log.write("  [dim]无目标[/]")
        else:
            candidates: List[str] = self._target_candidates
            if raw.isdigit():
                idx = int(raw) - 1
                if 0 <= idx < len(candidates):
                    targets = [candidates[idx]]
                else:
                    log.write(
                        f"[red]无效目标编号 '{raw}'，请输入 1-{len(candidates)} 或直接 Enter 跳过。[/]"
                    )
                    return
            else:
                matched = [n for n in candidates if n == raw or display_name(n) == raw]
                if matched:
                    targets = [matched[0]]
                else:
                    log.write(f"[red]找不到目标 '{raw}'，请重新输入。[/]")
                    return

        assert self._selected_item_name is not None
        item_name = self._selected_item_name
        self._selected_item_name = None
        self._target_candidates = []
        self._do_use_consumable(item_name, targets)

    @work
    async def _do_use_consumable(self, item_name: str, targets: List[str]) -> None:
        """后台提交使用消耗品任务，等待完成后展示结果并推进回合。"""
        log = self.query_one(RichLog)
        self._phase = _Phase.WAITING
        self.query_one(Input).disabled = True

        log.write(
            f"  [dim]▶ 使用消耗品：{item_name}  "
            f"目标：{[display_name(t) for t in targets] or '无'}[/]"
        )

        prev_round_idx = -1
        prev_consumable_use_count = 0
        try:
            pre_room = await fetch_dungeon_room(self._user_name, self._game_name)
            pre_rounds = pre_room.room.combat.rounds
            if pre_rounds:
                prev_round_idx = len(pre_rounds) - 1
                prev_consumable_use_count = pre_rounds[-1].consumable_use_count
        except Exception as e:
            logger.warning(f"_do_use_consumable: 使用前快照失败 error={e}")

        task_id = ""
        try:
            resp = await server_use_consumable(
                self._user_name, self._game_name, item_name, targets
            )
            task_id = resp.task_id
            logger.info(f"_do_use_consumable: 任务已创建 task_id={task_id}")
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            log.write(f"[bold red]❌ 使用消耗品请求失败: {detail}[/]")
            logger.error(f"_do_use_consumable: 请求失败 error={e}")
            self._return_to_menu("[dim]消耗品请求失败，已返回主菜单。[/]")
            return
        except Exception as e:
            log.write(f"[bold red]❌ 使用消耗品请求失败: {e}[/]")
            logger.error(f"_do_use_consumable: 请求失败 error={e}")
            self._return_to_menu("[dim]消耗品请求失败，已返回主菜单。[/]")
            return

        self._update_play_status("等待消耗品使用完成...")
        try:
            await watch_task_until_done(task_id, timeout_seconds=90)
            log.write("  [green]✓ 消耗品使用完成[/]")
            logger.info(f"_do_use_consumable: 任务完成 task_id={task_id}")
        except TaskFailedError as e:
            log.write(f"[bold red]❌ 消耗品使用失败: {e}[/]")
            logger.error(f"_do_use_consumable: 任务失败 task_id={task_id} error={e}")
        except TimeoutError:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(f"_do_use_consumable: 轮询超时 task_id={task_id}")
        except Exception as e:
            logger.warning(f"_do_use_consumable: 等待任务失败 error={e}")

        result_text = await self._collect_consumable_result_text(
            prev_round_idx, prev_consumable_use_count
        )
        used = prev_consumable_use_count + 1
        base_hint = (
            f"[dim]消耗品已使用（本回合第 {used} 次）。输入 [bold]3[/] 继续出牌。[/]"
        )
        hint = f"{result_text}\n{base_hint}" if result_text else base_hint
        self._return_to_menu(hint)
