"""游戏主场景 Screen（Home 状态）"""

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Input, RichLog, Static

import asyncio

from loguru import logger
import json

from .server_client import (
    fetch_entities_details,
    fetch_session_messages,
    fetch_stages_state,
    fetch_tasks_status,
    home_advance as server_home_advance,
    logout as server_logout,
)
from ..models.session_message import MessageType
from ..models.task import TaskStatus
from ..models.agent_event import EventHead

HOME_HEADER = """\
[bold cyan]╔══════════════════════════════════════════════════╗[/]
[bold cyan]║        AI RPG TCG  游戏主场景                   ║[/]
[bold cyan]╚══════════════════════════════════════════════════╝[/]
"""

HELP_TEXT = """\
[bold yellow]可用命令：[/]

  [bold green]/help            [/]  显示此帮助信息
  [bold green]/status          [/]  显示玩家状态、世界设定及玩家角色详情
  [bold green]/stages          [/]  查询全部场景与角色分布
  [bold green]/stage_desc      [/]  显示玩家当前所在场景的描述
  [bold green]/entities        [/]  打开实体浏览器（列出全部场景与角色）
  [bold green]/dungeon_overview [/]  打开地下城总览（列出全部副本预览）
  [bold green]/advance         [/]  推进家园流程（执行一轮 home pipeline）
  [bold green]/speak           [/]  与当前场景 NPC 对话
  [bold green]/switch_stage    [/]  切换到其他场景
  [bold green]/logout          [/]  登出并返回主菜单

"""


def _format_agent_event(data: dict) -> str:  # type: ignore[type-arg]
    """将 AGENT_EVENT 的 data dict 渲染为 Rich markup 字符串。"""
    head = data.get("head", EventHead.NONE)
    try:
        head = EventHead(head)
    except ValueError:
        head = EventHead.NONE

    match head:
        case EventHead.SPEAK_EVENT:
            actor = data.get("actor", "?")
            target = data.get("target", "?")
            content = data.get("content", "")
            return (
                f"[bold yellow]{actor}[/] 对 [yellow]{target}[/] 说：\n"
                f"  「{content}」"
            )
        case EventHead.WHISPER_EVENT:
            actor = data.get("actor", "?")
            target = data.get("target", "?")
            content = data.get("content", "")
            return f"[dim]{actor} 悄悄向 {target} 耳语：「{content}」[/]"
        case EventHead.ANNOUNCE_EVENT:
            actor = data.get("actor", "?")
            stage = data.get("stage", "?")
            content = data.get("content", "")
            return f"[bold magenta]【{actor}】[/] 在 {stage} 宣告：{content}"
        case EventHead.MIND_EVENT:
            actor = data.get("actor", "?")
            content = data.get("content", "")
            return f"[dim italic]（{actor} 心想：{content}）[/]"
        case EventHead.QUERY_EVENT:
            actor = data.get("actor", "?")
            question = data.get("question", "")
            return f"[dim]{actor} 询问：{question}[/]"
        case EventHead.TRANS_STAGE_EVENT:
            actor = data.get("actor", "?")
            from_stage = data.get("from_stage", "?")
            to_stage = data.get("to_stage", "?")
            return f"[cyan]▶ {actor}  {from_stage} → {to_stage}[/]"
        case EventHead.COMBAT_INITIATION_EVENT:
            actor = data.get("actor", "?")
            return f"[bold red]⚔ {actor} 发起战斗！[/]"
        case EventHead.COMBAT_ARBITRATION_EVENT:
            narrative = data.get("narrative", data.get("message", ""))
            return f"[bold]{narrative}[/]"
        case EventHead.COMBAT_ARCHIVE_EVENT:
            actor = data.get("actor", "?")
            summary = data.get("summary", "")
            return f"[dim]{actor} 战斗归档：{summary}[/]"
        case _:
            return f"[dim cyan]{data.get('message', '')}[/]"


class HomeScreen(Screen[None]):
    """游戏主场景 Screen（Screen 3）。新游戏创建成功后进入此界面。"""

    CSS = """
    HomeScreen {
        align: center middle;
    }

    #home-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #home-input-row {
        height: 3;
        dock: bottom;
    }

    #home-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #home-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("ctrl+c", "app.quit", "Quit"),
    ]

    def __init__(self, user_name: str, game_name: str) -> None:
        super().__init__()
        self._user_name = user_name
        self._game_name = game_name
        self._last_sequence_id: int = 0
        self._polling_active: bool = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield RichLog(id="home-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="home-input-row"):
            yield Static("> ", id="home-prompt")
            yield Input(placeholder="输入命令...", id="home-input")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(HOME_HEADER)
        log.write(HELP_TEXT)
        logger.info(
            f"HomeScreen: 进入主场景 user_name={self._user_name} game_name={self._game_name}"
        )
        self.query_one(Input).focus()
        self._polling_active = True
        self._poll_messages()
        self._show_player_status()

    def on_unmount(self) -> None:
        self._polling_active = False
        logger.info(f"HomeScreen: on_unmount，停止轮询 user_name={self._user_name}")

    @work
    async def _show_player_status(self) -> None:
        """进入主场景时，显示玩家角色及其当前所在场景。"""
        log = self.query_one(RichLog)
        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        bp = app.session_blueprint
        player_actor = bp.player_actor if bp else None

        if not player_actor:
            log.write("[dim]玩家角色信息暂不可用。[/]")
            return

        current_stage = "[dim]（查询中...）[/]"
        try:
            resp = await fetch_stages_state(self._user_name, self._game_name)
            for stage, actors in resp.mapping.items():
                if player_actor in actors:
                    current_stage = stage
                    break
            else:
                current_stage = "[dim]（未知场景）[/]"
        except Exception as e:
            logger.warning(f"_show_player_status: 查询场景失败 error={e}")
            current_stage = "[dim]（查询失败）[/]"

        log.write(
            f"[bold green]▶ 玩家角色：[bold cyan]{player_actor}[/][bold green]"
            f"  当前场景：[bold yellow]{current_stage}[/]"
        )

    @on(Input.Submitted, "#home-input")
    def handle_command(self, event: Input.Submitted) -> None:
        cmd = event.value.strip().lower()
        event.input.clear()
        log = self.query_one(RichLog)

        if not cmd:
            return

        log.write(f"[dim]> {cmd}[/]")
        logger.debug(f"HomeScreen: 收到命令 user_name={self._user_name} cmd={cmd}")

        if cmd == "/help":
            log.write(HELP_TEXT)
        elif cmd == "/status":
            self._fetch_status()
        elif cmd == "/stages":
            self._fetch_stages()
        elif cmd == "/stage_desc":
            self._fetch_stage_desc()
        elif cmd == "/entities":
            from .entity_browser import EntityBrowserScreen

            self.app.push_screen(
                EntityBrowserScreen(
                    user_name=self._user_name, game_name=self._game_name
                )
            )
        elif cmd == "/dungeon_overview":
            from .dungeon_overview import DungeonOverviewScreen

            self.app.push_screen(
                DungeonOverviewScreen(
                    user_name=self._user_name, game_name=self._game_name
                )
            )
        elif cmd == "/logout":
            self._do_logout()
        elif cmd == "/advance":
            self._do_advance()
        elif cmd == "/speak":
            from .speak import SpeakScreen

            self.app.push_screen(
                SpeakScreen(user_name=self._user_name, game_name=self._game_name)
            )
        elif cmd == "/switch_stage":
            from .switch_stage import SwitchStageScreen

            self.app.push_screen(
                SwitchStageScreen(user_name=self._user_name, game_name=self._game_name)
            )
        else:
            log.write(f"[red]未知命令：{cmd}，输入 /help 查看可用命令。[/]")

    @work
    async def _do_advance(self) -> None:
        """执行一轮家园推进（home pipeline），推进期间禁用输入框并轮询任务状态。"""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True
        log.write("[bold yellow]── 推进家园 ──────────────────────────────────────[/]")
        log.write("[dim]▶ 正在推进...[/]")
        logger.info(
            f"_do_advance: 开始推进 user_name={self._user_name} game_name={self._game_name}"
        )

        task_id: str = ""
        success = False
        try:
            resp = await server_home_advance(self._user_name, self._game_name)
            task_id = resp.task_id
            log.write(f"[dim]任务已创建：{task_id}[/]")
            logger.info(f"_do_advance: 任务已创建 task_id={task_id}")
        except Exception as e:
            logger.error(f"_do_advance: 触发推进失败 error={e}")
            log.write(f"[bold red]❌ 推进请求失败: {e}[/]")
            inp.disabled = False
            inp.focus()
            return

        # 轮询任务状态（最多 120 秒）
        _POLL_INTERVAL = 1.0
        _MAX_POLLS = 120
        for _ in range(_MAX_POLLS):
            await asyncio.sleep(_POLL_INTERVAL)
            try:
                status_resp = await fetch_tasks_status([task_id])
                if not status_resp.tasks:
                    continue
                task_record = status_resp.tasks[0]
                if task_record.status == TaskStatus.COMPLETED:
                    log.write("[bold green]✅ 推进完成[/]")
                    logger.info(f"_do_advance: 任务完成 task_id={task_id}")
                    success = True
                    break
                elif task_record.status == TaskStatus.FAILED:
                    error_msg = task_record.error or "未知错误"
                    log.write(f"[bold red]❌ 推进失败: {error_msg}[/]")
                    logger.error(
                        f"_do_advance: 任务失败 task_id={task_id} error={error_msg}"
                    )
                    break
            except Exception as e:
                logger.warning(f"_do_advance: 轮询任务状态失败 error={e}")
        else:
            log.write("[bold yellow]⚠️ 推进超时，请检查服务器状态[/]")
            logger.warning(f"_do_advance: 任务轮询超时 task_id={task_id}")

        inp.disabled = False
        inp.focus()
        if success:
            self._show_player_status()

    @work
    async def _fetch_status(self) -> None:
        log = self.query_one(RichLog)
        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        bp = app.session_blueprint
        player_actor = bp.player_actor if bp else None

        # 基础信息
        log.write(
            f"[bold yellow]── 当前状态 ──────────────────────────────────────[/]\n"
            f"  玩家：[bold]{self._user_name}[/]\n"
            f"  游戏：[bold]{self._game_name}[/]\n"
            f"  玩家角色：[bold cyan]{player_actor or '（未知）'}[/]\n"
        )

        # 世界设定
        if bp:
            log.write(
                f"[bold yellow]── 游戏世界设定 ──────────────────────────────────────[/]\n"
                f"{bp.campaign_setting}\n"
            )

        # 玩家角色实体详情
        if player_actor:
            log.write(f"[dim]正在查询玩家角色实体：{player_actor} ...[/]")
            logger.info(f"_fetch_status: 查询玩家角色实体 player_actor={player_actor}")
            try:
                resp = await fetch_entities_details(
                    self._user_name, self._game_name, [player_actor]
                )
                if not resp.entities_serialization:
                    log.write(f"[yellow]未找到玩家角色实体：{player_actor}[/]")
                else:
                    for entity in resp.entities_serialization:
                        log.write(
                            f"[bold yellow]── 玩家角色实体：{entity.name} ──────────────────────────────────────[/]"
                        )
                        for comp in entity.components:
                            data_str = json.dumps(
                                comp.data, ensure_ascii=False, indent=2
                            )
                            log.write(f"  [bold cyan][组件][/] [green]{comp.name}[/]")
                            log.write(f"[dim]{data_str}[/]")
                        log.write("")
                logger.info(
                    f"_fetch_status: 玩家角色实体查询成功 player_actor={player_actor}"
                )
            except Exception as e:
                logger.error(
                    f"_fetch_status: 玩家角色实体查询失败 player_actor={player_actor} error={e}"
                )
                log.write(f"[bold red]❌ 玩家角色实体查询失败: {e}[/]")

    @work
    async def _fetch_stage_desc(self) -> None:
        log = self.query_one(RichLog)
        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        bp = app.session_blueprint
        player_actor = bp.player_actor if bp else None

        if not player_actor:
            log.write("[red]❌ 无法取得玩家角色信息[/]")
            return

        log.write("[dim]正在定位玩家所在场景...[/]")
        logger.info(
            f"_fetch_stage_desc: 开始查询 user_name={self._user_name} game_name={self._game_name}"
        )
        try:
            stages_resp = await fetch_stages_state(self._user_name, self._game_name)
        except Exception as e:
            logger.error(f"_fetch_stage_desc: fetch_stages_state 失败 error={e}")
            log.write(f"[bold red]❌ 场景状态查询失败: {e}[/]")
            return

        current_stage: str = ""
        for stage, actors in stages_resp.mapping.items():
            if player_actor in actors:
                current_stage = stage
                break

        if not current_stage:
            log.write(f"[yellow]⚠ 未能找到玩家角色 {player_actor} 所在场景[/]")
            return

        log.write(f"[dim]玩家当前场景：{current_stage}，正在获取场景描述...[/]")
        logger.info(f"_fetch_stage_desc: 玩家所在场景 current_stage={current_stage}")
        try:
            entities_resp = await fetch_entities_details(
                self._user_name, self._game_name, [current_stage]
            )
        except Exception as e:
            logger.error(f"_fetch_stage_desc: fetch_entities_details 失败 error={e}")
            log.write(f"[bold red]❌ 场景实体查询失败: {e}[/]")
            return

        narrative = ""
        for entity in entities_resp.entities_serialization:
            for comp in entity.components:
                if comp.name == "StageDescriptionComponent":
                    narrative = comp.data.get("narrative", "")
                    break

        log.write(
            f"[bold yellow]── 场景描述：{current_stage} ──────────────────────────────────────[/]"
        )
        if narrative:
            log.write(narrative)
        else:
            log.write("[dim]（场景描述尚未生成）[/]")
        log.write("")
        logger.info(
            f"_fetch_stage_desc: 完成 current_stage={current_stage} narrative_len={len(narrative)}"
        )

    @work
    async def _fetch_stages(self) -> None:
        log = self.query_one(RichLog)
        log.write("[dim]正在查询场景状态...[/]")
        logger.info(
            f"_fetch_stages: 开始查询 user_name={self._user_name} game_name={self._game_name}"
        )
        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        bp = app.session_blueprint
        player_only_stage = bp.player_only_stage if bp else None
        try:
            resp = await fetch_stages_state(self._user_name, self._game_name)
            logger.info(f"_fetch_stages: 查询成功 mapping={resp.mapping}")
            log.write(
                "[bold yellow]── 场景与角色分布 ──────────────────────────────────────[/]"
            )
            if not resp.mapping:
                log.write("  [dim]（暂无场景数据）[/]")
            else:
                for stage, actors in resp.mapping.items():
                    actors_str = "、".join(actors) if actors else "[dim]（空）[/]"
                    if stage == player_only_stage:
                        log.write(
                            f"  [bold magenta]{stage} ★玩家专属场景[/] → {actors_str}"
                        )
                    else:
                        log.write(f"  [bold cyan]{stage}[/] → {actors_str}")
            log.write("")
        except Exception as e:
            logger.error(f"_fetch_stages: 查询失败 error={e}")
            log.write(f"[bold red]❌ 查询失败: {e}[/]")

    @work
    async def _poll_messages(self) -> None:
        logger.info(
            f"_poll_messages: 启动轮询 user_name={self._user_name} game_name={self._game_name}"
        )
        while self._polling_active:
            await asyncio.sleep(2)
            if not self._polling_active:
                break
            try:
                resp = await fetch_session_messages(
                    self._user_name, self._game_name, self._last_sequence_id
                )
                for msg in resp.session_messages:
                    if msg.message_type == MessageType.NONE:
                        continue
                    if msg.sequence_id > self._last_sequence_id:
                        self._last_sequence_id = msg.sequence_id
                    log = self.query_one(RichLog)
                    if msg.message_type == MessageType.GAME:
                        message_text = msg.data.get(
                            "message", json.dumps(msg.data, ensure_ascii=False)
                        )
                        log.write(f"[bold white]{message_text}[/]")
                    else:  # AGENT_EVENT
                        log.write(_format_agent_event(msg.data))
                    logger.debug(
                        f"_poll_messages: 收到消息 seq={msg.sequence_id} type={msg.message_type}"
                    )
            except Exception as e:
                logger.warning(f"_poll_messages: 轮询失败 error={e}")
        logger.info(f"_poll_messages: 轮询已停止 user_name={self._user_name}")

    @work
    async def _do_logout(self) -> None:
        log = self.query_one(RichLog)
        log.write("[dim]正在登出...[/]")
        logger.info(
            f"_do_logout: 开始登出 user_name={self._user_name} game_name={self._game_name}"
        )
        try:
            msg = await server_logout(self._user_name, self._game_name)
            log.write(f"[bold green]✅ {msg}[/]")
            logger.info(
                f"_do_logout: 登出成功 user_name={self._user_name} msg={msg} → 清空会话状态 + pop_screen"
            )
            self._polling_active = False
            from .app import GameClient

            app: GameClient = self.app  # type: ignore[assignment]
            app.clear_session()
            await asyncio.sleep(0.5)
            self.app.pop_screen()
        except Exception as e:
            logger.error(f"_do_logout: 登出失败 user_name={self._user_name} error={e}")
            log.write(f"[bold red]❌ 登出失败: {e}[/]")
