"""战斗房间 Screen（CombatRoom）"""

from typing import final
import httpx
from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static
from .combat_play_cards import _Phase, PlayCardsMixin
from .combat_menu import COMBAT_ROOM_MENU
from .combat_use_consumable import UseConsumableMixin
from .combat_use_gear import UseGearMixin
from .combat_room_renderer import write_full_entities_block
from .deck_detail import DeckDetailScreen
from .round_detail import RoundDetailScreen
from .utils import display_name
from .server_client import dungeon_combat_draw_cards as server_dungeon_combat_draw_cards
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
    CombatState,
)


def _format_http_error(e: Exception) -> str:
    """从 httpx.HTTPStatusError 响应体提取 detail，否则返回 str(e)。"""
    if isinstance(e, httpx.HTTPStatusError):
        try:
            return str(e.response.json().get("detail", str(e)))
        except Exception:
            pass
    return str(e)


@final
class CombatRoomScreen(PlayCardsMixin, UseConsumableMixin, UseGearMixin):
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

        # 出牌阶段状态机字段（由 PlayCardsMixin 提供）
        self._init_play_state()
        # 道具子流程状态字段（由 UseConsumableMixin / UseGearMixin 提供）
        self._init_item_state()

    @property
    def _user_name(self) -> str:
        assert self.game_client.session is not None
        return self.game_client.session.user_name

    @property
    def _game_name(self) -> str:
        assert self.game_client.session is not None
        return self.game_client.session.game_name

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
        log.write("[dim]输入 [bold]6[/] 查看当前战斗状态。[/]")
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
                    _Phase.ROUND_DONE,
                    _Phase.SELECT_CONSUMABLE,
                    _Phase.SELECT_CONSUMABLE_TARGET,
                ):
                    self._return_to_menu()
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
            elif self._phase == _Phase.SELECT_TARGET:
                self._handle_target_selection(raw)
            elif self._phase == _Phase.ROUND_DONE:
                self._confirm_round_done()
            elif self._phase == _Phase.SELECT_CONSUMABLE:
                self._phase = _Phase.LOADING
                self.query_one(Input).disabled = True
                self._handle_consumable_selection(raw)
            elif self._phase == _Phase.SELECT_CONSUMABLE_TARGET:
                self._handle_consumable_target_selection(raw)
            elif self._phase == _Phase.SELECT_GEAR:
                self._phase = _Phase.LOADING
                self.query_one(Input).disabled = True
                self._handle_gear_selection(raw)
            elif self._phase == _Phase.SELECT_GEAR_TARGET:
                self._handle_gear_target_selection(raw)
            return

        # ── 普通命令模式 ──
        cmd = raw
        if not cmd:
            return

        # 每次执行任意命令前先清空 Log 并重印菜单
        # 出牌（3）、消耗品（4）、装备（5）命令进入专属 UI，自行处理 log 初始化，不在此预写菜单
        if cmd not in ("3", "4", "5"):
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
            self._start_use_consumable()

        elif cmd == "5":
            self._start_use_gear()

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

            # Step B：从 stages state 取该场景的运行时 actor 名单
            stages_resp = await fetch_stages_state(self._user_name, self._game_name)
            actor_names = stages_resp.mapping.get(stage.name, [])

            # Step C：逐实体获取运行时 ECS 组件数据
            entities_serialization = []
            if actor_names:
                details_resp = await fetch_entities_details(
                    self._user_name, self._game_name, actor_names
                )
                entities_serialization = details_resp.entities_serialization

            # ── 1. 战斗摘要（宏观信息）──
            log.write(
                "[bold cyan]── 战斗摘要 ──────────────────────────────────────[/]"
            )
            log.write(
                f"  [bold]战斗状态：[/] {combat.state.name}  "
                f"[bold]战斗结果：[/] {combat.result.name}  "
                f"[bold]当前局数：[/] {len(combat.rounds)}"
            )
            action_order = []
            if combat.rounds:
                cur = combat.rounds[-1]
                snapshot = (
                    cur.actor_order_snapshots[-1] if cur.actor_order_snapshots else []
                )
                action_order = list(snapshot)
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

            # ── 分割线 ──
            log.write(
                "[bold cyan]══════════════════════════════════════════════════[/]"
            )
            log.write("")

            # ── 2. 逐个参战单位详情（按行动顺序排列）──
            log.write(
                "[bold cyan]── 参战角色 ──────────────────────────────────────[/]"
            )
            log.write("")
            if entities_serialization:
                entity_map = {e.name: e for e in entities_serialization}
                ordered_names = action_order + [
                    n for n in actor_names if n not in action_order
                ]
                for name in ordered_names:
                    entity = entity_map.get(name)
                    if entity is None:
                        continue
                    write_full_entities_block(log, [entity])
                    log.write(
                        "[dim]──────────────────────────────────────────────────[/]"
                    )
                    log.write("")
            else:
                log.write("  [dim]（房间内无角色）[/]")
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
            log.write(
                "[dim]输入 [bold]6[/] 查看当前战斗状态，输入 [bold]2[/] 开始抽牌。[/]"
            )

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
