"""战斗房间 Screen（CombatRoom）"""

from enum import auto, Enum
from typing import Dict, Final, List, Optional, final
import httpx
from loguru import logger
from rich import box as rich_box
from rich.table import Table
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Input, RichLog, Static
from .deck_detail import DeckDetailScreen
from .round_detail import RoundDetailScreen
from .utils import display_name
from .server_client import dungeon_combat_draw_cards as server_dungeon_combat_draw_cards
from .server_client import dungeon_combat_play_cards as server_play_cards
from .server_client import dungeon_combat_exhaust_card as server_exhaust_card
from .server_client import (
    dungeon_combat_use_consumable_item as server_use_consumable_item,
)
from .server_client import dungeon_combat_init as server_dungeon_combat_init
from .server_client import dungeon_combat_retreat as server_dungeon_combat_retreat
from .server_client import dungeon_exit as server_dungeon_exit
from .server_client import fetch_dungeon_room, fetch_dungeon_state
from .server_client import (
    fetch_entities_details,
    fetch_stages_state,
    watch_task_until_done,
    TaskFailedError,
)
from ..models import (
    Card,
    ConsumableItem,
    CombatResult,
    CombatState,
    EntitySerialization,
    EquipmentComponent,
    InventoryComponent,
    TargetType,
    CharacterStatsComponent,
    StatusEffectsComponent,
    DrawPileComponent,
    HandComponent,
    MonsterComponent,
    PartyMemberComponent,
    PlayerComponent,
)
from ..models.utils import compute_effective_stats


# ─────────────────────────────────────────────────
# 出牌状态机枚举
# ─────────────────────────────────────────────────
class _Phase(Enum):
    LOADING = auto()  # 初始加载回合信息
    ENEMY_TURN = auto()  # 等待用户按 Enter 触发敌人 AI
    SELECT_CARD = auto()  # 等待用户输入卡牌编号（出牌）
    SELECT_DISCARD_CARD = auto()  # 等待用户输入卡牌编号（弃牌）
    SELECT_TARGET = auto()  # 等待用户输入目标编号
    SELECT_CONSUMABLE_ITEM = auto()  # 等待用户选择消耗品编号
    SELECT_CONSUMABLE_TARGET = auto()  # 等待用户选择消耗品目标编号
    WAITING = auto()  # 正在等待后端任务完成
    ROUND_DONE = auto()  # 回合已全部完成


def _format_http_error(e: Exception) -> str:
    """从 httpx.HTTPStatusError 响应体提取 detail，否则返回 str(e)。"""
    if isinstance(e, httpx.HTTPStatusError):
        try:
            return str(e.response.json().get("detail", str(e)))
        except Exception:
            pass
    return str(e)


_TARGET_LABEL: Final[Dict[str, str]] = {
    "enemy_single": "[red]敌方单体[/]",
    "enemy_all": "[red]敌方全体[/]",
    "ally_single": "[green]友方单体[/]",
    "ally_all": "[green]友方全体[/]",
    "self_only": "[cyan]仅自己[/]",
}


COMBAT_ROOM_MENU: Final[
    str
] = """\
[bold yellow]可用操作（输入编号执行）：[/]

[bold cyan]── 战斗 ──────────────────────────────────────[/]
  [bold green]1[/]  战斗开始        执行战斗初始化（首次进入战斗时）
  [bold green]2[/]  抽牌            为全员抽牌
  [bold green]3[/]  出牌            进入出牌界面完成本回合
  [bold green]4[/]  弃牌            从手牌中弃置一张卡牌
  [bold green]5[/]  使用消耗品      从背包中取出并使用一件消耗道具

[bold cyan]── 查看 ──────────────────────────────────────[/]
  [bold green]6[/]  当前战斗状态    房间信息与角色属性
  [bold green]7[/]  回合详情        行动顺序与出手记录
  [bold green]8[/]  查阅牌组        本次地下城各角色历史牌组

[bold cyan]── 离场 ──────────────────────────────────────[/]
  [bold green]9[/]   撤退            在战斗进行中撤退
  [bold green]10[/]  退出战斗        战斗结束后返回游戏主场景

[bold cyan]── 系统 ──────────────────────────────────────[/]
  [bold green]0[/]  显示此菜单
  [bold dim]Escape[/]  提示退出方式

"""


@final
class CombatRoomScreen(Screen[None]):
    """战斗房间 Screen：进入地下城战斗房间后的主界面，支持战斗操作与状态查询。"""

    CSS = """
    #combat-status {
        dock: top;
        height: 3;
        padding: 0 1;
        background: $panel;
        border: solid $primary;
        color: $text;
        content-align: center middle;
    }

    #room-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #room-input-row {
        height: 3;
        dock: bottom;
    }

    #room-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #room-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "suggest_exit", "use 8 to quit"),
    ]

    def __init__(self) -> None:
        super().__init__()

        # 顶部状态栏文本缓存（由 _fetch_status 写入，其他地方只读不写）
        self._status_bar_text: str = "[bold cyan]战斗房间[/]  [dim]查询中...[/]"

        # 出牌阶段状态机字段（None = 普通命令模式）
        self._phase: Optional[_Phase] = None
        self._current_actor: Optional[str] = (
            None  # 当前出牌角色（ENEMY_TURN/SELECT_CARD/SELECT_TARGET）
        )
        self._selected_card_name: Optional[str] = (
            None  # 已选卡牌名（SELECT_TARGET 跨步骤）
        )
        self._target_candidates: List[str] = (
            []
        )  # 可选目标名列表（SELECT_TARGET 内有效，用完即清）
        self._discard_hand_cards: List[Card] = (
            []
        )  # 弃牌选牌阶段缓存的手牌（SELECT_DISCARD_CARD 内有效）
        self._consumable_candidates: List[ConsumableItem] = (
            []
        )  # 可用消耗品列表（SELECT_CONSUMABLE_ITEM 内有效）
        self._selected_consumable_name: Optional[str] = (
            None  # 已选消耗品名（SELECT_CONSUMABLE_TARGET 跨步骤）
        )

    @property
    def _user_name(self) -> str:
        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        assert app.session is not None
        return app.session.user_name

    @property
    def _game_name(self) -> str:
        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        assert app.session is not None
        return app.session.game_name

    def compose(self) -> ComposeResult:
        yield Static("", id="combat-status", markup=True)
        yield RichLog(id="room-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="room-input-row"):
            yield Static("> ", id="room-prompt")
            yield Input(placeholder="输入命令...", id="room-input")

    def on_mount(self) -> None:
        self.query_one("#combat-status", Static).update(self._status_bar_text)
        log = self.query_one(RichLog)
        log.write(COMBAT_ROOM_MENU)
        self._fetch_status()
        self.query_one(Input).focus()

    def action_suggest_exit(self) -> None:
        log = self.query_one(RichLog)
        log.write("[yellow]请输入 10 退出战斗（战斗结束后），或 9 撤退（战斗中）。[/]")

    @on(Input.Submitted, "#room-input")
    def handle_command(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        # ── 出牌模式：路由至状态机处理器 ──
        if self._phase is not None:
            # q / 退出 → 随时中断并回到主菜单（LOADING/WAITING 除外）
            if raw.lower() in ("q", "退出"):
                if self._phase in (
                    _Phase.ENEMY_TURN,
                    _Phase.SELECT_CARD,
                    _Phase.SELECT_TARGET,
                    _Phase.SELECT_CONSUMABLE_ITEM,
                    _Phase.SELECT_CONSUMABLE_TARGET,
                    _Phase.ROUND_DONE,
                ):
                    self._abort_play_cards()
                else:
                    log.write("[yellow]正在处理中，请稍候...[/]")
                return
            if self._phase == _Phase.ENEMY_TURN:
                # 立即锁定，防止重复触发
                self._phase = _Phase.WAITING
                self.query_one(Input).disabled = True
                self._trigger_enemy_turn()
            elif self._phase == _Phase.SELECT_CARD:
                # 立即锁定，防止重复提交（_handle_card_selection 是 @work async）
                self._phase = _Phase.LOADING
                self.query_one(Input).disabled = True
                self._handle_card_selection(raw)
            elif self._phase == _Phase.SELECT_DISCARD_CARD:
                self._handle_discard_card_selection(raw)
            elif self._phase == _Phase.SELECT_TARGET:
                self._handle_target_selection(raw)
            elif self._phase == _Phase.SELECT_CONSUMABLE_ITEM:
                self._phase = _Phase.LOADING
                self.query_one(Input).disabled = True
                self._handle_consumable_item_selection(raw)
            elif self._phase == _Phase.SELECT_CONSUMABLE_TARGET:
                self._handle_consumable_target_selection(raw)
            elif self._phase == _Phase.ROUND_DONE:
                self._confirm_round_done()
            return

        # ── 普通命令模式 ──
        cmd = raw
        if not cmd:
            return

        # 每次执行任意命令前先清空 Log 并重印菜单
        log.clear()
        log.write(COMBAT_ROOM_MENU)

        if cmd == "0":
            pass  # 仅显示菜单，已经显示

        elif cmd == "1":
            self._do_combat_start()

        elif cmd == "2":
            self._do_advance_combat()

        elif cmd == "3":
            self._start_play_cards()

        elif cmd == "4":
            self._start_discard_card()

        elif cmd == "5":
            self._start_use_consumable_item()

        elif cmd == "6":
            self._fetch_status()

        elif cmd == "7":
            self.app.push_screen(RoundDetailScreen())

        elif cmd == "8":
            self.app.push_screen(DeckDetailScreen())

        elif cmd == "9":
            self._do_combat_retreat()

        elif cmd == "10":
            self._do_exit()

        else:
            log.write(f"[red]未知输入：{cmd}，输入 0 查看操作菜单。[/]")

    @work
    async def _fetch_status(self) -> None:
        """查询地下城状态并渲染当前房间及角色信息。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在查询战斗状态...[/]")
        logger.info(
            f"CombatRoomScreen._fetch_status: user={self._user_name} game={self._game_name}"
        )

        try:
            # ── 第一段：地下城整体信息（名称、生态、总房间数） ──
            state_resp = await fetch_dungeon_state(self._user_name, self._game_name)
            dungeon = state_resp.dungeon

            self._status_bar_text = (
                f"[bold cyan]战斗房间[/]  [bold yellow]{display_name(dungeon.name)}[/]  "
                f"[dim]房间 {dungeon.current_room_index + 1}/{len(dungeon.rooms)}[/]"
            )
            self.query_one("#combat-status", Static).update(self._status_bar_text)

            logger.info(
                f"CombatRoomScreen._fetch_status: 地下城状态查询成功 dungeon={dungeon.name}"
            )
        except Exception as e:
            logger.error(
                f"CombatRoomScreen._fetch_status: 地下城状态查询失败 error={e}"
            )
            log.write(f"[bold red]❌ 查询地下城状态失败: {e}[/]")
            return

        try:
            # ── 第二段：当前房间详情（ECS 运行时数据链） ──

            # Step A：获取当前房间及战斗状态
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            room = room_resp.room
            stage = room.stage
            combat = room.combat

            self._status_bar_text = (
                f"[bold cyan]战斗房间[/]  [bold yellow]{display_name(dungeon.name)}[/]  "
                f"[bold white]▶[/]  [bold green]{display_name(stage.name)}[/]  "
                f"[dim]{dungeon.current_room_index + 1}/{len(dungeon.rooms)}[/]"
            )
            self.query_one("#combat-status", Static).update(self._status_bar_text)

            log.write(
                "[bold cyan]── 参战角色 ──────────────────────────────────────[/]"
            )

            # Step B：从 stages state 取该场景的运行时 actor 名单
            stages_resp = await fetch_stages_state(self._user_name, self._game_name)
            actor_names = stages_resp.mapping.get(stage.name, [])

            # Step C：逐实体获取运行时 ECS 组件数据
            if actor_names:
                details_resp = await fetch_entities_details(
                    self._user_name, self._game_name, actor_names
                )
                self._write_full_entities_block(details_resp.entities_serialization)
            else:
                log.write("  [dim]（房间内无角色）[/]")
            log.write("")

            log.write(
                f"  [bold]战斗状态：[/] {combat.state.name}  "
                f"[bold]战斗结果：[/] {combat.result.name}  "
                f"[bold]当前局数：[/] {len(combat.rounds)}"
            )
            if combat.rounds:
                cur = combat.rounds[-1]
                snapshot = (
                    cur.actor_order_snapshots[-1] if cur.actor_order_snapshots else []
                )
                order_str = (
                    " => ".join(display_name(a) for a in snapshot)
                    if snapshot
                    else "[dim]（无）[/]"
                )
                done_str = (
                    "  ".join(display_name(a) for a in cur.completed_actors)
                    if cur.completed_actors
                    else "[dim]（无）[/]"
                )
                current_actor_str = (
                    f"[bold yellow]{display_name(cur.current_turn_actor_name)}[/]"
                    if cur.current_turn_actor_name
                    else "[dim]（回合已结束）[/]"
                )
                log.write(f"  [bold]行动顺序：[/] {order_str}")
                log.write(f"  [bold]已出手：[/]   {done_str}")
                log.write(f"  [bold]当前行动：[/] {current_actor_str}")
            log.write("")

            logger.info(
                f"CombatRoomScreen._fetch_status: 房间查询成功 room={stage.name}"
            )
        except Exception as e:
            logger.warning(
                f"CombatRoomScreen._fetch_status: 房间查询失败（可能尚未进入房间）error={e}"
            )
            log.write("[dim]（当前地下城暂无进行中的房间）[/]")

    @work
    async def _do_combat_start(self) -> None:
        """执行战斗初始化（cmd 1）：仅在 INITIALIZATION 阶段有效。"""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        logger.info(
            f"CombatRoomScreen._do_combat_start: user={self._user_name} game={self._game_name}"
        )

        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            state = room_resp.room.combat.state
        except Exception as e:
            logger.error(f"_do_combat_start: 读取房间状态失败 error={e}")
            log.write(f"[bold red]❌ 读取战斗状态失败: {_format_http_error(e)}[/]")
            inp.disabled = False
            inp.focus()
            return

        if state != CombatState.INITIALIZATION:
            log.write(f"[yellow]⚠ 当前战斗状态为 {state.name}，无需初始化。[/]")
            inp.disabled = False
            inp.focus()
            return

        log.write("[dim]▶ 正在初始化战斗...[/]")
        ok = await self._run_combat_init()

        inp.disabled = False
        inp.focus()
        if ok:
            self._fetch_status()

    @work
    async def _do_advance_combat(self) -> None:
        """为全员抽牌（cmd 2）。"""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        logger.info(
            f"CombatRoomScreen._do_advance_combat: user={self._user_name} game={self._game_name}"
        )

        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            state = room_resp.room.combat.state
        except Exception as e:
            logger.error(f"_do_advance_combat: 读取房间状态失败 error={e}")
            log.write(f"[bold red]❌ 读取战斗状态失败: {_format_http_error(e)}[/]")
            inp.disabled = False
            inp.focus()
            return

        if state in (CombatState.COMPLETE, CombatState.POST_COMBAT):
            log.write("[yellow]⚠ 战斗已结束，无法抽牌。[/]")
            inp.disabled = False
            inp.focus()
            return

        if state == CombatState.NONE:
            log.write("[yellow]⚠ 战斗尚未创建，请先进入战斗房间。[/]")
            inp.disabled = False
            inp.focus()
            return

        if state == CombatState.INITIALIZATION:
            log.write("[yellow]⚠ 战斗尚未初始化，请先执行 1 战斗开始。[/]")
            inp.disabled = False
            inp.focus()
            return

        # ── 全员抽牌 ──
        log.write("[dim]▶ 正在激活全员抽牌...[/]")
        await self._run_draw_cards()

        inp.disabled = False
        inp.focus()
        self._fetch_status()

    async def _run_combat_init(self) -> bool:
        """执行战斗初始化任务，返回 True 表示成功。"""
        log = self.query_one(RichLog)
        logger.info(
            f"CombatRoomScreen._run_combat_init: user={self._user_name} game={self._game_name}"
        )
        task_id = ""
        try:
            resp = await server_dungeon_combat_init(self._user_name, self._game_name)
            task_id = resp.task_id
            log.write(f"[dim]任务已创建：{task_id}[/]")
            logger.info(f"_run_combat_init: 任务已创建 task_id={task_id}")
        except Exception as e:
            logger.error(f"_run_combat_init: 请求失败 error={e}")
            log.write(f"[bold red]❌ 战斗初始化请求失败: {_format_http_error(e)}[/]")
            return False

        try:
            await watch_task_until_done(task_id, timeout_seconds=60)
            log.write("[bold green]✅ 战斗初始化完成[/]")
            logger.info(f"_run_combat_init: 任务完成 task_id={task_id}")
            return True
        except TaskFailedError as e:
            log.write(f"[bold red]❌ 战斗初始化失败: {e}[/]")
            logger.error(f"_run_combat_init: 任务失败 task_id={task_id} error={e}")
            return False
        except TimeoutError:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(f"_run_combat_init: 轮询超时 task_id={task_id}")
            return False
        except Exception as e:
            logger.warning(f"_run_combat_init: 等待任务失败 error={e}")
            return False

    async def _run_draw_cards(self) -> bool:
        """执行全员抽牌任务，返回 True 表示成功。"""
        log = self.query_one(RichLog)
        logger.info(
            f"CombatRoomScreen._run_draw_cards: user={self._user_name} game={self._game_name}"
        )
        task_id = ""
        try:
            resp = await server_dungeon_combat_draw_cards(
                self._user_name, self._game_name
            )
            task_id = resp.task_id
            log.write(f"[dim]任务已创建：{task_id}[/]")
            logger.info(f"_run_draw_cards: 任务已创建 task_id={task_id}")
        except Exception as e:
            logger.error(f"_run_draw_cards: 请求失败 error={e}")
            log.write(f"[bold red]❌ 全员抽牌请求失败: {_format_http_error(e)}[/]")
            return False

        try:
            await watch_task_until_done(task_id, timeout_seconds=60)
            log.write("[bold green]✅ 全员抽牌完成[/]")
            logger.info(f"_run_draw_cards: 任务完成 task_id={task_id}")
            return True
        except TaskFailedError as e:
            log.write(f"[bold red]❌ 全员抽牌失败: {e}[/]")
            logger.error(f"_run_draw_cards: 任务失败 task_id={task_id} error={e}")
            return False
        except TimeoutError:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(f"_run_draw_cards: 轮询超时 task_id={task_id}")
            return False
        except Exception as e:
            logger.warning(f"_run_draw_cards: 等待任务失败 error={e}")
            return False

    @work
    async def _do_combat_retreat(self) -> None:
        """触发战斗撤退，轮询任务完成后刷新状态。"""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        log.write("[dim]▶ 正在触发撤退...[/]")
        logger.info(
            f"CombatRoomScreen._do_combat_retreat: user={self._user_name} game={self._game_name}"
        )

        task_id = ""
        try:
            resp = await server_dungeon_combat_retreat(self._user_name, self._game_name)
            task_id = resp.task_id
            log.write(f"[dim]任务已创建：{task_id}[/]")
            logger.info(f"_do_combat_retreat: 任务已创建 task_id={task_id}")
        except Exception as e:
            logger.error(f"_do_combat_retreat: 请求失败 error={e}")
            log.write(f"[bold red]❌ 撤退请求失败: {_format_http_error(e)}[/]")
            inp.disabled = False
            inp.focus()
            return

        try:
            await watch_task_until_done(task_id, timeout_seconds=60)
            log.write("[bold green]✅ 撤退成功[/]")
            logger.info(f"_do_combat_retreat: 任务完成 task_id={task_id}")
        except TaskFailedError as e:
            log.write(f"[bold red]❌ 撤退失败: {e}[/]")
            logger.error(f"_do_combat_retreat: 任务失败 task_id={task_id} error={e}")
        except TimeoutError:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(f"_do_combat_retreat: 轮询超时 task_id={task_id}")
        except Exception as e:
            logger.warning(f"_do_combat_retreat: 等待任务失败 error={e}")

        inp.disabled = False
        inp.focus()
        self._fetch_status()

    @work
    async def _do_exit(self) -> None:
        """退出地下城，返回到地下城总览。"""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        log.write("[dim]▶ 正在退出地下城...[/]")
        logger.info(
            f"CombatRoomScreen._do_exit: user={self._user_name} game={self._game_name}"
        )

        try:
            await server_dungeon_exit(self._user_name, self._game_name)
            log.write("[bold green]✅ 已退出地下城，正在返回...[/]")
            logger.info("CombatRoomScreen._do_exit: 退出成功")
            self.app.pop_screen()  # 弹出 CombatRoomScreen
            self.app.pop_screen()  # 弹出 DungeonOverviewScreen，回到 HomeScreen
        except Exception as e:
            logger.error(f"CombatRoomScreen._do_exit: 退出失败 error={e}")
            log.write(f"[bold red]❌ 退出地下城失败: {_format_http_error(e)}[/]")
            inp.disabled = False
            inp.focus()

    # ══════════════════════════════════════════════
    # 出牌流程（原 PlayCardsScreen 内联合并）
    # ══════════════════════════════════════════════

    def _start_play_cards(self) -> None:
        """进入出牌模式：打印标题后启动 _advance()。"""
        log = self.query_one(RichLog)
        log.write(
            "\n[bold cyan]── 出牌阶段 ─────────────────────────────────────────[/]\n"
            "  逐步完成当前回合所有角色的出牌。\n"
        )
        inp = self.query_one(Input)
        inp.disabled = True
        self._phase = _Phase.LOADING
        self._advance()

    @work
    async def _start_discard_card(self) -> None:
        """弃牌模式：拉取玩家手牌并展示，等待用户选择要弃置的卡牌。"""
        log = self.query_one(RichLog)
        self.query_one(Input).disabled = True

        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            stage_name = room_resp.room.stage.name
            stages_resp = await fetch_stages_state(self._user_name, self._game_name)
            stage_actor_names: List[str] = list(stages_resp.mapping.get(stage_name, []))
            all_details = await fetch_entities_details(
                self._user_name, self._game_name, stage_actor_names
            )
        except Exception as e:
            log.write(f"[bold red]❌ 加载手牌失败: {e}[/]")
            inp = self.query_one(Input)
            inp.disabled = False
            inp.focus()
            return

        # 找到玩家控制的角色（PlayerComponent + HandComponent）
        player_actor: Optional[str] = None
        hand_cards: List[Card] = []
        for entity in all_details.entities_serialization:
            comp_names = {c.name for c in entity.components}
            if PlayerComponent.__name__ not in comp_names:
                continue
            player_actor = entity.name
            for comp in entity.components:
                if comp.name == HandComponent.__name__:
                    hand_cards = HandComponent(**comp.data).cards
            break

        if player_actor is None:
            log.write("[yellow]⚠ 未找到玩家角色。[/]")
            inp = self.query_one(Input)
            inp.disabled = False
            inp.focus()
            return

        if not hand_cards:
            log.write("[yellow]⚠ 手牌为空，请先抽牌。[/]")
            inp = self.query_one(Input)
            inp.disabled = False
            inp.focus()
            return

        short = display_name(player_actor)
        log.write(
            f"\n[bold cyan]── 弃牌：{short} ────────────────────────────────────────[/]"
        )
        self._write_hand_table(hand_cards, player_actor)

        self._current_actor = player_actor
        self._discard_hand_cards = list(hand_cards)
        self._phase = _Phase.SELECT_DISCARD_CARD
        self._update_play_status(
            f"[{short}] 弃牌：输入编号（1-{len(hand_cards)}）  |  q 取消"
        )
        log.write(f"  [dim](输入卡牌编号弃牌 / q 取消)[/]")
        inp = self.query_one(Input)
        inp.placeholder = f"1-{len(hand_cards)} / q 取消"
        inp.disabled = False
        inp.focus()

    def _handle_discard_card_selection(self, raw: str) -> None:
        """用户在弃牌选牌阶段输入编号后：验证并调用 _do_discard_card。"""
        log = self.query_one(RichLog)
        hand_cards = self._discard_hand_cards

        if raw.lower() == "q":
            self._discard_hand_cards = []
            self._abort_play_cards()
            return

        if not raw.isdigit():
            log.write(f"[red]请输入 1-{len(hand_cards)} 的数字，或 q 取消。[/]")
            return

        idx = int(raw) - 1
        if not (0 <= idx < len(hand_cards)):
            log.write(f"[red]无效编号 '{raw}'，请输入 1-{len(hand_cards)}。[/]")
            return

        assert self._current_actor is not None
        discard_card = hand_cards[idx]
        log.write(f"  准备弃牌：[bold cyan]{discard_card.name}[/]")
        self._discard_hand_cards = []
        self._do_discard_card(self._current_actor, discard_card.name)

    # ──────────────────────────────────────────────
    # 消耗品使用流程
    # ──────────────────────────────────────────────

    @work
    async def _start_use_consumable_item(self) -> None:
        """进入消耗品使用模式：加载玩家背包中的消耗品并展示选择列表。"""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            stage_name = room_resp.room.stage.name
            stages_resp = await fetch_stages_state(self._user_name, self._game_name)
            stage_actor_names: List[str] = list(stages_resp.mapping.get(stage_name, []))
            all_details = await fetch_entities_details(
                self._user_name, self._game_name, stage_actor_names
            )
        except Exception as e:
            log.write(f"[bold red]❌ 加载背包信息失败: {_format_http_error(e)}[/]")
            inp.disabled = False
            inp.focus()
            return

        # 找到玩家控制的角色（PlayerComponent）
        player_actor: Optional[str] = None
        consumables: List[ConsumableItem] = []
        for entity in all_details.entities_serialization:
            comp_names = {c.name for c in entity.components}
            if PlayerComponent.__name__ not in comp_names:
                continue
            player_actor = entity.name
            for comp in entity.components:
                if comp.name == InventoryComponent.__name__:
                    inv = InventoryComponent(**comp.data)
                    consumables = [
                        item
                        for item in inv.items
                        if isinstance(item, ConsumableItem) and item.count > 0
                    ]
            break

        if player_actor is None:
            log.write("[yellow]⚠ 未找到玩家角色。[/]")
            inp.disabled = False
            inp.focus()
            return

        if not consumables:
            log.write("[yellow]⚠ 背包中没有可用的消耗品。[/]")
            inp.disabled = False
            inp.focus()
            return

        short = display_name(player_actor)
        log.write(
            f"\n[bold cyan]── 使用消耗品：{short} ──────────────────────────────────[/]"
        )
        for i, item in enumerate(consumables, 1):
            tt_str = _TARGET_LABEL.get(item.target_type, f"[dim]{item.target_type}[/]")
            effects_str = (
                f"\n        [yellow]效果：{'、'.join(item.effects)}[/]"
                if item.effects
                else ""
            )
            log.write(
                f"    [bold cyan]{i}.[/] [bold]{item.name}[/]  "
                f"x{item.count}  目标:{tt_str}"
                f"\n        [dim]{item.description}[/]" + effects_str
            )

        self._current_actor = player_actor
        self._consumable_candidates = list(consumables)
        self._phase = _Phase.SELECT_CONSUMABLE_ITEM
        self._update_play_status(
            f"[{short}] 选择消耗品（1-{len(consumables)}）  |  q 取消"
        )
        log.write(f"  [dim](输入编号选择 / q 取消)[/]")
        inp.placeholder = f"1-{len(consumables)} / q 取消"
        inp.disabled = False
        inp.focus()

    @work
    async def _handle_consumable_item_selection(self, raw: str) -> None:
        """用户选择消耗品编号后：若需要选目标则展示目标列表，否则直接使用。"""
        log = self.query_one(RichLog)
        candidates = self._consumable_candidates

        if raw.lower() == "q":
            self._consumable_candidates = []
            self._abort_play_cards()
            return

        if not raw.isdigit():
            log.write(f"[red]请输入 1-{len(candidates)} 的数字，或 q 取消。[/]")
            self._phase = _Phase.SELECT_CONSUMABLE_ITEM
            inp = self.query_one(Input)
            inp.disabled = False
            inp.focus()
            return

        idx = int(raw) - 1
        if not (0 <= idx < len(candidates)):
            log.write(f"[red]无效编号 '{raw}'，请输入 1-{len(candidates)}。[/]")
            self._phase = _Phase.SELECT_CONSUMABLE_ITEM
            inp = self.query_one(Input)
            inp.disabled = False
            inp.focus()
            return

        assert self._current_actor is not None
        item = candidates[idx]
        log.write(f"  已选：[bold cyan]{item.name}[/]")
        self._consumable_candidates = []

        # ENEMY_SINGLE：需要选目标
        if item.target_type == TargetType.ENEMY_SINGLE:
            try:
                room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
                stage_name = room_resp.room.stage.name
                enemy_names = await self._fetch_play_enemy_names(stage_name)
            except Exception as e:
                log.write(f"[bold red]❌ 加载敌方列表失败: {_format_http_error(e)}[/]")
                self._abort_play_cards()
                return

            if not enemy_names:
                log.write("  [dim]场上无存活敌人，直接使用[/]")
                self._do_use_consumable_item(self._current_actor, item.name, [])
                return

            log.write("  [bold]可用目标：[/]")
            for i, name in enumerate(enemy_names, 1):
                log.write(f"    [bold cyan]{i}.[/] {display_name(name)}")
            self._selected_consumable_name = item.name
            self._target_candidates = list(enemy_names)
            self._phase = _Phase.SELECT_CONSUMABLE_TARGET
            self._update_play_status(f"输入目标编号（1-{len(enemy_names)}）  |  q 取消")
            inp = self.query_one(Input)
            inp.placeholder = f"1-{len(enemy_names)} / q 取消"
            inp.disabled = False
            inp.focus()

        else:
            # SELF_ONLY / ENEMY_ALL：无需手动选目标，系统自动处理
            label_map = {
                TargetType.ENEMY_ALL: "自动命中所有存活敌方",
                TargetType.SELF_ONLY: "仅作用于自身",
            }
            hint = label_map.get(item.target_type, "自动处理目标")
            log.write(f"  [dim]此消耗品{hint}[/]")
            self._do_use_consumable_item(self._current_actor, item.name, [])

    def _handle_consumable_target_selection(self, raw: str) -> None:
        """用户在消耗品目标选择阶段输入编号后：验证并调用 _do_use_consumable_item。"""
        log = self.query_one(RichLog)

        if raw.lower() == "q":
            self._selected_consumable_name = None
            self._target_candidates = []
            self._abort_play_cards()
            return

        candidates = self._target_candidates
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(candidates):
                target = candidates[idx]
            else:
                log.write(
                    f"[red]无效目标编号 '{raw}'，请输入 1-{len(candidates)} 或 q 取消。[/]"
                )
                return
        else:
            matched = [n for n in candidates if n == raw or display_name(n) == raw]
            if matched:
                target = matched[0]
            else:
                log.write(f"[red]找不到目标 '{raw}'，请重新输入。[/]")
                return

        assert self._current_actor is not None
        assert self._selected_consumable_name is not None
        actor = self._current_actor
        item_name = self._selected_consumable_name
        self._selected_consumable_name = None
        self._target_candidates = []
        self._do_use_consumable_item(actor, item_name, [target])

    @work
    async def _do_use_consumable_item(
        self, actor_name: str, item_name: str, targets: List[str]
    ) -> None:
        """后台消耗品使用任务：调用服务器接口并轮询完成，然后刷新状态。"""
        log = self.query_one(RichLog)
        self._phase = _Phase.WAITING
        self.query_one(Input).disabled = True

        short = display_name(actor_name)
        target_str = (
            "、".join(display_name(t) for t in targets) if targets else "（自动）"
        )
        log.write(f"  [dim]▶ {short} 使用消耗品：{item_name}  目标：{target_str}[/]")
        logger.info(
            f"CombatRoomScreen._do_use_consumable_item: actor={actor_name} item={item_name} targets={targets}"
        )

        task_id = ""
        try:
            resp = await server_use_consumable_item(
                self._user_name, self._game_name, actor_name, item_name, targets
            )
            task_id = resp.task_id
            logger.info(f"_do_use_consumable_item: 任务已创建 task_id={task_id}")
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            log.write(f"[bold red]❌ 使用消耗品请求失败: {detail}[/]")
            logger.error(f"_do_use_consumable_item: 请求失败 error={e}")
            self._abort_play_cards()
            return
        except Exception as e:
            log.write(f"[bold red]❌ 使用消耗品请求失败: {_format_http_error(e)}[/]")
            logger.error(f"_do_use_consumable_item: 请求失败 error={e}")
            self._abort_play_cards()
            return

        self._update_play_status(f"等待 {short} 使用消耗品完成...")
        try:
            await watch_task_until_done(task_id, timeout_seconds=90)
            log.write(f"  [green]✓ {short} 使用消耗品完成：{item_name}[/]")
            logger.info(f"_do_use_consumable_item: 任务完成 task_id={task_id}")
        except TaskFailedError as e:
            log.write(f"[bold red]❌ {short} 使用消耗品失败: {e}[/]")
            logger.error(
                f"_do_use_consumable_item: 任务失败 task_id={task_id} error={e}"
            )
        except TimeoutError:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(f"_do_use_consumable_item: 轮询超时 task_id={task_id}")
        except Exception as e:
            logger.warning(f"_do_use_consumable_item: 等待任务失败 error={e}")

        self._phase = None
        inp = self.query_one(Input)
        inp.placeholder = "输入命令..."
        inp.disabled = False
        inp.focus()
        self._fetch_status()

    # ──────────────────────────────────────────────
    # 核心状态机推进（唯一分发点，不递归）
    # ──────────────────────────────────────────────
    @work
    async def _advance(self) -> None:
        """从服务器拉取最新状态，决定下一个 phase，做一次 phase 进入后 return。
        永远不会调用自身；_do_play_card 结束后以新 @work 调用本方法。
        """
        log = self.query_one(RichLog)

        # ── 拉取当前战斗状态 ──
        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            combat = room_resp.room.combat
            stage_name = room_resp.room.stage.name
            cur = combat.rounds[-1] if combat.rounds else None
            enemy_names = await self._fetch_play_enemy_names(stage_name)
        except Exception as e:
            logger.warning(f"_advance: 拉取状态失败 error={e}")
            self._enter_round_done()
            return

        # ── 战斗已结束 ──
        if combat.state in (CombatState.COMPLETE, CombatState.POST_COMBAT):
            self._confirm_round_done()
            return

        # ── 无回合记录 → 需要先抽牌 ──
        if cur is None:
            log.write("[yellow]⚠ 当前没有进行中的回合，请输入 [bold]1[/] 抽牌。[/]")
            self._phase = None
            inp = self.query_one(Input)
            inp.placeholder = "输入命令..."
            inp.disabled = False
            inp.focus()
            return

        current_actor = cur.current_turn_actor_name
        round_num = len(combat.rounds)
        action_order = list(
            cur.actor_order_snapshots[-1] if cur.actor_order_snapshots else []
        )
        completed_actors = list(cur.completed_actors)

        # ── 回合已全部出完 ──
        if current_actor is None:
            self._enter_round_done()
            return

        # ── 拉取场上实体（敌/友方共用）──
        try:
            stages_resp = await fetch_stages_state(self._user_name, self._game_name)
            stage_actor_names: List[str] = list(stages_resp.mapping.get(stage_name, []))
            if current_actor not in stage_actor_names:
                stage_actor_names.append(current_actor)
            all_details = await fetch_entities_details(
                self._user_name, self._game_name, stage_actor_names
            )
        except Exception as e:
            logger.error(f"_advance: 加载实体详情失败 error={e}")
            log.write(f"[bold red]❌ 加载战场数据失败: {e}[/]")
            self._phase = None
            inp = self.query_one(Input)
            inp.placeholder = "输入命令..."
            inp.disabled = False
            inp.focus()
            return

        # ── 提取 current_actor 的手牌（敌人同样有 HandComponent，统一处理）──
        hand_cards: List[Card] = []
        for entity in all_details.entities_serialization:
            if entity.name == current_actor:
                for comp in entity.components:
                    if comp.name == HandComponent.__name__:
                        hand_cards = HandComponent(**comp.data).cards
                break

        # ── 无手牌时的统一守卫 ──
        if not hand_cards:
            if not cur.completed_actors:
                # 新回合，CombatRoundTransitionSystem 已清除所有手牌，需要先抽牌
                log.write("[yellow]⚠ 新回合已开始，请输入 [bold]1[/] 抽牌后再出牌。[/]")
                self._phase = None
                inp = self.query_one(Input)
                inp.placeholder = "输入命令..."
                inp.disabled = False
                inp.focus()
            else:
                # 回合进行中但此角色无手牌（罕见边缘情况）：提交空出牌让服务器推进
                log.write(
                    f"[yellow]⚠ {display_name(current_actor)} 没有手牌，跳过出牌。[/]"
                )
                self._do_play_card(current_actor, "", [])
            return

        # ── 敌方回合（手牌已确认非空）──
        if current_actor in enemy_names:
            self._current_actor = current_actor
            self._enter_enemy_turn(
                current_actor, stage_name, round_num, action_order, completed_actors
            )
            return

        # ── 进入选牌 ──
        short = display_name(current_actor)
        log.write(
            f"[bold green]── 你的回合：{short} ────────────────────────────────[/]"
        )
        ao_str = " → ".join(display_name(a) for a in action_order)
        done_str = (
            "  ".join(display_name(a) for a in completed_actors)
            if completed_actors
            else "（无）"
        )
        log.write(
            f"  [bold yellow]回合 {round_num}[/]  行动序列：{ao_str}  已出手：{done_str}"
        )
        ally_entities = [
            e
            for e in all_details.entities_serialization
            if not any(c.name == MonsterComponent.__name__ for c in e.components)
        ]
        self._write_full_entities_block(
            ally_entities, show_hand=False, show_header=False
        )
        log.write("  [bold cyan]── 选牌（输入编号）──[/]")
        self._write_hand_table(hand_cards, current_actor)
        self._current_actor = current_actor
        self._phase = _Phase.SELECT_CARD
        self._update_play_status(
            f"[{short}] 输入卡牌编号（1-{len(hand_cards)}）选牌  |  q 返回主菜单"
        )
        log.write(f"  [dim](输入卡牌编号出牌 / q 返回主菜单)[/]")
        inp = self.query_one(Input)
        inp.placeholder = f"1-{len(hand_cards)} 或卡牌名 / q 返回"
        inp.disabled = False
        inp.focus()

    @work
    async def _enter_enemy_turn(
        self,
        actor_name: str,
        stage_name: str,
        round_num: int = 0,
        action_order: Optional[List[str]] = None,
        completed_actors: Optional[List[str]] = None,
    ) -> None:
        log = self.query_one(RichLog)
        short = display_name(actor_name)
        log.write(
            f"[bold red]── 敌人回合：{short} ──────────────────────────────────[/]"
        )
        try:
            stages_resp = await fetch_stages_state(self._user_name, self._game_name)
            actor_names: List[str] = list(stages_resp.mapping.get(stage_name, []))
            details = await fetch_entities_details(
                self._user_name, self._game_name, actor_names
            )
            self._write_battlefield_block(
                details.entities_serialization,
                round_num,
                action_order,
                completed_actors,
            )
        except Exception as e:
            logger.warning(f"_enter_enemy_turn: 战场态势加载失败 error={e}")
            log.write("[dim](战场态势加载失败)[/]\n")
        log.write(
            "  按 [bold]Enter[/] 触发 AI 决策  [dim]（输入 q 返回主菜单，下次可继续）[/]"
        )
        self._phase = _Phase.ENEMY_TURN
        self._update_play_status(
            f"敌人 [{short}] 的回合 — 按 Enter 触发 AI 出牌  |  q 返回主菜单"
        )
        inp = self.query_one(Input)
        inp.placeholder = "Enter 触发 AI / q 返回主菜单"
        inp.disabled = False
        inp.focus()

    def _enter_round_done(self) -> None:
        """回合结束：保留 log（narrative/combat_log 仍可见），等待用户按 Enter 回到主菜单。"""
        log = self.query_one(RichLog)
        self._phase = _Phase.ROUND_DONE
        log.write(
            "\n[bold green]✅ 本回合所有角色已出手，回合结束。[/]"
            "  按 [bold]Enter[/] 回到主菜单。\n"
        )
        inp = self.query_one(Input)
        inp.placeholder = "按 Enter 回到主菜单..."
        inp.disabled = False
        inp.focus()

    def _abort_play_cards(self) -> None:
        """中断出牌流程，清空状态，回到主菜单命令模式。"""
        self._phase = None
        self._current_actor = None
        self._selected_card_name = None
        self._target_candidates = []
        self._consumable_candidates = []
        self._selected_consumable_name = None
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.placeholder = "输入命令..."
        inp.disabled = False
        inp.focus()
        log.clear()
        log.write(COMBAT_ROOM_MENU)
        log.write("[dim]已中断出牌。输入 [bold]2[/] 可随时继续本回合。[/]\n")

    def _confirm_round_done(self) -> None:
        """用户确认后跳回主菜单（清 log、重印菜单）。"""
        log = self.query_one(RichLog)
        self._phase = None
        inp = self.query_one(Input)
        inp.placeholder = "输入命令..."
        inp.disabled = False
        inp.focus()
        log.clear()
        log.write(COMBAT_ROOM_MENU)

    # ──────────────────────────────────────────────
    # 敌方名单辅助（通过 MonsterComponent）
    # ──────────────────────────────────────────────
    async def _fetch_play_enemy_names(self, stage_name: str) -> List[str]:
        stages_resp = await fetch_stages_state(self._user_name, self._game_name)
        actor_names = stages_resp.mapping.get(stage_name, [])
        if not actor_names:
            return []
        details = await fetch_entities_details(
            self._user_name, self._game_name, actor_names
        )
        return [
            e.name
            for e in details.entities_serialization
            if any(c.name == MonsterComponent.__name__ for c in e.components)
        ]

    # ──────────────────────────────────────────────
    # 卡牌选择（@work async：实时拉取手牌，不依赖缓存）
    # ──────────────────────────────────────────────
    @work
    async def _handle_card_selection(self, raw: str) -> None:
        """用户输入卡牌编号后处理：实时从服务器拉取手牌、阵营列表，解析选择，
        进入 SELECT_TARGET 或直接提交出牌。
        """
        log = self.query_one(RichLog)
        if self._current_actor is None:
            log.write("[red]错误：当前无出牌角色。[/]")
            return

        actor_name = self._current_actor

        # ── 实时拉取手牌与阵营列表 ──
        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            stage_name = room_resp.room.stage.name
            stages_resp = await fetch_stages_state(self._user_name, self._game_name)
            stage_actor_names: List[str] = list(stages_resp.mapping.get(stage_name, []))
            if actor_name not in stage_actor_names:
                stage_actor_names.append(actor_name)
            all_details = await fetch_entities_details(
                self._user_name, self._game_name, stage_actor_names
            )
        except Exception as e:
            logger.error(f"_handle_card_selection: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载手牌失败: {e}[/]")
            self._phase = _Phase.SELECT_CARD
            inp = self.query_one(Input)
            inp.disabled = False
            inp.focus()
            return

        hand_cards: List[Card] = []
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
                    if comp.name == HandComponent.__name__:
                        hand_cards = HandComponent(**comp.data).cards

        if not hand_cards:
            log.write("[yellow]⚠ 手牌已不存在，重新推进回合...[/]")
            self._advance()
            return

        # ── 解析用户输入 ──
        card: Optional[Card] = None
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(hand_cards):
                card = hand_cards[idx]
        else:
            for c in hand_cards:
                if c.name == raw:
                    card = c
                    break

        if card is None:
            log.write(
                f"[red]无效输入 '{raw}'，请输入 1-{len(hand_cards)} 的数字或卡牌名称。[/]"
            )
            self._phase = _Phase.SELECT_CARD
            inp = self.query_one(Input)
            inp.placeholder = f"1-{len(hand_cards)} 或卡牌名 / q 返回"
            inp.disabled = False
            inp.focus()
            return

        log.write(f"  已选：[bold cyan]{card.name}[/]")
        target_type = card.target_type

        # ── 按目标类型分支 ──
        if target_type in ("enemy_all", "ally_all", "self_only"):
            label_map = {
                "enemy_all": "自动命中所有存活敌方",
                "ally_all": "自动命中所有存活友方",
                "self_only": "仅作用于自身",
            }
            log.write(f"  [dim]此卡{label_map[target_type]}[/]")
            self._do_play_card(actor_name, card.name, [])

        elif target_type == "ally_single":
            if alive_allies:
                log.write("  [bold]可选友方目标：[/]")
                for i, name in enumerate(alive_allies, 1):
                    log.write(f"    [bold cyan]{i}.[/] {display_name(name)}")
                self._selected_card_name = card.name
                self._target_candidates = list(alive_allies)
                self._phase = _Phase.SELECT_TARGET
                self._update_play_status(
                    f"输入目标编号（1-{len(alive_allies)}），或直接 Enter 跳过"
                )
                inp = self.query_one(Input)
                inp.placeholder = "编号或 Enter 跳过"
                inp.disabled = False
                inp.focus()
            else:
                log.write("  [dim]无存活友方，直接出牌[/]")
                self._do_play_card(actor_name, card.name, [])

        else:  # enemy_single（默认）
            if alive_enemies:
                log.write("  [bold]可用目标：[/]")
                for i, name in enumerate(alive_enemies, 1):
                    log.write(f"    [bold cyan]{i}.[/] {display_name(name)}")
                self._selected_card_name = card.name
                self._target_candidates = list(alive_enemies)
                self._phase = _Phase.SELECT_TARGET
                self._update_play_status(
                    f"输入目标编号（1-{len(alive_enemies)}），或直接 Enter 跳过"
                )
                inp = self.query_one(Input)
                inp.placeholder = "编号或 Enter 跳过"
                inp.disabled = False
                inp.focus()
            else:
                log.write("  [dim]无存活敌人，直接出牌[/]")
                self._do_play_card(actor_name, card.name, [])

    # ──────────────────────────────────────────────
    # 目标选择
    # ──────────────────────────────────────────────
    def _handle_target_selection(self, raw: str) -> None:
        log = self.query_one(RichLog)
        targets: List[str] = []

        if raw == "":
            log.write("  [dim]无目标[/]")
        else:
            candidates = self._target_candidates
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

        assert self._current_actor is not None
        assert self._selected_card_name is not None
        actor = self._current_actor
        card_name = self._selected_card_name
        self._selected_card_name = None
        self._target_candidates = []
        self._do_play_card(actor, card_name, targets)

    # ──────────────────────────────────────────────
    # 敌人出牌触发
    # ──────────────────────────────────────────────
    def _trigger_enemy_turn(self) -> None:
        assert self._current_actor is not None
        self._do_play_card(self._current_actor, "", [])

    # ──────────────────────────────────────────────
    # 后台出牌任务（玩家 & 敌人共用）
    # ──────────────────────────────────────────────
    @work
    async def _do_play_card(
        self, actor_name: str, card_name: str, targets: List[str]
    ) -> None:
        log = self.query_one(RichLog)
        self._phase = _Phase.WAITING
        self.query_one(Input).disabled = True

        short = display_name(actor_name)
        display_card = card_name if card_name else "（AI 自选）"
        log.write(
            f"  [dim]▶ {short} 出牌中：{display_card}  "
            f"目标：{[display_name(t) for t in targets] or '无'}[/]"
        )
        logger.info(
            f"CombatRoomScreen._do_play_card: actor={actor_name} card={card_name} targets={targets}"
        )

        prev_round_idx = -1
        prev_completed_count = 0
        prev_energy = 0
        try:
            pre_room = await fetch_dungeon_room(self._user_name, self._game_name)
            pre_rounds = pre_room.room.combat.rounds
            if pre_rounds:
                prev_round_idx = len(pre_rounds) - 1
                prev_completed_count = len(pre_rounds[-1].completed_actors)
                snapshot = pre_rounds[-1].actor_order_snapshots
                prev_energy = len(snapshot[-1] if snapshot else [])
        except Exception as e:
            logger.warning(f"_do_play_card: 出牌前快照失败 error={e}")

        task_id = ""
        try:
            resp = await server_play_cards(
                self._user_name, self._game_name, actor_name, card_name, targets
            )
            task_id = resp.task_id
            logger.info(f"_do_play_card: 任务已创建 task_id={task_id}")
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            log.write(f"[bold red]❌ 出牌请求失败: {detail}[/]")
            logger.error(f"_do_play_card: 请求失败 error={e}")
            self._advance()
            return
        except Exception as e:
            log.write(f"[bold red]❌ 出牌请求失败: {e}[/]")
            logger.error(f"_do_play_card: 请求失败 error={e}")
            self._advance()
            return

        self._update_play_status(f"等待 {short} 出牌完成...")
        try:
            await watch_task_until_done(task_id, timeout_seconds=90)
            log.write(f"  [green]✓ {short} 出牌完成[/]")
            logger.info(f"_do_play_card: 任务完成 task_id={task_id}")
        except TaskFailedError as e:
            log.write(f"[bold red]❌ {short} 出牌失败: {e}[/]")
            logger.error(f"_do_play_card: 任务失败 task_id={task_id} error={e}")
        except TimeoutError:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(f"_do_play_card: 轮询超时 task_id={task_id}")
        except Exception as e:
            logger.warning(f"_do_play_card: 等待任务失败 error={e}")

        await self._show_play_results(prev_round_idx, prev_completed_count)

        # ── 出牌后状态检查：若战斗已结束或本回合已完成，暂停并提示 ──
        if prev_energy > 0 and prev_round_idx >= 0:
            try:
                post_room = await fetch_dungeon_room(self._user_name, self._game_name)
                post_combat = post_room.room.combat
                post_rounds = post_combat.rounds
                log = self.query_one(RichLog)

                if post_combat.state in (CombatState.COMPLETE, CombatState.POST_COMBAT):
                    result = post_combat.result
                    if result == CombatResult.WIN:
                        log.write("\n[bold green]✅ 战斗胜利！所有敌人已被击败。[/]")
                    elif result == CombatResult.LOSE:
                        log.write("\n[bold red]💀 战斗失败，队伍全员阵亡。[/]")
                    else:
                        log.write("\n[bold yellow]⚔ 战斗已结束。[/]")
                    self._enter_round_done()
                    return

                if (
                    prev_round_idx < len(post_rounds)
                    and len(post_rounds[prev_round_idx].completed_actors) >= prev_energy
                ):
                    self._enter_round_done()
                    return
            except Exception as e:
                logger.warning(f"_do_play_card: 出牌后状态检查失败 error={e}")

        self._advance()  # 启动新 @work 推进状态机；当前 coroutine 到此结束

    # ──────────────────────────────────────────────
    # 后台弃牌任务
    # ──────────────────────────────────────────────
    @work
    async def _do_discard_card(self, actor_name: str, card_name: str) -> None:
        log = self.query_one(RichLog)
        self._phase = _Phase.WAITING
        self.query_one(Input).disabled = True

        short = display_name(actor_name)
        log.write(f"  [dim]▶ {short} 弃牌中：{card_name}[/]")
        logger.info(
            f"CombatRoomScreen._do_discard_card: actor={actor_name} card={card_name}"
        )

        task_id = ""
        try:
            resp = await server_exhaust_card(
                self._user_name, self._game_name, actor_name, card_name
            )
            task_id = resp.task_id
            logger.info(f"_do_discard_card: 任务已创建 task_id={task_id}")
        except httpx.HTTPStatusError as e:
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            log.write(f"[bold red]❌ 弃牌请求失败: {detail}[/]")
            logger.error(f"_do_discard_card: 请求失败 error={e}")
            self._advance()
            return
        except Exception as e:
            log.write(f"[bold red]❌ 弃牌请求失败: {e}[/]")
            logger.error(f"_do_discard_card: 请求失败 error={e}")
            self._advance()
            return

        self._update_play_status(f"等待 {short} 弃牌完成...")
        try:
            await watch_task_until_done(task_id, timeout_seconds=90)
            log.write(f"  [green]✓ {short} 弃牌完成：{card_name}[/]")
            logger.info(f"_do_discard_card: 任务完成 task_id={task_id}")
        except TaskFailedError as e:
            log.write(f"[bold red]❌ {short} 弃牌失败: {e}[/]")
            logger.error(f"_do_discard_card: 任务失败 task_id={task_id} error={e}")
        except TimeoutError:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(f"_do_discard_card: 轮询超时 task_id={task_id}")
        except Exception as e:
            logger.warning(f"_do_discard_card: 等待任务失败 error={e}")

        self._advance()

    # ──────────────────────────────────────────────
    # 显示本次出牌的战斗演绎与计算日志
    # ──────────────────────────────────────────────
    async def _show_play_results(
        self, prev_round_idx: int, prev_completed_count: int
    ) -> None:
        if prev_round_idx < 0:
            return
        log = self.query_one(RichLog)
        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            rounds = room_resp.room.combat.rounds
            if prev_round_idx >= len(rounds):
                return
            cur = rounds[prev_round_idx]
            for text in cur.narrative[prev_completed_count:]:
                if text:
                    log.write(f"  [italic]{text}[/]")
            for text in cur.combat_log[prev_completed_count:]:
                if text:
                    log.write(f"  [dim cyan]{text}[/]")
        except Exception as e:
            logger.warning(f"_show_play_results: 加载日志失败 error={e}")

    # ──────────────────────────────────────────────
    # 出牌阶段提示（写入 log，不修改顶部状态栏）
    # ──────────────────────────────────────────────
    def _update_play_status(self, text: str) -> None:
        if text:
            log = self.query_one(RichLog)
            log.write(f"[dim]{text}[/]")

    # ──────────────────────────────────────────────
    # 战场态势渲染（通用辅助）
    # ──────────────────────────────────────────────
    def _write_battlefield_block(
        self,
        entities: List[EntitySerialization],
        round_num: int = 0,
        action_order: Optional[List[str]] = None,
        completed_actors: Optional[List[str]] = None,
    ) -> None:
        """从 ECS 实体列表渲染战场态势一览（回合信息 / HP）。"""
        log = self.query_one(RichLog)
        if round_num > 0:
            ao_str = " → ".join(display_name(a) for a in (action_order or []))
            done_list = completed_actors or []
            done_str = (
                "  ".join(display_name(a) for a in done_list) if done_list else "（无）"
            )
            log.write(
                f"  [bold yellow]回合 {round_num}[/]  行动序列：{ao_str}  已出手：{done_str}"
            )
        log.write("  [bold]战场态势：[/]")
        for entity in entities:
            comp_names = {c.name for c in entity.components}
            if MonsterComponent.__name__ in comp_names:
                flabel = "[red]敌[/]"
            elif PartyMemberComponent.__name__ in comp_names:
                flabel = "[green]友[/]"
            else:
                flabel = "[dim]?[/]"
            hp_str = "?/?"
            _stats_comp = None
            _equip_comp = None
            _inv_comp = None
            for comp in entity.components:
                if comp.name == CharacterStatsComponent.__name__:
                    _stats_comp = CharacterStatsComponent(**comp.data)
                elif comp.name == EquipmentComponent.__name__:
                    _equip_comp = EquipmentComponent(**comp.data)
                elif comp.name == InventoryComponent.__name__:
                    _inv_comp = InventoryComponent(**comp.data)
            if _stats_comp is not None:
                _final = compute_effective_stats(_stats_comp, _equip_comp, _inv_comp)
                hp_str = f"{_final.hp}/{_final.max_hp}"
            short = display_name(entity.name)
            log.write(f"    {flabel} [bold]{short}[/]" f"  HP:[yellow]{hp_str}[/]")
        log.write("")

    # ──────────────────────────────────────────────
    # 手牌表格渲染（通用辅助，选牌/弃牌/状态显示共用）
    # ──────────────────────────────────────────────
    def _write_hand_table(self, cards: List[Card], entity_name: str) -> None:
        """将手牌列表以表格形式写入 RichLog，与命令 6 状态显示保持一致。"""
        log = self.query_one(RichLog)
        hand_table = Table(
            show_header=True,
            show_lines=True,
            box=rich_box.ROUNDED,
            padding=(0, 1),
            expand=True,
        )
        hand_table.add_column("#", style="cyan", width=3, no_wrap=True)
        hand_table.add_column("名称", style="bold", min_width=10, no_wrap=True)
        hand_table.add_column("伤害", style="red", width=6, no_wrap=True)
        hand_table.add_column("目标", width=10, no_wrap=True)
        hand_table.add_column("描述 / 效果 / 词条", ratio=1)
        for idx, card in enumerate(cards, 1):
            dmg_cell = (
                f"{card.damage_dealt}x{card.hit_count}"
                if card.hit_count > 1
                else str(card.damage_dealt)
            )
            tt_str = _TARGET_LABEL.get(card.target_type, f"[dim]{card.target_type}[/]")
            detail_parts: List[str] = []
            if card.description:
                detail_parts.append(f"[dim]{card.description}[/]")
            if card.effects:
                detail_parts.append(f"[yellow]效果：{'、'.join(card.effects)}[/]")
            if not card.playable:
                detail_parts.append("[bold orange1]【不可出牌】[/]")
            if not card.discardable:
                detail_parts.append("[bold orange1]【不可弃牌】[/]")
            if card.source and card.source != entity_name:
                detail_parts.append(f"[dim]来源:{display_name(card.source)}[/]")
            hand_table.add_row(
                str(idx),
                card.name,
                dmg_cell,
                tt_str,
                "\n".join(detail_parts),
            )
        log.write(hand_table)

    # ──────────────────────────────────────────────
    # 实体完整信息渲染（与命令 3 一致：阵营/属性/状态效果/手牌）
    # ──────────────────────────────────────────────
    def _write_full_entities_block(
        self,
        entities: List[EntitySerialization],
        show_hand: bool = True,
        show_header: bool = True,
    ) -> None:
        """渲染每个实体的完整战斗信息，与命令 3（查看战斗状态）保持一致。"""
        log = self.query_one(RichLog)
        for entity in entities:
            faction = "[dim]未知[/]"
            is_player = any(
                c.name == PlayerComponent.__name__ for c in entity.components
            )
            for comp in entity.components:
                if comp.name == PartyMemberComponent.__name__:
                    faction = "[bold green]友方[/]"
                    break
                elif comp.name == MonsterComponent.__name__:
                    faction = "[bold red]敌方[/]"
                    break
            player_tag = r"  [bold yellow]\[玩家][/]" if is_player else ""
            if show_header:
                log.write(
                    f"[bold cyan]── {faction} [bold]{display_name(entity.name)}[/]{player_tag} ──[/]"
                )
            # 战斗属性
            stats_comp = next(
                (
                    c
                    for c in entity.components
                    if c.name == CharacterStatsComponent.__name__
                ),
                None,
            )
            if stats_comp is not None:
                equip_comp_raw = next(
                    (
                        c
                        for c in entity.components
                        if c.name == EquipmentComponent.__name__
                    ),
                    None,
                )
                inventory_comp_raw = next(
                    (
                        c
                        for c in entity.components
                        if c.name == InventoryComponent.__name__
                    ),
                    None,
                )
                status_effects_comp = next(
                    (
                        c
                        for c in entity.components
                        if c.name == StatusEffectsComponent.__name__
                    ),
                    None,
                )
                stats = compute_effective_stats(
                    CharacterStatsComponent(**stats_comp.data),
                    (
                        EquipmentComponent(**equip_comp_raw.data)
                        if equip_comp_raw is not None
                        else None
                    ),
                    (
                        InventoryComponent(**inventory_comp_raw.data)
                        if inventory_comp_raw is not None
                        else None
                    ),
                    (
                        StatusEffectsComponent(
                            **status_effects_comp.data
                        ).status_effects
                        if status_effects_comp is not None
                        else None
                    ),
                )
                log.write(
                    f"  [yellow]HP:{stats.hp}/{stats.max_hp}[/yellow]"
                    f"  [red]ATK:{stats.attack}[/red]"
                    f"  [blue]DEF:{stats.defense}[/blue]"
                    f"  [cyan]SPD:{stats.speed}[/cyan]"
                    f"  行动:{stats.energy}次/回合"
                )
            else:
                log.write("  [dim](无战斗属性)[/]")
            # 状态效果
            status_effects_comp = next(
                (
                    c
                    for c in entity.components
                    if c.name == StatusEffectsComponent.__name__
                ),
                None,
            )
            if status_effects_comp is not None:
                effects = StatusEffectsComponent(
                    **status_effects_comp.data
                ).status_effects
                if effects:
                    log.write(f"  [bold]状态效果（{len(effects)}）：[/]")
                    se_table = Table(
                        show_header=True,
                        show_lines=False,
                        box=rich_box.SIMPLE_HEAD,
                        padding=(0, 1),
                        expand=True,
                    )
                    se_table.add_column(
                        "名称", style="magenta", min_width=10, no_wrap=True
                    )
                    se_table.add_column("剩余", style="dim", width=10, no_wrap=True)
                    se_table.add_column("阶段", width=12, no_wrap=True)
                    se_table.add_column("速度", width=6, no_wrap=True)
                    se_table.add_column("防御", width=6, no_wrap=True)
                    se_table.add_column("描述", ratio=1)
                    phase_colors = {
                        "draw": "cyan",
                        "arbitration": "yellow",
                        "round_end": "red",
                    }
                    phase_labels = {
                        "draw": "抽牌",
                        "arbitration": "仲裁",
                        "round_end": "回合末",
                    }
                    for effect in effects:
                        duration_str = (
                            "永久"
                            if effect.duration == -1
                            else f"剩余{effect.duration}回合"
                        )
                        phase_color = phase_colors.get(effect.phase, "white")
                        phase_label = phase_labels.get(effect.phase, effect.phase)
                        phase_cell = f"[{phase_color}]{phase_label}[/{phase_color}]"
                        if effect.speed > 0:
                            speed_cell = f"[green]+{effect.speed}[/green]"
                        elif effect.speed < 0:
                            speed_cell = f"[red]{effect.speed}[/red]"
                        else:
                            speed_cell = "[dim]0[/dim]"
                        if effect.defense > 0:
                            defense_cell = f"[green]+{effect.defense}[/green]"
                        elif effect.defense < 0:
                            defense_cell = f"[red]{effect.defense}[/red]"
                        else:
                            defense_cell = "[dim]0[/dim]"
                        desc_cell = effect.description
                        if effect.source and effect.source != entity.name:
                            desc_cell += f"  [dim]来源:{display_name(effect.source)}[/]"
                        se_table.add_row(
                            effect.name,
                            duration_str,
                            phase_cell,
                            speed_cell,
                            defense_cell,
                            desc_cell,
                        )
                    log.write(se_table)
                else:
                    log.write("  [dim](无状态效果)[/]")
            else:
                log.write("  [dim](无状态效果)[/]")
            log.write("")
            # 抽牌堆
            draw_pile_comp = next(
                (c for c in entity.components if c.name == DrawPileComponent.__name__),
                None,
            )
            if draw_pile_comp is not None:
                draw_pile = DrawPileComponent(**draw_pile_comp.data)
                log.write(f"  [bold]抽牌堆（{len(draw_pile.cards)} 张）：[/]")
                if draw_pile.cards:
                    self._write_hand_table(draw_pile.cards, entity.name)
                else:
                    log.write("    [dim](空)[/]")
            log.write("")
            # 手牌
            if show_hand:
                hand_comp = next(
                    (c for c in entity.components if c.name == HandComponent.__name__),
                    None,
                )
                if hand_comp is not None:
                    hand = HandComponent(**hand_comp.data)
                    log.write(
                        f"  [bold]手牌（回合 {hand.round}，共 {len(hand.cards)} 张）：[/]"
                    )
                    if hand.cards:
                        self._write_hand_table(hand.cards, entity.name)
                    else:
                        log.write("    [dim](手牌为空)[/]")
                else:
                    log.write("  [dim](无手牌)[/]")
            log.write("")
