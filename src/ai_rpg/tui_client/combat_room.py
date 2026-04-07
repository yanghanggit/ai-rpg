"""战斗房间 Screen（CombatRoom）"""

import asyncio
from enum import auto, Enum
from typing import Dict, Final, List, Optional, final
import httpx
from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Input, RichLog, Static
from .round_detail import RoundDetailScreen
from .utils import display_name
from .server_client import dungeon_combat_draw_cards as server_dungeon_combat_draw_cards
from .server_client import dungeon_combat_play_cards as server_play_cards
from .server_client import dungeon_combat_init as server_dungeon_combat_init
from .server_client import dungeon_combat_retreat as server_dungeon_combat_retreat
from .server_client import dungeon_exit as server_dungeon_exit
from .server_client import fetch_dungeon_room, fetch_dungeon_state
from .server_client import (
    fetch_entities_details,
    fetch_stages_state,
    fetch_tasks_status,
)
from ..models import (
    Card,
    TaskStatus,
    CharacterStatsComponent,
    StatusEffectsComponent,
    HandComponent,
    AllyComponent,
    EnemyComponent,
    PlayerComponent,
)


# ─────────────────────────────────────────────────
# 出牌状态机枚举
# ─────────────────────────────────────────────────
class _Phase(Enum):
    LOADING = auto()  # 初始加载回合信息
    ENEMY_TURN = auto()  # 等待用户按 Enter 触发敌人 AI
    SELECT_CARD = auto()  # 等待用户输入卡牌编号
    SELECT_TARGET = auto()  # 等待用户输入目标编号
    WAITING = auto()  # 正在等待后端任务完成
    ROUND_DONE = auto()  # 回合已全部完成


_PLAY_POLL_INTERVAL: Final[float] = 1.0
_PLAY_MAX_POLLS: Final[int] = 90


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

[bold cyan]── 查看 ──────────────────────────────────────[/]
  [bold green]1[/]  当前战斗状态    房间信息与角色属性
  [bold green]3[/]  回合详情        行动顺序与出手记录

[bold cyan]── 战斗 ──────────────────────────────────────[/]
  [bold green]4[/]  初始化战斗      INITIALIZING → ONGOING
  [bold green]5[/]  全员抽牌        为所有战斗角色激活抽牌
  [bold green]6[/]  出牌            进入出牌界面完成本回合
  [bold green]7[/]  撤退            在战斗进行中撤退

[bold cyan]── 系统 ──────────────────────────────────────[/]
  [bold green]0[/]  显示此菜单
  [bold green]8[/]  退出战斗        返回游戏主场景
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

    def __init__(self, user_name: str, game_name: str) -> None:
        super().__init__()
        self._user_name: Final[str] = user_name
        self._game_name: Final[str] = game_name

        # 顶部状态栏文本缓存（由 _fetch_status 写入，其他地方只读不写）
        self._status_bar_text: str = "[bold cyan]战斗房间[/]  [dim]查询中...[/]"

        # 出牌阶段状态机字段（None = 普通命令模式）
        self._phase: Optional[_Phase] = None
        self._pending_actor_name: Optional[str] = None
        self._pending_card_name: Optional[str] = None
        self._pending_hand_cards: List[Card] = []
        self._pending_alive_enemies: List[str] = []
        self._pending_alive_allies: List[str] = []
        self._pending_target_candidates: List[str] = []

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
        log.write("[yellow]请输入 8 退出战斗房间。[/]")

    @on(Input.Submitted, "#room-input")
    def handle_command(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        # ── 出牌模式：路由至状态机处理器 ──
        if self._phase is not None:
            if self._phase == _Phase.ENEMY_TURN:
                self._trigger_enemy_turn()
            elif self._phase == _Phase.SELECT_CARD:
                self._handle_card_selection(raw)
            elif self._phase == _Phase.SELECT_TARGET:
                self._handle_target_selection(raw)
            elif self._phase == _Phase.ROUND_DONE:
                log.write("[dim]回合已结束，请等待...[/]")
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
            self._fetch_status()

        elif cmd == "3":
            self.app.push_screen(RoundDetailScreen(self._user_name, self._game_name))

        elif cmd == "4":
            self._do_combat_init()

        elif cmd == "5":
            self._do_draw_cards()

        elif cmd == "6":
            self._start_play_cards()

        elif cmd == "7":
            self._do_combat_retreat()

        elif cmd == "8":
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
                for entity in details_resp.entities_serialization:
                    # 阵营检测 + 玩家标记
                    faction = "[dim]未知[/]"
                    is_player = any(
                        c.name == PlayerComponent.__name__ for c in entity.components
                    )
                    for comp in entity.components:
                        if comp.name == AllyComponent.__name__:
                            faction = "[bold green]友方[/]"
                            break
                        elif comp.name == EnemyComponent.__name__:
                            faction = "[bold red]敌方[/]"
                            break

                    player_tag = r"  [bold yellow]\[玩家][/]" if is_player else ""
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
                        stats = CharacterStatsComponent(**stats_comp.data).stats
                        log.write(
                            f"  HP:[yellow]{stats.hp}/{stats.max_hp}[/]"
                            f"  ATK:[red]{stats.attack}[/]"
                            f"  DEF:[blue]{stats.defense}[/]"
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
                            for effect in effects:
                                log.write(
                                    f"    └ [magenta]{effect.name}[/]"
                                    f"  [{effect.category}]  {effect.description}"
                                )
                        else:
                            log.write("  [dim](无状态效果)[/]")
                    else:
                        log.write("  [dim](无状态效果)[/]")

                    # 手牌
                    hand_comp = next(
                        (
                            c
                            for c in entity.components
                            if c.name == HandComponent.__name__
                        ),
                        None,
                    )
                    if hand_comp is not None:
                        hand = HandComponent(**hand_comp.data)
                        log.write(
                            f"  [bold]手牌（回合 {hand.round}，共 {len(hand.cards)} 张）：[/]"
                        )
                        if hand.cards:
                            for card in hand.cards:
                                hit_str = (
                                    f"x[yellow]{card.hit_count}[/]"
                                    if card.hit_count > 1
                                    else ""
                                )
                                tt_str = _TARGET_LABEL.get(
                                    card.target_type,
                                    f"[dim]{card.target_type}[/]",
                                )
                                log.write(
                                    f"    └ [bold]{card.name}[/]"
                                    f"  伤害:[red]{card.damage_dealt}[/]{hit_str}"
                                    f"  格挡:[blue]{card.block_gain}[/]"
                                    f"  目标:{tt_str}"
                                    + (
                                        f"  [dim]{card.action}[/]"
                                        if card.action
                                        else ""
                                    )
                                )
                        else:
                            log.write("    [dim](手牌为空)[/]")

                    log.write("")
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
                order_str = (
                    " => ".join(display_name(a) for a in cur.action_order)
                    if cur.action_order
                    else "[dim]（无）[/]"
                )
                done_str = (
                    "  ".join(display_name(a) for a in cur.completed_actors)
                    if cur.completed_actors
                    else "[dim]（无）[/]"
                )
                log.write(f"  [bold]行动顺序：[/] {order_str}")
                log.write(f"  [bold]已出手：[/]   {done_str}")
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
    async def _do_combat_init(self) -> None:
        """触发战斗初始化（INITIALIZING → ONGOING），轮询任务完成后刷新状态。"""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        log.write("[dim]▶ 正在初始化战斗...[/]")
        logger.info(
            f"CombatRoomScreen._do_combat_init: user={self._user_name} game={self._game_name}"
        )

        task_id = ""
        try:
            resp = await server_dungeon_combat_init(self._user_name, self._game_name)
            task_id = resp.task_id
            log.write(f"[dim]任务已创建：{task_id}[/]")
            logger.info(f"_do_combat_init: 任务已创建 task_id={task_id}")
        except Exception as e:
            logger.error(f"_do_combat_init: 请求失败 error={e}")
            log.write(f"[bold red]❌ 战斗初始化请求失败: {_format_http_error(e)}[/]")
            inp.disabled = False
            inp.focus()
            return

        _POLL_INTERVAL = 1.0
        _MAX_POLLS = 60
        for _ in range(_MAX_POLLS):
            await asyncio.sleep(_POLL_INTERVAL)
            try:
                status_resp = await fetch_tasks_status([task_id])
                if not status_resp.tasks:
                    continue
                record = status_resp.tasks[0]
                if record.status == TaskStatus.COMPLETED:
                    log.write("[bold green]✅ 战斗初始化完成[/]")
                    logger.info(f"_do_combat_init: 任务完成 task_id={task_id}")
                    break
                elif record.status == TaskStatus.FAILED:
                    error_msg = record.error or "未知错误"
                    log.write(f"[bold red]❌ 战斗初始化失败: {error_msg}[/]")
                    logger.error(
                        f"_do_combat_init: 任务失败 task_id={task_id} error={error_msg}"
                    )
                    break
            except Exception as e:
                logger.warning(f"_do_combat_init: 轮询失败 error={e}")
        else:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(f"_do_combat_init: 轮询超时 task_id={task_id}")

        inp.disabled = False
        inp.focus()
        self._fetch_status()

    @work
    async def _do_draw_cards(self) -> None:
        """为全体战斗角色激活抽牌动作，轮询任务完成后刷新状态。"""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        log.write("[dim]▶ 正在激活全员抽牌...[/]")
        logger.info(
            f"CombatRoomScreen._do_draw_cards: user={self._user_name} game={self._game_name}"
        )

        task_id = ""
        try:
            resp = await server_dungeon_combat_draw_cards(
                self._user_name, self._game_name
            )
            task_id = resp.task_id
            log.write(f"[dim]任务已创建：{task_id}[/]")
            logger.info(f"_do_draw_cards: 任务已创建 task_id={task_id}")
        except Exception as e:
            logger.error(f"_do_draw_cards: 请求失败 error={e}")
            log.write(f"[bold red]❌ 全员抽牌请求失败: {_format_http_error(e)}[/]")
            inp.disabled = False
            inp.focus()
            return

        _POLL_INTERVAL = 1.0
        _MAX_POLLS = 60
        for _ in range(_MAX_POLLS):
            await asyncio.sleep(_POLL_INTERVAL)
            try:
                status_resp = await fetch_tasks_status([task_id])
                if not status_resp.tasks:
                    continue
                record = status_resp.tasks[0]
                if record.status == TaskStatus.COMPLETED:
                    log.write("[bold green]✅ 全员抽牌完成[/]")
                    logger.info(f"_do_draw_cards: 任务完成 task_id={task_id}")
                    break
                elif record.status == TaskStatus.FAILED:
                    error_msg = record.error or "未知错误"
                    log.write(f"[bold red]❌ 全员抽牌失败: {error_msg}[/]")
                    logger.error(
                        f"_do_draw_cards: 任务失败 task_id={task_id} error={error_msg}"
                    )
                    break
            except Exception as e:
                logger.warning(f"_do_draw_cards: 轮询失败 error={e}")
        else:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(f"_do_draw_cards: 轮询超时 task_id={task_id}")

        inp.disabled = False
        inp.focus()
        self._fetch_status()

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

        _POLL_INTERVAL = 1.0
        _MAX_POLLS = 60
        for _ in range(_MAX_POLLS):
            await asyncio.sleep(_POLL_INTERVAL)
            try:
                status_resp = await fetch_tasks_status([task_id])
                if not status_resp.tasks:
                    continue
                record = status_resp.tasks[0]
                if record.status == TaskStatus.COMPLETED:
                    log.write("[bold green]✅ 撤退成功[/]")
                    logger.info(f"_do_combat_retreat: 任务完成 task_id={task_id}")
                    break
                elif record.status == TaskStatus.FAILED:
                    error_msg = record.error or "未知错误"
                    log.write(f"[bold red]❌ 撤退失败: {error_msg}[/]")
                    logger.error(
                        f"_do_combat_retreat: 任务失败 task_id={task_id} error={error_msg}"
                    )
                    break
            except Exception as e:
                logger.warning(f"_do_combat_retreat: 轮询失败 error={e}")
        else:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(f"_do_combat_retreat: 轮询超时 task_id={task_id}")

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
        """进入出牌模式：打印标题后启动 _load_round。"""
        log = self.query_one(RichLog)
        log.write(
            "\n[bold cyan]── 出牌阶段 ─────────────────────────────────────────[/]\n"
            "  逐步完成当前回合所有角色的出牌。\n"
        )
        inp = self.query_one(Input)
        inp.disabled = True
        self._phase = _Phase.LOADING
        self._load_round()

    # ──────────────────────────────────────────────
    # 加载回合信息
    # ──────────────────────────────────────────────
    @work
    async def _load_round(self) -> None:
        log = self.query_one(RichLog)
        log.write("[dim]正在加载回合信息...[/]")
        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            combat = room_resp.room.combat
            rounds = combat.rounds

            if not rounds:
                log.write("[yellow]⚠ 当前没有进行中的回合，请先抽牌。[/]")
                self._phase = None
                self._update_play_status("无活跃回合")
                self.query_one(Input).disabled = False
                self.query_one(Input).focus()
                return

            cur = rounds[-1]
            action_order = list(cur.action_order)
            completed_actors = list(cur.completed_actors)
            stage_name = room_resp.room.stage.name

            enemy_names = await self._fetch_play_enemy_names(stage_name)

            log.write(
                f"[bold yellow]回合 {len(rounds)}[/]  "
                f"行动序列：{' → '.join(action_order)}\n"
                f"已出手：{', '.join(completed_actors) if completed_actors else '（无）'}\n"
            )
            logger.info(
                f"CombatRoomScreen._load_round: action_order={action_order} "
                f"completed={completed_actors} enemies={enemy_names}"
            )
        except Exception as e:
            logger.error(f"CombatRoomScreen._load_round: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载回合信息失败: {e}[/]")
            self._phase = None
            self._update_play_status("加载失败")
            self.query_one(Input).disabled = False
            self.query_one(Input).focus()
            return

        self._advance_to_next_actor(cur.current_actor, enemy_names)

    # ──────────────────────────────────────────────
    # 状态机推进
    # ──────────────────────────────────────────────
    def _advance_to_next_actor(
        self,
        current_actor: Optional[str],
        enemy_names: List[str],
    ) -> None:
        if current_actor is None:
            self._enter_round_done()
            return
        if current_actor in enemy_names:
            self._enter_enemy_turn(current_actor)
        else:
            self._enter_select_card(current_actor)

    def _enter_enemy_turn(self, actor_name: str) -> None:
        log = self.query_one(RichLog)
        short = actor_name.split(".")[-1]
        log.write(
            f"[bold red]── 敌人回合：{short} ──────────────────────────────────[/]"
        )
        log.write("  按 [bold]Enter[/] 触发 AI 决策...")
        self._pending_actor_name = actor_name
        self._phase = _Phase.ENEMY_TURN
        self._update_play_status(f"敌人 [{short}] 的回合 — 按 Enter 触发 AI 出牌")
        inp = self.query_one(Input)
        inp.disabled = False
        inp.focus()

    def _enter_select_card(self, actor_name: str) -> None:
        log = self.query_one(RichLog)
        short = actor_name.split(".")[-1]
        log.write(
            f"[bold green]── 你的回合：{short} ────────────────────────────────[/]"
        )
        self._pending_actor_name = actor_name
        self._fetch_hand_and_show(actor_name)

    def _enter_round_done(self) -> None:
        log = self.query_one(RichLog)
        self._phase = None
        inp = self.query_one(Input)
        inp.placeholder = "输入命令..."
        inp.disabled = False
        inp.focus()
        # 回合结束后清空 log，重显菜单并附加结束提示
        log.clear()
        log.write(COMBAT_ROOM_MENU)
        log.write("[bold green]✅ 本回合所有角色已出手，回合结束。[/]\n")

    # ──────────────────────────────────────────────
    # 敌方名单辅助（通过 EnemyComponent）
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
            if any(c.name == "EnemyComponent" for c in e.components)
        ]

    # ──────────────────────────────────────────────
    # 手牌加载与显示
    # ──────────────────────────────────────────────
    @work
    async def _fetch_hand_and_show(self, actor_name: str) -> None:
        log = self.query_one(RichLog)
        log.write("[dim]正在加载手牌...[/]")
        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            stage_name = room_resp.room.stage.name
            combat = room_resp.room.combat
            cur_round = combat.rounds[-1] if combat.rounds else None

            stages_resp = await fetch_stages_state(self._user_name, self._game_name)
            stage_actor_names: List[str] = list(stages_resp.mapping.get(stage_name, []))
            if actor_name not in stage_actor_names:
                stage_actor_names.append(actor_name)

            all_details = await fetch_entities_details(
                self._user_name, self._game_name, stage_actor_names
            )

            hand_cards: List[Card] = []
            alive_enemies: List[str] = []
            alive_allies: List[str] = []
            for entity in all_details.entities_serialization:
                comp_names = {c.name for c in entity.components}
                if "EnemyComponent" in comp_names:
                    alive_enemies.append(entity.name)
                elif "ExpeditionMemberComponent" in comp_names:
                    alive_allies.append(entity.name)
                if entity.name == actor_name:
                    for comp in entity.components:
                        if comp.name == "HandComponent":
                            hand_cards = HandComponent(**comp.data).cards

        except Exception as e:
            logger.error(f"CombatRoomScreen._fetch_hand_and_show: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载手牌失败: {e}[/]")
            self._phase = None
            self._update_play_status("加载失败")
            self.query_one(Input).disabled = False
            self.query_one(Input).focus()
            return

        if not hand_cards:
            log.write("[yellow]⚠ 该角色没有手牌，跳过出牌。[/]")
            self._advance_to_next_actor(
                cur_round.current_actor if cur_round else None, alive_enemies
            )
            return

        self._pending_hand_cards = hand_cards
        self._pending_alive_enemies = alive_enemies
        self._pending_alive_allies = alive_allies

        log.write("  [bold]手牌：[/]")
        for i, card in enumerate(hand_cards, 1):
            hit_str = f"x[yellow]{card.hit_count}[/]" if card.hit_count > 1 else ""
            tt_str = _TARGET_LABEL.get(card.target_type, f"[dim]{card.target_type}[/]")
            log.write(
                f"    [bold cyan]{i}.[/] {card.name}  "
                f"伤害:[red]{card.damage_dealt}[/]{hit_str}  格挡:[blue]{card.block_gain}[/]  目标:{tt_str}"
            )

        self._phase = _Phase.SELECT_CARD
        short = actor_name.split(".")[-1]
        self._update_play_status(f"[{short}] 输入卡牌编号（1-{len(hand_cards)}）选牌")
        inp = self.query_one(Input)
        inp.placeholder = f"1-{len(hand_cards)} 或卡牌名"
        inp.disabled = False
        inp.focus()

    # ──────────────────────────────────────────────
    # 卡牌选择
    # ──────────────────────────────────────────────
    def _handle_card_selection(self, raw: str) -> None:
        log = self.query_one(RichLog)
        if not self._pending_hand_cards:
            log.write("[red]没有可用手牌。[/]")
            return

        card: Optional[Card] = None
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(self._pending_hand_cards):
                card = self._pending_hand_cards[idx]
        else:
            for c in self._pending_hand_cards:
                if c.name == raw:
                    card = c
                    break

        if card is None:
            log.write(
                f"[red]无效输入 '{raw}'，请输入 1-{len(self._pending_hand_cards)} 的数字或卡牌名称。[/]"
            )
            return

        self._pending_card_name = card.name
        target_type = card.target_type
        log.write(f"  已选：[bold cyan]{self._pending_card_name}[/]")

        if target_type == "enemy_all":
            log.write("  [dim]此卡自动命中所有存活敌方[/]")
            self._submit_play_card(targets=[])
        elif target_type == "ally_all":
            log.write("  [dim]此卡自动命中所有存活友方[/]")
            self._submit_play_card(targets=[])
        elif target_type == "self_only":
            log.write("  [dim]此卡仅作用于自身[/]")
            self._submit_play_card(targets=[])
        elif target_type == "ally_single":
            candidates = self._pending_alive_allies
            if candidates:
                log.write("  [bold]可选友方目标：[/]")
                for i, name in enumerate(candidates, 1):
                    log.write(f"    [bold cyan]{i}.[/] {name.split('.')[-1]}  ({name})")
                self._pending_target_candidates = list(candidates)
                self._phase = _Phase.SELECT_TARGET
                self._update_play_status(
                    f"输入目标编号（1-{len(candidates)}），或直接 Enter 跳过"
                )
                inp = self.query_one(Input)
                inp.placeholder = "编号或 Enter 跳过"
                inp.focus()
            else:
                log.write("  [dim]无存活友方，直接出牌[/]")
                self._submit_play_card(targets=[])
        else:  # enemy_single（默认）
            candidates = self._pending_alive_enemies
            if candidates:
                log.write("  [bold]可用目标：[/]")
                for i, name in enumerate(candidates, 1):
                    log.write(f"    [bold cyan]{i}.[/] {name.split('.')[-1]}  ({name})")
                self._pending_target_candidates = list(candidates)
                self._phase = _Phase.SELECT_TARGET
                self._update_play_status(
                    f"输入目标编号（1-{len(candidates)}），或直接 Enter 跳过"
                )
                inp = self.query_one(Input)
                inp.placeholder = "编号或 Enter 跳过"
                inp.focus()
            else:
                log.write("  [dim]无存活敌人，直接出牌[/]")
                self._submit_play_card(targets=[])

    # ──────────────────────────────────────────────
    # 目标选择
    # ──────────────────────────────────────────────
    def _handle_target_selection(self, raw: str) -> None:
        log = self.query_one(RichLog)
        targets: List[str] = []

        if raw == "":
            log.write("  [dim]无目标[/]")
        else:
            candidates = self._pending_target_candidates
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
                matched = [n for n in candidates if n == raw or n.split(".")[-1] == raw]
                if matched:
                    targets = [matched[0]]
                else:
                    log.write(f"[red]找不到目标 '{raw}'，请重新输入。[/]")
                    return

        self._submit_play_card(targets=targets)

    # ──────────────────────────────────────────────
    # 出牌提交（玩家）
    # ──────────────────────────────────────────────
    def _submit_play_card(self, targets: List[str]) -> None:
        assert self._pending_actor_name is not None
        assert self._pending_card_name is not None
        self._do_play_card(self._pending_actor_name, self._pending_card_name, targets)
        self._pending_card_name = None
        self._pending_hand_cards = []
        self._pending_alive_enemies = []
        self._pending_alive_allies = []
        self._pending_target_candidates = []

    # ──────────────────────────────────────────────
    # 敌人出牌触发
    # ──────────────────────────────────────────────
    def _trigger_enemy_turn(self) -> None:
        assert self._pending_actor_name is not None
        self._do_play_card(self._pending_actor_name, "", [])

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

        short = actor_name.split(".")[-1]
        display_card = card_name if card_name else "（AI 自选）"
        log.write(
            f"  [dim]▶ {short} 出牌中：{display_card}  "
            f"目标：{[t.split('.')[-1] for t in targets] or '无'}[/]"
        )
        logger.info(
            f"CombatRoomScreen._do_play_card: actor={actor_name} card={card_name} targets={targets}"
        )

        prev_round_idx = -1
        prev_completed_count = 0
        try:
            pre_room = await fetch_dungeon_room(self._user_name, self._game_name)
            pre_rounds = pre_room.room.combat.rounds
            if pre_rounds:
                prev_round_idx = len(pre_rounds) - 1
                prev_completed_count = len(pre_rounds[-1].completed_actors)
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
            await self._reload_and_advance()
            return
        except Exception as e:
            log.write(f"[bold red]❌ 出牌请求失败: {e}[/]")
            logger.error(f"_do_play_card: 请求失败 error={e}")
            await self._reload_and_advance()
            return

        self._update_play_status(f"等待 {short} 出牌完成...")
        for _ in range(_PLAY_MAX_POLLS):
            await asyncio.sleep(_PLAY_POLL_INTERVAL)
            try:
                status_resp = await fetch_tasks_status([task_id])
                if not status_resp.tasks:
                    continue
                record = status_resp.tasks[0]
                if record.status == TaskStatus.COMPLETED:
                    log.write(f"  [green]✓ {short} 出牌完成[/]")
                    logger.info(f"_do_play_card: 任务完成 task_id={task_id}")
                    break
                elif record.status == TaskStatus.FAILED:
                    error_msg = record.error or "未知错误"
                    log.write(f"[bold red]❌ {short} 出牌失败: {error_msg}[/]")
                    logger.error(
                        f"_do_play_card: 任务失败 task_id={task_id} error={error_msg}"
                    )
                    break
            except Exception as e:
                logger.warning(f"_do_play_card: 轮询失败 error={e}")
        else:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(f"_do_play_card: 轮询超时 task_id={task_id}")

        await self._show_play_results(prev_round_idx, prev_completed_count)
        await self._reload_and_advance()

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
    # 出牌后：重新拉取状态并推进状态机
    # ──────────────────────────────────────────────
    async def _reload_and_advance(self) -> None:
        try:
            room_resp = await fetch_dungeon_room(self._user_name, self._game_name)
            combat = room_resp.room.combat
            cur = combat.rounds[-1] if combat.rounds else None
            stage_name = room_resp.room.stage.name
            enemy_names = await self._fetch_play_enemy_names(stage_name)
        except Exception as e:
            logger.warning(f"_reload_and_advance: 刷新回合状态失败 error={e}")
            self._enter_round_done()
            return
        self._advance_to_next_actor(cur.current_actor if cur else None, enemy_names)

    # ──────────────────────────────────────────────
    # 出牌阶段提示（写入 log，不修改顶部状态栏）
    # ──────────────────────────────────────────────
    def _update_play_status(self, text: str) -> None:
        if text:
            log = self.query_one(RichLog)
            log.write(f"[dim]{text}[/]")
