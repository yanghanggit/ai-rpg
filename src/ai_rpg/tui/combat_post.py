"""战斗结算 Screen（CombatPostScreen）

对应 CombatState.COMPLETE / POST_COMBAT 阶段：正文区 + 输入区，支持斜杠命令。
提供结算查询（info / loot / history 等）与结算动作（collect / exit / advance）。
"""

from typing import Dict, List, Optional, Tuple

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, Static, TextArea

from .base import BaseGameScreen
from .cmd_combat import (
    build_deck_text,
    build_entity_inspect_text,
    build_inventory_text,
)
from .cmd_combat_post import (
    advance_stage,
    build_loot_text,
    build_post_combat_info_text,
    build_round_history_text,
    collect_loot,
    exit_dungeon,
)
from .cmd_round import build_round_detail_text
from .combat_data_access import is_mock_mode
from .dungeon_room_router import route_to_current_room
from .server_client import fetch_session_messages, stream_session_messages
from .utils import format_agent_event, strip_markup

INTRO_TEXT = """\
[bold cyan]── 战斗结算（POST_COMBAT） ──[/]
[dim]输入 [bold]/[/] 查看可用命令。[/]
"""

# 命令定义：(完整命令, 简写, 说明)，顺序即 /help 展示顺序
COMMAND_DEFS: List[Tuple[str, str, str]] = [
    # 查询（只读）
    ("info", "i", "结算宏观状态（胜负结果 + 总局数）+ 场景角色摘要"),
    ("deck", "dk", "查阅牌组（双方）"),
    ("inventory", "inv", "查阅我方背包"),
    ("inspect", "insp", "查阅指定实体：/inspect @实体名"),
    ("loot", "lt", "查阅战利品"),
    ("round", "r", "查阅指定回合：/round <回合序号>"),
    ("history", "hist", "一次性列出全部回合（含日志/叙事）"),
    ("session", "ss", "查看消息（可带 sequence_id）"),
    # 改变
    ("collect", "cl", "收取战利品（转入随身背包）"),
    ("exit", "x", "退出副本，返回家园"),
    ("advance", "a", "进入下一关（房间）"),
    # 通用命令（固定在底部）
    ("help", "h", "显示本帮助"),
    ("clear", "c", "清空正文区"),
    ("quit", "q", "退出游戏"),
]

# 命令列表展示时，在这些命令前插入空行作为分组分隔
GROUP_BREAK_BEFORE = {"collect", "help"}

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


class CombatPostScreen(BaseGameScreen):
    """战斗 COMPLETE / POST_COMBAT 阶段结算 Screen。"""

    CSS = """
    CombatPostScreen {
        align: center middle;
    }

    #body {
        height: 1fr;
        padding: 0 1;
        border: none;
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
        yield TextArea(
            id="body",
            read_only=True,
            soft_wrap=True,
            show_cursor=False,
        )
        yield Static("", id="notify")
        with Horizontal(id="input-row"):
            yield Static("> ", id="prompt")
            yield Input(
                placeholder="输入 / 查看帮助，或输入 /command",
                id="command-input",
            )

    def on_mount(self) -> None:
        self._write(INTRO_TEXT)
        if is_mock_mode(self.game_client):
            self._write("[dim]（mock 模式：未检测到登录会话，使用固定调试数据）[/]")
        self.query_one("#command-input", Input).focus()
        self._watch_notifications()
        self._do_info()

    def _write(self, text: str) -> None:
        body = self.query_one("#body", TextArea)
        body.text = body.text + strip_markup(text) + "\n"
        body.scroll_end(animate=False)

    @on(Input.Submitted, "#command-input")
    def _on_submit(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()

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
            self._write("")
            handler(args)

    # ── 命令处理 ──

    def _cmd_help(self, args: str) -> None:
        self._write(HELP_TEXT)

    def _cmd_clear(self, args: str) -> None:
        self.query_one("#body", TextArea).text = ""
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

    def _cmd_loot(self, args: str) -> None:
        self._do_loot()

    def _cmd_round(self, args: str) -> None:
        raw = args.strip()
        if not raw:
            self._write("[yellow]用法：/round <回合序号>[/]")
            return
        try:
            round_number = int(raw)
        except ValueError:
            self._write(f"[bold red]❌ 无效的回合序号：{raw}，请输入数字。[/]")
            return
        self._do_round(round_number)

    def _cmd_history(self, args: str) -> None:
        self._do_history()

    def _cmd_session(self, args: str) -> None:
        self._do_view_messages(args)

    def _cmd_collect(self, args: str) -> None:
        self._do_collect()

    def _cmd_exit(self, args: str) -> None:
        self._do_exit()

    def _cmd_advance(self, args: str) -> None:
        self._do_advance()

    # ── 任务 ──

    @work
    async def _do_info(self) -> None:
        text = await build_post_combat_info_text(self.game_client)
        self._write(text)

    @work
    async def _do_deck(self) -> None:
        text = await build_deck_text(self.game_client)
        self._write(text)

    @work
    async def _do_inventory(self) -> None:
        text = await build_inventory_text(self.game_client)
        self._write(text)

    @work
    async def _do_inspect(self, entity_name: str) -> None:
        text = await build_entity_inspect_text(self.game_client, entity_name)
        self._write(text)

    @work
    async def _do_loot(self) -> None:
        text = await build_loot_text(self.game_client)
        self._write(text)

    @work
    async def _do_round(self, round_number: int) -> None:
        text = await build_round_detail_text(self.game_client, round_number)
        self._write(text)

    @work
    async def _do_history(self) -> None:
        text = await build_round_history_text(self.game_client)
        self._write(text)

    @work
    async def _do_collect(self) -> None:
        self._write(
            "[bold yellow]── 收取战利品 ──────────────────────────────────────[/]"
        )
        self._write("[dim]▶ 正在收取...[/]")
        ok, text = await collect_loot(self.game_client)
        self._write(text)

    @work
    async def _do_exit(self) -> None:
        self._write(
            "[bold yellow]── 退出副本 ──────────────────────────────────────[/]"
        )
        self._write("[dim]▶ 正在退出...[/]")
        ok, text = await exit_dungeon(self.game_client)
        self._write(text)
        # mock 模式下无真实家园可返回，直接退出应用
        if ok and is_mock_mode(self.game_client):
            self.app.exit()

    @work
    async def _do_advance(self) -> None:
        self._write(
            "[bold yellow]── 进入下一关 ──────────────────────────────────────[/]"
        )
        self._write("[dim]▶ 正在推进...[/]")
        ok, text = await advance_stage(self.game_client)
        self._write(text)
        if ok:
            if is_mock_mode(self.game_client):
                # mock 模式无真实会话，无法路由到下一关，直接退出应用
                self.app.exit()
            else:
                await route_to_current_room(self.game_client)

    # ── 会话消息（与其它战斗页一致） ──

    @work
    async def _do_view_messages(self, raw: str) -> None:
        if is_mock_mode(self.game_client):
            self._write("[dim]mock 模式：无会话消息流，/session 不可用。[/]")
            return

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
            badge.update("[dim]（mock 模式）[/]")
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
