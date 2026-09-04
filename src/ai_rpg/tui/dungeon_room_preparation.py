"""副本房间准备 Screen：展示副本与当前房间信息，确认后进入房间。"""

from typing import Dict, List, Tuple

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from ..models import CombatRoom, Dungeon, DungeonRoom, OpeningRoom
from .base import BaseGameScreen
from .combat_room import CombatRoomScreen
from .dungeon_opening_room import DungeonOpeningRoomScreen
from .server_client import fetch_dungeon_state
from .utils import display_name

INTRO_TEXT = """\
[bold cyan]── 副本房间准备 ──[/]
[dim]输入 [bold]/[/] 查看可用命令。[/]
"""

# 命令定义：(完整命令, 简写, 说明)，顺序即 /help 展示顺序
COMMAND_DEFS: List[Tuple[str, str, str]] = [
    ("info", "i", "查看地下城与当前房间信息"),
    ("start-room", "sr", "开始当前房间"),
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


class DungeonRoomPreparationScreen(BaseGameScreen):
    """副本房间准备 Screen：展示地下城信息，由玩家确认后再进入当前房间。"""

    CSS = """
    DungeonRoomPreparationScreen {
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

        handler = getattr(self, f"_cmd_{canonical.replace('-', '_')}", None)
        if handler is not None:
            # 空行分隔每条命令产生的输出
            self._write("")
            handler(args)

    # ── 命令处理 ──

    def _cmd_help(self, args: str) -> None:
        self._write(HELP_TEXT)

    def _cmd_clear(self, args: str) -> None:
        self.query_one("#body", RichLog).clear()
        self._write(INTRO_TEXT)

    def _cmd_quit(self, args: str) -> None:
        self.app.exit()

    def _cmd_info(self, args: str) -> None:
        self._do_info()

    def _cmd_start_room(self, args: str) -> None:
        self._do_start_room()

    @work
    async def _do_info(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        try:
            resp = await fetch_dungeon_state(
                app.session.user_name, app.session.game_name
            )
        except Exception as e:
            logger.error(f"_do_info: 查询副本状态失败 error={e}")
            self._write(f"[bold red]❌ 查询副本状态失败: {e}[/]")
            return
        self._write(self._render_dungeon_info(resp.dungeon))

    @work
    async def _do_start_room(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        try:
            resp = await fetch_dungeon_state(
                app.session.user_name, app.session.game_name
            )
        except Exception as e:
            logger.error(f"_do_start_room: 查询副本状态失败 error={e}")
            self._write(f"[bold red]❌ 查询副本状态失败: {e}[/]")
            return

        room = resp.dungeon.current_room
        if room is None:
            self._write("[bold red]❌ 当前没有有效的房间[/]")
            return

        if isinstance(room, CombatRoom):
            logger.info(f"_do_start_room: 进入战斗房间 stage={room.stage.name}")
            self._write(f"[dim]▶ 进入战斗房间：{display_name(room.stage.name)}...[/]")
            self.app.switch_screen(CombatRoomScreen())
        elif isinstance(room, OpeningRoom):
            logger.info(f"_do_start_room: 进入开场房间 stage={room.stage.name}")
            self._write(f"[dim]▶ 进入开场房间：{display_name(room.stage.name)}...[/]")
            self.app.switch_screen(DungeonOpeningRoomScreen())
        elif isinstance(room, DungeonRoom):
            logger.info(f"_do_start_room: 探索房间无专属界面 stage={room.stage.name}")
            self._write("[yellow]当前房间为探索房间，暂无专属界面。[/]")
            self._write(self._render_dungeon_info(resp.dungeon))
        else:
            logger.warning(f"_do_start_room: 未知房间类型 type={room.type}")
            self._write(f"[bold red]❌ 未知房间类型：{room.type}[/]")

    def _render_dungeon_info(self, dungeon: Dungeon) -> str:
        """渲染地下城与当前房间信息，返回富文本字符串。"""
        lines: List[str] = []
        lines.append(
            f"[bold yellow]── 副本：{display_name(dungeon.name)} ──────────────────────────────────────[/]"
        )
        lines.append(f"  {dungeon.profile}")
        lines.append(f"  进度：{dungeon.current_room_index + 1} / {len(dungeon.rooms)}")
        lines.append("")

        room = dungeon.current_room
        if room is None:
            lines.append("  [yellow]当前没有有效房间。[/]")
        else:
            room_tag = {
                "combat": "[bold red]⚔ 战斗[/]",
                "opening": "[dim cyan]○ 开场[/]",
                "base": "[dim cyan]○ 探索[/]",
            }.get(room.type, room.type)
            lines.append(
                f"  [bold cyan]当前房间：[/]{display_name(room.stage.name)}  {room_tag}"
            )
            if room.stage.profile:
                lines.append(f"  {room.stage.profile}")

        return "\n".join(lines)
