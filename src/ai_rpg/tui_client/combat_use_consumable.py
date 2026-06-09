"""消耗品流程状态机 Mixin（UseConsumableMixin）。

此模块包含：
- _Phase 枚举：出牌/消耗品阶段状态机的所有状态（由 combat_play_cards 重新导出）
- UseConsumableMixin：消耗品流程的 5 个方法

UseConsumableMixin 是纯 Mixin，不继承任何基类。
宿主类需通过 MRO 提供：
  - self._user_name: str / self._game_name: str
  - self.query_one()  ← 由 Textual Widget 提供
  - self._abort_play_cards() / self._advance()
  - self._update_play_status() / self._show_play_results()
"""

from enum import auto, Enum
from typing import List, Optional
import httpx
from loguru import logger
from rich import box as rich_box
from rich.table import Table
from textual import work
from textual.widgets import Input, RichLog
from .server_client import dungeon_combat_use_consumable as server_use_consumable
from .server_client import (
    fetch_dungeon_room,
    fetch_entities_details,
    fetch_stages_state,
    watch_task_until_done,
    TaskFailedError,
)
from ..models import (
    ConsumableItem,
    InventoryComponent,
    MonsterComponent,
    PartyMemberComponent,
    PlayerComponent,
)
from .combat_room_renderer import TARGET_LABEL
from .utils import display_name


# ─────────────────────────────────────────────────
# 出牌/消耗品状态机枚举
# ─────────────────────────────────────────────────
class _Phase(Enum):
    LOADING = auto()  # 初始加载回合信息
    ENEMY_TURN = auto()  # 等待用户按 Enter 触发敌人 AI
    SELECT_CARD = auto()  # 等待用户输入卡牌编号（出牌）
    SELECT_TARGET = auto()  # 等待用户输入目标编号
    WAITING = auto()  # 正在等待后端任务完成
    ROUND_DONE = auto()  # 回合已全部完成
    SELECT_CONSUMABLE = auto()  # 等待用户输入消耗品编号
    SELECT_CONSUMABLE_TARGET = auto()  # 等待用户输入消耗品目标编号


class UseConsumableMixin:
    """消耗品流程状态机。

    宿主类（CombatRoomScreen）必须在 __init__ 中调用 self._init_play_state()。
    PlayCardsMixin 通过继承链提供缺失的状态字段和方法。
    """

    # 消耗品流程专用状态
    _consumable_actor: Optional[str]
    _selected_item_name: Optional[str]
    # 与出牌流程共享的状态（由 PlayCardsMixin._init_play_state 初始化）
    _phase: Optional[_Phase]
    _target_candidates: List[str]

    # ══════════════════════════════════════════════
    # 消耗品流程入口
    # ══════════════════════════════════════════════

    def _start_use_consumable(self) -> None:
        """命令 4 入口：拉取玩家背包并展示消耗品列表，等待用户选择。"""
        log = self.query_one(RichLog)  # type: ignore[attr-defined]
        log.clear()
        log.write("[bold yellow]── 使用消耗品 ──[/]")
        log.write("[dim]正在加载背包...[/]")
        self._phase = _Phase.LOADING
        self.query_one(Input).disabled = True  # type: ignore[attr-defined]
        self._load_consumables_for_player()

    @work
    async def _load_consumables_for_player(self) -> None:
        """拉取当前玩家实体的背包，展示消耗品列表，进入 SELECT_CONSUMABLE 阶段。"""
        log = self.query_one(RichLog)  # type: ignore[attr-defined]
        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)  # type: ignore[attr-defined]
            stage_name = room_resp.room.stage.name
            stages_resp = await fetch_stages_state(self._user_name, self._game_name)  # type: ignore[attr-defined]
            actor_names: List[str] = list(stages_resp.mapping.get(stage_name, []))

            all_details = await fetch_entities_details(
                self._user_name, self._game_name, actor_names  # type: ignore[attr-defined]
            )

            player_actor: Optional[str] = None
            consumables: List[ConsumableItem] = []
            for entity in all_details.entities_serialization:
                if any(c.name == PlayerComponent.__name__ for c in entity.components):
                    player_actor = entity.name
                    for comp in entity.components:
                        if comp.name == InventoryComponent.__name__:
                            inventory = InventoryComponent(**comp.data)
                            for item in inventory.items:
                                if isinstance(item, ConsumableItem):
                                    consumables.append(item)
                    break

            if player_actor is None:
                log.write("[red]未找到玩家角色。[/]")
                self._abort_play_cards()  # type: ignore[attr-defined]
                return

            self._consumable_actor = player_actor

            if not consumables:
                log.write("[yellow]背包中没有消耗品。[/]")
                self._abort_play_cards()  # type: ignore[attr-defined]
                return

            log.write(f"  [bold]背包消耗品（{display_name(player_actor)}）：[/]")
            item_table = Table(
                show_header=True,
                show_lines=True,
                box=rich_box.ROUNDED,
                padding=(0, 1),
                expand=True,
            )
            item_table.add_column("#", style="cyan", width=3, no_wrap=True)
            item_table.add_column("名称", style="bold", min_width=12, no_wrap=True)
            item_table.add_column("目标", width=12, no_wrap=True)
            item_table.add_column("词条 / 描述", ratio=1)
            for idx, item in enumerate(consumables, 1):
                tt_str = TARGET_LABEL.get(
                    item.target_type, f"[dim]{item.target_type}[/]"
                )
                desc_parts = []
                if item.affixes:
                    desc_parts.append("、".join(item.affixes))
                if item.modifiers:
                    desc_parts.append("[即时] " + "、".join(item.modifiers))
                desc = "  |  ".join(desc_parts) if desc_parts else "[dim](无描述)[/]"
                item_table.add_row(str(idx), item.name, tt_str, desc)
            log.write(item_table)

            self._target_candidates = [item.name for item in consumables]
            self._phase = _Phase.SELECT_CONSUMABLE
            inp = self.query_one(Input)  # type: ignore[attr-defined]
            inp.placeholder = f"1-{len(consumables)} 或消耗品名 / q 返回"
            inp.disabled = False
            inp.focus()

        except Exception as e:
            logger.error(f"_load_consumables_for_player: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载背包失败: {e}[/]")
            self._abort_play_cards()  # type: ignore[attr-defined]

    @work
    async def _handle_consumable_selection(self, raw: str) -> None:
        """用户输入消耗品编号/名称后处理：决定是否需要选择目标。"""
        log = self.query_one(RichLog)  # type: ignore[attr-defined]
        candidates: List[str] = self._target_candidates

        item_name: Optional[str] = None
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(candidates):
                item_name = candidates[idx]
        else:
            for name in candidates:
                if name == raw or display_name(name) == raw:
                    item_name = name
                    break

        if item_name is None:
            log.write(
                f"[red]无效输入 '{raw}'，请输入 1-{len(candidates)} 的数字或消耗品名称。[/]"
            )
            self._phase = _Phase.SELECT_CONSUMABLE
            inp = self.query_one(Input)  # type: ignore[attr-defined]
            inp.placeholder = f"1-{len(candidates)} 或消耗品名 / q 返回"
            inp.disabled = False
            inp.focus()
            return

        log.write(f"  已选：[bold cyan]{item_name}[/]")

        try:
            actor_name = self._consumable_actor
            assert actor_name is not None
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)  # type: ignore[attr-defined]
            stage_name = room_resp.room.stage.name
            stages_resp = await fetch_stages_state(self._user_name, self._game_name)  # type: ignore[attr-defined]
            actor_names: List[str] = list(stages_resp.mapping.get(stage_name, []))
            all_details = await fetch_entities_details(
                self._user_name, self._game_name, actor_names  # type: ignore[attr-defined]
            )

            target_type: str = "self_only"
            alive_enemies: List[str] = []
            alive_allies: List[str] = []
            for entity in all_details.entities_serialization:
                comp_names = {c.name for c in entity.components}
                if MonsterComponent.__name__ in comp_names:
                    alive_enemies.append(entity.name)
                elif PartyMemberComponent.__name__ in comp_names:
                    alive_allies.append(entity.name)
                if entity.name == actor_name:
                    for comp in entity.components:
                        if comp.name == InventoryComponent.__name__:
                            inventory = InventoryComponent(**comp.data)
                            for item in inventory.items:
                                if (
                                    isinstance(item, ConsumableItem)
                                    and item.name == item_name
                                ):
                                    target_type = item.target_type
        except Exception as e:
            logger.warning(
                f"_handle_consumable_selection: 拉取目标信息失败 error={e}, 使用 self_only"
            )
            target_type = "self_only"
            alive_enemies = []
            alive_allies = []
            actor_name = self._consumable_actor or ""

        self._target_candidates = []

        if target_type in ("self_only", "enemy_all", "ally_all", "enemy_random_multi"):
            label_map = {
                "self_only": "仅作用于自身",
                "enemy_all": "作用于所有存活敌方",
                "ally_all": "作用于所有存活友方",
                "enemy_random_multi": "随机命中敌方目标",
            }
            log.write(f"  [dim]此消耗品{label_map.get(target_type, target_type)}[/]")
            self._do_use_consumable(actor_name, item_name, [])

        elif target_type == "ally_single":
            if alive_allies:
                log.write("  [bold]可选友方目标：[/]")
                for i, name in enumerate(alive_allies, 1):
                    log.write(f"    [bold cyan]{i}.[/] {display_name(name)}")
                self._selected_item_name = item_name
                self._target_candidates = list(alive_allies)
                self._phase = _Phase.SELECT_CONSUMABLE_TARGET
                inp = self.query_one(Input)  # type: ignore[attr-defined]
                inp.placeholder = f"1-{len(alive_allies)} 或 Enter 跳过"
                inp.disabled = False
                inp.focus()
            else:
                log.write("  [dim]无存活友方，直接使用[/]")
                self._do_use_consumable(actor_name, item_name, [])

        else:  # enemy_single
            if alive_enemies:
                log.write("  [bold]可用目标：[/]")
                for i, name in enumerate(alive_enemies, 1):
                    log.write(f"    [bold cyan]{i}.[/] {display_name(name)}")
                self._selected_item_name = item_name
                self._target_candidates = list(alive_enemies)
                self._phase = _Phase.SELECT_CONSUMABLE_TARGET
                inp = self.query_one(Input)  # type: ignore[attr-defined]
                inp.placeholder = f"1-{len(alive_enemies)} 或 Enter 跳过"
                inp.disabled = False
                inp.focus()
            else:
                log.write("  [dim]无存活敌人，直接使用[/]")
                self._do_use_consumable(actor_name, item_name, [])

    def _handle_consumable_target_selection(self, raw: str) -> None:
        """用户输入消耗品目标编号后处理。"""
        log = self.query_one(RichLog)  # type: ignore[attr-defined]
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

        assert self._consumable_actor is not None
        assert self._selected_item_name is not None
        actor = self._consumable_actor
        item_name = self._selected_item_name
        self._selected_item_name = None
        self._target_candidates = []
        self._do_use_consumable(actor, item_name, targets)

    @work
    async def _do_use_consumable(
        self, actor_name: str, item_name: str, targets: List[str]
    ) -> None:
        """后台提交使用消耗品任务，等待完成后展示结果并推进回合。"""
        log = self.query_one(RichLog)  # type: ignore[attr-defined]
        self._phase = _Phase.WAITING
        self.query_one(Input).disabled = True  # type: ignore[attr-defined]

        short = display_name(actor_name)
        log.write(
            f"  [dim]▶ {short} 使用消耗品：{item_name}  "
            f"目标：{[display_name(t) for t in targets] or '无'}[/]"
        )

        prev_round_idx = -1
        prev_completed_count = 0
        try:
            pre_room = await fetch_dungeon_room(self._user_name, self._game_name)  # type: ignore[attr-defined]
            pre_rounds = pre_room.room.combat.rounds
            if pre_rounds:
                prev_round_idx = len(pre_rounds) - 1
                prev_completed_count = len(pre_rounds[-1].completed_actors)
        except Exception as e:
            logger.warning(f"_do_use_consumable: 使用前快照失败 error={e}")

        task_id = ""
        try:
            resp = await server_use_consumable(
                self._user_name, self._game_name, actor_name, item_name, targets  # type: ignore[attr-defined]
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
            self._advance()  # type: ignore[attr-defined]
            return
        except Exception as e:
            log.write(f"[bold red]❌ 使用消耗品请求失败: {e}[/]")
            logger.error(f"_do_use_consumable: 请求失败 error={e}")
            self._advance()  # type: ignore[attr-defined]
            return

        self._update_play_status(f"等待 {short} 使用消耗品完成...")  # type: ignore[attr-defined]
        try:
            await watch_task_until_done(task_id, timeout_seconds=90)
            log.write(f"  [green]✓ {short} 使用消耗品完成[/]")
            logger.info(f"_do_use_consumable: 任务完成 task_id={task_id}")
        except TaskFailedError as e:
            log.write(f"[bold red]❌ {short} 使用消耗品失败: {e}[/]")
            logger.error(f"_do_use_consumable: 任务失败 task_id={task_id} error={e}")
        except TimeoutError:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(f"_do_use_consumable: 轮询超时 task_id={task_id}")
        except Exception as e:
            logger.warning(f"_do_use_consumable: 等待任务失败 error={e}")

        await self._show_play_results(prev_round_idx, prev_completed_count)  # type: ignore[attr-defined]
        self._consumable_actor = None
        self._advance()  # type: ignore[attr-defined]
