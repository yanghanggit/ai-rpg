"""战斗房间 Screen（CombatRoomScreen）

对应 CombatState.NONE / INITIALIZATION 阶段：正文区 + 输入区，支持斜杠命令。
战斗开始（/start）成功后切换到 CombatOngoingScreen。
"""

from typing import Dict, List, Optional, Tuple

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from .base import BaseGameScreen
from .cmd_combat import (
    build_combat_info_text,
    build_deck_text,
    build_entity_inspect_text,
    build_inventory_text,
    start_combat,
)
from .combat_ongoing import CombatOngoingScreen
from .server_client import fetch_session_messages, stream_session_messages
from .utils import format_agent_event

INTRO_TEXT = """\
[bold cyan]── 战斗房间 ──[/]
[dim]输入 [bold]/[/] 查看可用命令。[/]
"""

# 命令定义：(完整命令, 简写, 说明)，顺序即 /help 展示顺序
COMMAND_DEFS: List[Tuple[str, str, str]] = [
    # 查询（只读）
    ("info", "i", "战斗宏观状态 + 场景角色有效属性"),
    ("deck", "dk", "查阅牌组（双方）"),
    ("inventory", "inv", "查阅我方背包"),
    ("inspect", "insp", "查阅指定实体：/inspect @实体名"),
    ("session", "ss", "查看消息（可带 sequence_id）"),
    # 改变
    ("start", "s", "开始战斗（INITIALIZATION → ONGOING）"),
    # 通用命令（固定在底部）
    ("help", "h", "显示本帮助"),
    ("clear", "c", "清空正文区"),
    ("quit", "q", "退出游戏"),
]

# 命令列表展示时，在这些命令前插入空行作为分组分隔
GROUP_BREAK_BEFORE = {"start", "help"}

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


class CombatRoomScreen(BaseGameScreen):
    """战斗房间 Screen：NONE / INITIALIZATION 阶段，正文区累加展示信息。"""

    CSS = """
    CombatRoomScreen {
        align: center middle;
    }

    #body {
        height: 1fr;
        padding: 0 1;
    }

    #notify {
        height: 1;
        content-align: left middle;
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
        yield Static("", id="notify")
        with Horizontal(id="input-row"):
            yield Static("> ", id="prompt")
            yield Input(
                placeholder="输入 / 查看帮助，或输入 /command",
                id="command-input",
            )

    def on_mount(self) -> None:
        self._write(INTRO_TEXT)
        self.query_one("#command-input", Input).focus()
        self._watch_notifications()

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

    def _cmd_inventory(self, args: str) -> None:
        self._do_inventory()

    def _cmd_inspect(self, args: str) -> None:
        target = args.strip()
        if not target.startswith("@"):
            self._write("[yellow]用法：/inspect @实体名[/]")
            return
        entity_name = target[1:].strip()
        if not entity_name:
            self._write("[yellow]用法：/inspect @实体名[/]")
            return
        self._do_inspect(entity_name)

    def _cmd_session(self, args: str) -> None:
        self._do_view_messages(args)

    def _cmd_start(self, args: str) -> None:
        self._do_start()

    # ── 后台任务 ──

    @work
    async def _do_info(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await build_combat_info_text(
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
    async def _do_inventory(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await build_inventory_text(
            app.session.user_name, app.session.game_name, app.session.actor_name
        )
        self._write(text)

    @work
    async def _do_inspect(self, entity_name: str) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await build_entity_inspect_text(
            app.session.user_name, app.session.game_name, entity_name
        )
        self._write(text)

    @work
    async def _do_start(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        self._write(
            "[bold yellow]── 开始战斗 ──────────────────────────────────────[/]"
        )
        self._write("[dim]▶ 正在初始化战斗...[/]")
        ok, text = await start_combat(app.session.user_name, app.session.game_name)
        self._write(text)
        if ok:
            self.app.switch_screen(CombatOngoingScreen())

    @work
    async def _do_view_messages(self, raw: str) -> None:
        raw = raw.strip()
        start_seq: Optional[int] = None
        if raw:
            try:
                start_seq = int(raw)
            except ValueError:
                self._write(f"[bold red]❌ 无效的 sequence_id：{raw}，已取消[/]")
                return
            self._write(f"[dim]▶ 拉取 sequence_id > {start_seq} 的消息...[/]")
        else:
            self._write("[dim]▶ 拉取最新未读消息...[/]")

        count = await self._pull_messages(start_seq)
        if count == 0:
            self._write("[dim](没有更多消息)[/]")

    async def _pull_messages(self, start_sequence_id: Optional[int] = None) -> int:
        app = self.game_client
        if app.session is None:
            return 0
        since = (
            start_sequence_id
            if start_sequence_id is not None
            else app.session.last_sequence_id
        )
        try:
            resp = await fetch_session_messages(
                app.session.user_name, app.session.game_name, since
            )
        except Exception as e:
            logger.warning(f"_pull_messages: 拉取失败 error={e}")
            return 0

        count = 0
        for msg in resp.session_messages:
            if app.session is None:
                break
            if msg.sequence_id > app.session.last_sequence_id:
                app.session.last_sequence_id = msg.sequence_id
            if msg.agent_event is None:
                continue
            self._write(format_agent_event(msg.agent_event))
            self._write("--------------------------------------")
            count += 1
            logger.debug(f"_pull_messages: 写入消息 seq={msg.sequence_id}")
        self._update_notify_badge()
        return count

    def _update_notify_badge(self) -> None:
        app = self.game_client
        badge = self.query_one("#notify", Static)
        if app.session is None:
            badge.update("")
            return
        last_seq = app.session.last_sequence_id
        notify_seq = app.session.notify_last_sequence_id
        unread = max(0, notify_seq - last_seq)
        seq_info = f"[dim]（本地:{last_seq} / 服务器:{notify_seq}）[/]"
        if unread > 0:
            badge.update(
                f"[bold yellow]🔔 有 {unread} 条新消息[/] {seq_info}"
                f" —— 输入 [bold green]/session[/] 查看"
            )
        else:
            badge.update(seq_info)

    @work(exclusive=True)
    async def _watch_notifications(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        user_name = app.session.user_name
        game_name = app.session.game_name
        app.session.notify_last_sequence_id = app.session.last_sequence_id
        logger.info(f"_watch_notifications: 启动通知监听 user_name={user_name}")
        try:
            async for msg in stream_session_messages(
                user_name, game_name, app.session.notify_last_sequence_id
            ):
                if app.session is None:
                    break
                if msg.sequence_id > app.session.notify_last_sequence_id:
                    app.session.notify_last_sequence_id = msg.sequence_id
                self._update_notify_badge()
        except Exception as e:
            logger.warning(f"_watch_notifications: 通知流中断 error={e}")
        logger.info(f"_watch_notifications: 通知流已停止 user_name={user_name}")
