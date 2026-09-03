"""新游戏 Screen：正文区 + 输入区，支持斜杠命令。"""

from datetime import datetime
from typing import Dict, List, Tuple

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from ..models import Blueprint
from .base import BaseGameScreen
from .server_client import fetch_blueprint_list, login, new_game
from .utils import display_name

INTRO_TEXT = """\
[bold cyan]── 开始新游戏 ──[/]
[dim]输入 [bold]/[/] 查看可用命令。[/]
"""

# 命令定义：(完整命令, 简写, 说明)，顺序即 /help 展示顺序
COMMAND_DEFS: List[Tuple[str, str, str]] = [
    ("info", "i", "获取蓝图信息"),
    ("start", "s", "开始新游戏"),
    ("help", "h", "显示本帮助"),
    ("clear", "c", "清空正文区"),
    ("quit", "q", "退出游戏"),
]

# 通用命令：固定在命令列表底部展示
COMMON_COMMANDS = {"help", "clear", "quit"}

# 命令名（完整或简写）→ 完整命令名
COMMAND_ALIASES: Dict[str, str] = {
    alias: full for full, short, _ in COMMAND_DEFS for alias in (full, short)
}


def _build_help_text() -> str:
    lines = ["[bold yellow]可用命令：[/]", ""]
    separated = False
    for full, short, desc in COMMAND_DEFS:
        if not separated and full in COMMON_COMMANDS:
            lines.append("")
            separated = True
        lines.append(f"  [bold green]/{full}[/] [dim](/{short})[/]  {desc}")
    lines.append("")
    lines.append("[dim]直接输入 [bold]/[/] 亦可显示本帮助。[/]")
    return "\n".join(lines)


HELP_TEXT = _build_help_text()


class NewGameScreen(BaseGameScreen):
    """新游戏 Screen：正文区累加展示信息，输入区接收斜杠命令。"""

    CSS = """
    NewGameScreen {
        align: center middle;
    }

    #body {
        height: 1fr;
        padding: 0 1;
    }

    #input-row {
        height: 3;
        dock: bottom;
    }

    #prompt {
        width: 3;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #command-input {
        width: 1fr;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self._blueprints: List[Blueprint] = []
        self._auto_player_id = f"tui_player_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self._starting = False

    def compose(self) -> ComposeResult:
        yield RichLog(id="body", highlight=True, markup=True, wrap=True)
        with Horizontal(id="input-row"):
            yield Static("> ", id="prompt")
            yield Input(
                placeholder="输入 / 查看帮助，或输入 /command",
                id="command-input",
            )

    def on_mount(self) -> None:
        self._write(INTRO_TEXT)
        self.query_one("#command-input", Input).focus()

    def _write(self, text: str) -> None:
        """把信息追加写入正文区。"""
        self.query_one("#body", RichLog).write(text)

    @on(Input.Submitted, "#command-input")
    def _on_submit(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()

        # 空输入或单独输入 '/'：等同于帮助
        if not raw or raw == "/":
            self._write("")
            self._write(HELP_TEXT)
            return

        if not raw.startswith("/"):
            self._write("")
            self._write(f"[dim]未知输入：{raw}，输入 [bold]/[/] 查看可用命令。[/]")
            return

        parts = raw[1:].strip().split(maxsplit=1)
        name = parts[0].lower() if parts else ""
        args = parts[1].strip() if len(parts) > 1 else ""

        canonical = COMMAND_ALIASES.get(name)
        if canonical is None:
            self._write("")
            self._write(f"[red]未知命令：/{name}，输入 [bold]/[/] 查看可用命令。[/]")
            return

        handler = getattr(self, f"_cmd_{canonical}", None)
        if handler is not None:
            # 空行分隔每条命令产生的输出
            self._write("")
            handler(args)

    # ── 命令处理 ──

    def _cmd_help(self, args: str) -> None:
        self._write(HELP_TEXT)

    def _cmd_info(self, args: str) -> None:
        self._fetch_blueprints()

    def _cmd_start(self, args: str) -> None:
        if self._starting:
            return
        if not self._blueprints:
            self._write("[yellow]⚠ 尚未获取蓝图信息，请先输入 /info。[/]")
            return
        self._starting = True
        self._start_new_game(self._auto_player_id, self._blueprints[0].name)

    def _cmd_clear(self, args: str) -> None:
        self.query_one("#body", RichLog).clear()
        self._write(INTRO_TEXT)

    def _cmd_quit(self, args: str) -> None:
        self.app.exit()

    # ── 后台任务 ──

    @work
    async def _fetch_blueprints(self) -> None:
        logger.info("_fetch_blueprints: 正在获取蓝图列表...")
        try:
            resp = await fetch_blueprint_list()
            self._blueprints = resp.blueprints
            if self._blueprints:
                bp = self._blueprints[0]
                self._write(f"玩家 ID：[bold green]{self._auto_player_id}[/]")
                self._write("")
                self._write(
                    "[bold cyan]── 游戏蓝图 ──────────────────────────────────[/]"
                )
                self._write(f"[bold green]{bp.name}[/]")
                self._write(f"\n{bp.campaign_setting}\n")

                self._write(
                    "[bold cyan]── 玩家角色 ──────────────────────────────────[/]"
                )
                self._write(f"  [bold magenta]{display_name(bp.player_actor)}[/]\n")

                self._write(
                    "[bold cyan]── 场景与角色 ────────────────────────────────[/]"
                )
                for stage in bp.stages:
                    actor_names = [a.name for a in stage.actors]
                    if actor_names:
                        actors_str = "、".join(
                            f"[{'bold magenta' if a == bp.player_actor else 'green'}]{display_name(a)}[/]"
                            for a in actor_names
                        )
                    else:
                        actors_str = "[dim]（空）[/]"
                    self._write(
                        f"  [bold cyan]{display_name(stage.name)}[/] → {actors_str}"
                    )
                self._write("")
                self._write("[bold cyan]── 世界 ──────────────────────────────────[/]")
                for ws in bp.world_entities:
                    comp_names = (
                        "、".join(c.name for c in ws.components)
                        if ws.components
                        else "[dim]（无特殊组件）[/]"
                    )
                    self._write(
                        f"  [bold yellow]{display_name(ws.name)}[/] → [dim]{comp_names}[/]"
                    )
                self._write("")
                self._write("[dim]输入 [bold]/start[/] 开始游戏。[/]")
            else:
                self._write("[red]❌ 服务器暂无可用蓝图，无法开始游戏。[/]")
            logger.info(
                f"_fetch_blueprints: 获取成功，共 {len(self._blueprints)} 个蓝图"
            )
        except Exception as e:
            logger.error(f"_fetch_blueprints: 获取失败 error={e}")
            self._write(f"[red]❌ 蓝图列表获取失败：{e}[/]")

    @work
    async def _start_new_game(self, user_name: str, game_name: str) -> None:
        self._write(f"[dim]正在登录，player_id={user_name} ...[/]")
        logger.info(
            f"_start_new_game: 开始登录 user_name={user_name} game_name={game_name}"
        )
        try:
            login_msg = await login(user_name, game_name)
            self._write(f"[green]✅ 登录成功：{login_msg}[/]")
            logger.info(
                f"_start_new_game: 登录成功 user_name={user_name} msg={login_msg}"
            )
        except Exception as e:
            logger.error(f"_start_new_game: 登录失败 user_name={user_name} error={e}")
            self._write(f"[bold red]❌ 登录失败: {e}[/]")
            self._starting = False
            return

        self._write(f"[dim]正在创建游戏，game_name={game_name} ...[/]")
        logger.info(f"_start_new_game: 开始创建游戏 game_name={game_name}")
        try:
            resp = await new_game(user_name, game_name)
            self._write("[bold green]✅ 游戏已创建！正在进入...[/]")
            logger.info(
                f"_start_new_game: 游戏创建成功 user_name={user_name} game_name={game_name} → 进入 HomeScreen"
            )
            from .home_screen import HomeScreen
            from .session import ClientSession

            app = self.game_client
            app.session = ClientSession(
                player_session=resp.player_session,
                blueprint=resp.blueprint,
            )
            app.switch_screen(HomeScreen())
        except Exception as e:
            logger.error(
                f"_start_new_game: 创建游戏失败 game_name={game_name} error={e}"
            )
            self._write(f"[bold red]❌ 创建游戏失败: {e}[/]")
            self._starting = False
