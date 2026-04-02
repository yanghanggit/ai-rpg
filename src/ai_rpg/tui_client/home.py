"""游戏主场景 Screen（Home 状态）"""

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Header, Input, RichLog, Static

import asyncio

from loguru import logger
import json

from .server_client import (
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

MENU_TEXT = """\
[bold yellow]可用操作（输入编号执行）：[/]

[bold cyan]── 查看 ──────────────────────────────────────[/]
  [bold green]1[/]  当前状态      玩家/世界设定/角色详情
  [bold green]2[/]  场景总览      场景分布与当前场景描述
  [bold green]3[/]  实体浏览器    列出全部场景与角色
  [bold green]4[/]  地下城总览    列出全部副本预览

[bold cyan]── 行动 ──────────────────────────────────────[/]
  [bold green]5[/]  推进家园      执行一轮 home pipeline
  [bold green]6[/]  与NPC对话     与当前场景 NPC 对话
  [bold green]7[/]  切换场景      移动到其他场景
  [bold green]8[/]  管理远征队    加入/移除远征队成员

[bold cyan]── 系统 ──────────────────────────────────────[/]
  [bold green]0[/]  显示此菜单
  [bold dim]Escape[/]  登出并返回主菜单

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
        ("escape", "logout", "登出"),
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
            yield Input(placeholder="输入编号执行操作...", id="home-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(HOME_HEADER)
        log.write(MENU_TEXT)
        logger.info(
            f"HomeScreen: 进入主场景 user_name={self._user_name} game_name={self._game_name}"
        )
        self.query_one(Input).focus()
        self._polling_active = True
        self._poll_messages()

    def on_unmount(self) -> None:
        self._polling_active = False
        logger.info(f"HomeScreen: on_unmount，停止轮询 user_name={self._user_name}")

    def on_screen_resume(self) -> None:
        """从子 Screen 返回时刷新玩家状态。"""
        logger.info(
            f"HomeScreen: on_screen_resume，刷新数据 user_name={self._user_name}"
        )
        self._show_player_status()
        self.query_one(Input).focus()

    def action_logout(self) -> None:
        """ESC 触发登出。"""
        self._do_logout()

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
        cmd = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if not cmd:
            return

        log.write(f"[dim]> {cmd}[/]")
        logger.debug(f"HomeScreen: 收到命令 user_name={self._user_name} cmd={cmd}")

        if cmd == "0":
            log.write(MENU_TEXT)
        elif cmd == "1":
            from .player_status import PlayerStatusScreen

            self.app.push_screen(
                PlayerStatusScreen(user_name=self._user_name, game_name=self._game_name)
            )
        elif cmd == "2":
            from .stages import StagesScreen

            self.app.push_screen(
                StagesScreen(user_name=self._user_name, game_name=self._game_name)
            )
        elif cmd == "3":
            from .entity_browser import EntityBrowserScreen

            self.app.push_screen(
                EntityBrowserScreen(
                    user_name=self._user_name, game_name=self._game_name
                )
            )
        elif cmd == "4":
            from .dungeon_overview import DungeonOverviewScreen

            self.app.push_screen(
                DungeonOverviewScreen(
                    user_name=self._user_name, game_name=self._game_name
                )
            )
        elif cmd == "5":
            self._do_advance()
        elif cmd == "6":
            from .speak import SpeakScreen

            self.app.push_screen(
                SpeakScreen(user_name=self._user_name, game_name=self._game_name)
            )
        elif cmd == "7":
            from .switch_stage import SwitchStageScreen

            self.app.push_screen(
                SwitchStageScreen(user_name=self._user_name, game_name=self._game_name)
            )
        elif cmd == "8":
            from .roster import RosterScreen

            self.app.push_screen(
                RosterScreen(user_name=self._user_name, game_name=self._game_name)
            )
        else:
            log.write(f"[red]未知输入：{cmd}，输入 0 查看操作菜单。[/]")

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
