"""开场房间 Screen：正文区 + 输入区，支持斜杠命令。"""

from typing import Dict, List, Tuple

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from .base import BaseGameScreen
from .cmd_opening import (
    advance_stage,
    build_card_pool_text,
    build_deck_text,
    build_inventory_text,
    build_opening_info_text,
    generate_card_pool,
    init_opening,
    pick_card,
)

INTRO_TEXT = """\
[bold cyan]── 开场房间 ──[/]
[dim]输入 [bold]/[/] 查看可用命令。[/]
"""

# 命令定义：(完整命令, 简写, 说明)，顺序即 /help 展示顺序
COMMAND_DEFS: List[Tuple[str, str, str]] = [
    # 查询（只读）
    ("info", "i", "开场房间状态总览"),
    ("deck", "dk", "查阅我方牌组"),
    ("card-pool", "cp", "查阅我方卡池"),
    ("inventory", "inv", "查阅我方背包"),
    # 操作
    ("init", "in", "初始化开场房间（叙事 + 牌库）"),
    ("generate-pool", "gp", "生成卡池"),
    ("pick", "pc", "挑卡：/pick @角色名 @卡名"),
    ("next", "n", "进入下一关"),
    # 通用命令（固定在底部）
    ("help", "h", "显示本帮助"),
    ("clear", "c", "清空正文区"),
    ("quit", "q", "退出游戏"),
]

# 命令列表展示时，在这些命令前插入空行作为分组分隔
GROUP_BREAK_BEFORE = {"init", "help"}

# 命令名（完整或简写）→ 完整命令名
COMMAND_ALIASES: Dict[str, str] = {
    alias: full for full, short, _ in COMMAND_DEFS for alias in (full, short)
}


def _build_help_text() -> str:
    lines = ["[bold yellow]可用命令：[/]", ""]
    for full, short, desc in COMMAND_DEFS:
        if full in GROUP_BREAK_BEFORE and lines[-1] != "":
            lines.append("")
        lines.append(f"  [bold green]/{full}[/] [dim](/{short})[/]  {desc}")
    lines.append("")
    lines.append("[dim]直接输入 [bold]/[/] 亦可显示本帮助。[/]")
    return "\n".join(lines)


HELP_TEXT = _build_help_text()


class DungeonOpeningRoomScreen(BaseGameScreen):
    """开场房间 Screen：正文区累加展示信息，输入区接收斜杠命令。"""

    CSS = """
    DungeonOpeningRoomScreen {
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

    def _cmd_deck(self, args: str) -> None:
        self._do_deck()

    def _cmd_card_pool(self, args: str) -> None:
        self._do_card_pool()

    def _cmd_inventory(self, args: str) -> None:
        self._do_inventory()

    def _cmd_init(self, args: str) -> None:
        self._do_init()

    def _cmd_generate_pool(self, args: str) -> None:
        self._do_generate_pool()

    def _cmd_pick(self, args: str) -> None:
        parts = args.strip().split()
        if len(parts) < 2:
            self._write("[yellow]用法：/pick @角色名 @卡名[/]")
            return
        actor = parts[0]
        card = " ".join(parts[1:])
        if not actor.startswith("@") or not card.startswith("@"):
            self._write("[yellow]用法：/pick @角色名 @卡名[/]")
            return
        actor = actor[1:]
        card = card[1:]
        if not actor or not card:
            self._write("[yellow]用法：/pick @角色名 @卡名[/]")
            return
        self._do_pick(actor, card)

    def _cmd_next(self, args: str) -> None:
        self._do_next()

    # ── 后台任务 ──

    @work
    async def _do_info(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await build_opening_info_text(
            app.session.user_name, app.session.game_name, app.session.actor_name
        )
        self._write(text)

    @work
    async def _do_deck(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await build_deck_text(
            app.session.user_name, app.session.game_name, app.session.actor_name
        )
        self._write(text)

    @work
    async def _do_card_pool(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await build_card_pool_text(
            app.session.user_name, app.session.game_name, app.session.actor_name
        )
        self._write(text)

    @work
    async def _do_inventory(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await build_inventory_text(
            app.session.user_name, app.session.game_name, app.session.actor_name
        )
        self._write(text)

    @work
    async def _do_init(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await init_opening(app.session.user_name, app.session.game_name)
        self._write(text)

    @work
    async def _do_generate_pool(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await generate_card_pool(app.session.user_name, app.session.game_name)
        self._write(text)

    @work
    async def _do_pick(self, actor: str, card: str) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await pick_card(
            app.session.user_name, app.session.game_name, actor, card
        )
        self._write(text)

    @work
    async def _do_next(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        ok, text = await advance_stage(app.session.user_name, app.session.game_name)
        self._write(text)
        if ok:
            # 延迟导入，避免 dungeon_opening_room ↔ dungeon_room_preparation 循环引用
            from .dungeon_room_preparation import DungeonRoomPreparationScreen

            self.app.switch_screen(DungeonRoomPreparationScreen())
