"""战斗房间 Screen（CombatRoom）"""

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Input, RichLog, Static

import asyncio

import httpx

from .combat_actor_detail import CombatActorDetailScreen
from .round_detail import RoundDetailScreen
from .utils import display_name
from .play_cards_screen import PlayCardsScreen
from .server_client import dungeon_combat_draw_cards as server_dungeon_combat_draw_cards
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
    TaskStatus,
    CharacterStatsComponent,
    StatusEffectsComponent,
    HandComponent,
    AllyComponent,
    EnemyComponent,
)


def _format_http_error(e: Exception) -> str:
    """从 httpx.HTTPStatusError 响应体提取 detail，否则返回 str(e)。"""
    if isinstance(e, httpx.HTTPStatusError):
        try:
            return str(e.response.json().get("detail", str(e)))
        except Exception:
            pass
    return str(e)


COMBAT_ROOM_MENU = """\
[bold yellow]可用操作（输入编号执行）：[/]

[bold cyan]── 查看 ──────────────────────────────────────[/]
  [bold green]1[/]  当前战斗状态    房间信息与角色属性
  [bold green]2[/]  角色详情        完整属性与状态效果
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
        self._user_name = user_name
        self._game_name = game_name

    def compose(self) -> ComposeResult:
        yield Static("", id="combat-status", markup=True)
        yield RichLog(id="room-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="room-input-row"):
            yield Static("> ", id="room-prompt")
            yield Input(placeholder="输入命令...", id="room-input")

    def on_mount(self) -> None:
        self.query_one("#combat-status", Static).update(
            "[bold cyan]战斗房间[/]  [dim]查询中...[/]"
        )
        log = self.query_one(RichLog)
        log.write(COMBAT_ROOM_MENU)
        self._fetch_status()
        self.query_one(Input).focus()

    def action_suggest_exit(self) -> None:
        log = self.query_one(RichLog)
        log.write("[yellow]请输入 8 退出战斗房间。[/]")

    @on(Input.Submitted, "#room-input")
    def handle_command(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if not cmd:
            return

        log.write(f"[dim]> {cmd}[/]")

        if cmd == "0":
            log.write(COMBAT_ROOM_MENU)

        elif cmd == "1":
            self._fetch_status()

        elif cmd == "2":
            self.app.push_screen(
                CombatActorDetailScreen(self._user_name, self._game_name)
            )

        elif cmd == "3":
            self.app.push_screen(RoundDetailScreen(self._user_name, self._game_name))

        elif cmd == "4":
            self._do_combat_init()

        elif cmd == "5":
            self._do_draw_cards()

        elif cmd == "6":
            self.app.push_screen(PlayCardsScreen(self._user_name, self._game_name))

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

            self.query_one("#combat-status", Static).update(
                f"[bold cyan]战斗房间[/]  [bold yellow]{display_name(dungeon.name)}[/]  [dim]房间 {dungeon.current_room_index + 1}/{len(dungeon.rooms)}[/]"
            )

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

            self.query_one("#combat-status", Static).update(
                f"[bold cyan]战斗房间[/]  [bold yellow]{display_name(dungeon.name)}[/]  [bold white]▶[/]  [bold green]{display_name(stage.name)}[/]  [dim]{dungeon.current_room_index + 1}/{len(dungeon.rooms)}[/]"
            )

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
                    # 阵营检测
                    faction = "[dim]未知[/]"
                    for comp in entity.components:
                        if comp.name == AllyComponent.__name__:
                            faction = "[bold green]友方[/]"
                            break
                        elif comp.name == EnemyComponent.__name__:
                            faction = "[bold red]敌方[/]"
                            break

                    # 状态效果（独立于战斗属性）
                    status_effects_comp = next(
                        (
                            c
                            for c in entity.components
                            if c.name == StatusEffectsComponent.__name__
                        ),
                        None,
                    )
                    status_effects = (
                        status_effects_comp.data.get("status_effects", [])
                        if status_effects_comp is not None
                        else []
                    )
                    effects_str = f"  状态效果:[magenta]{len(status_effects)}[/]"

                    # 手牌
                    hand_comp = next(
                        (
                            c
                            for c in entity.components
                            if c.name == HandComponent.__name__
                        ),
                        None,
                    )
                    hand_count = (
                        len(hand_comp.data.get("cards", []))
                        if hand_comp is not None
                        else 0
                    )
                    hand_str = f"  手牌:[cyan]{hand_count}[/]"

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
                        stats = stats_comp.data.get("stats", {})
                        hp = stats.get("hp", "?")
                        max_hp = stats.get("max_hp", "?")
                        attack = stats.get("attack", "?")
                        defense = stats.get("defense", "?")
                        log.write(
                            f"  · {faction} [bold]{display_name(entity.name)}[/]"
                            f"  HP:[yellow]{hp}/{max_hp}[/]"
                            f"  ATK:[red]{attack}[/]"
                            f"  DEF:[blue]{defense}[/]" + effects_str + hand_str
                        )
                    else:
                        log.write(
                            f"  · {faction} [bold]{display_name(entity.name)}[/]  [dim](无战斗属性)[/]"
                            + effects_str
                            + hand_str
                        )
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
