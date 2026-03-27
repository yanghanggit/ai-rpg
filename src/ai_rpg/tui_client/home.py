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
    fetch_session_messages,
    fetch_stages_state,
    logout as server_logout,
)
from ..models.session_message import MessageType

HOME_HEADER = """\
[bold cyan]╔══════════════════════════════════════════════════╗[/]
[bold cyan]║        AI RPG TCG  游戏主场景                   ║[/]
[bold cyan]╚══════════════════════════════════════════════════╝[/]
"""

HELP_TEXT = """\
[bold yellow]可用命令：[/]

  [bold green]/help   [/]  显示此帮助信息
  [bold green]/status [/]  显示当前玩家与游戏状态
  [bold green]/stages [/]  查询全部场景与角色分布
  [bold green]/campaign_setting[/]  显示游戏世界设定（campaign_setting）
  [bold green]/logout [/]  登出并返回主菜单

"""


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
        ("ctrl+c", "app.quit", "退出"),
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
        log.write(
            f"[bold green]✅ 欢迎，{self._user_name}！游戏 [{self._game_name}] 已就绪。[/]"
        )
        log.write(HELP_TEXT)
        logger.info(
            f"HomeScreen: 进入主场景 user_name={self._user_name} game_name={self._game_name}"
        )
        self.query_one(Input).focus()
        self._polling_active = True
        self._poll_messages()

    def on_unmount(self) -> None:
        self._polling_active = False
        logger.info(
            f"HomeScreen: on_unmount，停止轮询 user_name={self._user_name}"
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
            from .app import GameClient

            app: GameClient = self.app  # type: ignore[assignment]
            bp = app.session_blueprint
            player_actor = bp.player_actor if bp else "[dim]（未知）[/]"
            log.write(
                f"[bold yellow]── 当前状态 ──────────────────────────────────────[/]\n"
                f"  玩家：[bold]{self._user_name}[/]\n"
                f"  游戏：[bold]{self._game_name}[/]\n"
                f"  玩家角色：[bold cyan]{player_actor}[/]\n"
            )
        elif cmd == "/stages":
            self._fetch_stages()
        elif cmd == "/campaign_setting":
            from .app import GameClient

            app2: GameClient = self.app  # type: ignore[assignment]
            bp2 = app2.session_blueprint
            if bp2:
                log.write(
                    f"[bold yellow]── 游戏世界设定 ──────────────────────────────────────[/]\n"
                    f"{bp2.campaign_setting}\n"
                )
            else:
                log.write("[dim]暂无世界设定数据。[/]")
        elif cmd == "/logout":
            self._do_logout()
        else:
            log.write(f"[red]未知命令：{cmd}，输入 /help 查看可用命令。[/]")

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
                    data_str = json.dumps(msg.data, ensure_ascii=False)
                    if msg.message_type == MessageType.GAME:
                        self.query_one(RichLog).write(
                            f"[bold white]{data_str}[/]"
                        )
                    else:  # AGENT_EVENT
                        self.query_one(RichLog).write(
                            f"[dim cyan]{data_str}[/]"
                        )
                    logger.debug(
                        f"_poll_messages: 收到消息 seq={msg.sequence_id} type={msg.message_type} data={data_str}"
                    )
            except Exception as e:
                logger.warning(f"_poll_messages: 轮询失败 error={e}")
        logger.info(
            f"_poll_messages: 轮询已停止 user_name={self._user_name}"
        )

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
