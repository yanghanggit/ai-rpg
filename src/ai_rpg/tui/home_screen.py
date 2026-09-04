"""游戏主场景 Screen（Home 状态）：正文区 + 输入区，支持斜杠命令。"""

import asyncio
from typing import Dict, List, Optional, Tuple

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from .base import BaseGameScreen
from .cmd_advance import run_home_advance
from .cmd_browse import build_entity_browser_text
from .cmd_costume import (
    build_worn_list_text,
    remove_costume,
    wear_costume,
)
from .cmd_items import (
    build_items_list_text,
    move_item_to_inventory,
    move_item_to_storage,
)
from .cmd_roster import (
    add_roster_member,
    build_roster_list_text,
    remove_roster_member,
)
from .cmd_speak import speak_to
from .cmd_stage import build_stage_view_text
from .cmd_switch import switch_stage
from .server_client import (
    fetch_session_messages,
    logout as server_logout,
    stream_session_messages,
)
from .utils import display_name, format_agent_event

INTRO_TEXT = """\
[bold cyan]── 家园模式 ──[/]
[dim]输入 [bold]/[/] 查看可用命令。[/]
"""

# 命令定义：(完整命令, 简写, 说明)，顺序即 /help 展示顺序
COMMAND_DEFS: List[Tuple[str, str, str]] = [
    # 查看（系统级 / 幂等）
    ("info", "i", "查看蓝图与玩家信息"),
    ("browse", "b", "实体浏览器：列出全部场景与角色"),
    ("stage", "st", "查看当前所在场景描述与角色外观"),
    ("session", "ss", "查看消息（可带 sequence_id）"),
    # 副本
    ("dungeon", "d", "副本预览并可进入副本"),
    # 队伍
    ("list-roster", "lr", "查看队伍与盟友列表"),
    ("add-roster", "ar", "将盟友加入队伍：/add-roster @人名"),
    ("remove-roster", "rr", "将盟友移出队伍：/remove-roster @人名"),
    # 角色行动
    ("speak", "sp", "与当前场景 NPC 对话：/speak @人名 对话内容"),
    ("switch", "sw", "切换到其他场景：/switch @场景名"),
    # 核心行动
    ("advance", "a", "推进家园：让所有 NPC 角色触发规划与行动"),
    # 时装
    ("list-worn", "lw", "列出已穿戴时装的角色（含外观）"),
    ("wear", "w", "为目标穿戴时装：/wear @角色名 @时装名"),
    ("unwear", "uw", "卸下目标当前时装：/unwear @角色名"),
    # 道具与工坊
    ("list-items", "li", "列出随身背包与储物箱道具"),
    ("to-inventory", "ti", "储物箱→随身背包：/to-inventory @道具名"),
    ("to-storage", "ts", "随身背包→储物箱：/to-storage @道具名"),
    ("craft-consumable", "cc", "消耗品工坊：合成消耗品"),
    ("craft-gear", "cg", "装备工坊：用材料锻造装备"),
    ("craft-costume", "cf", "时装工坊：用材料制作时装"),
    # 系统
    ("logout", "lo", "登出并返回主菜单"),
    # 通用命令（固定在底部）
    ("help", "h", "显示本帮助"),
    ("clear", "c", "清空正文区"),
    ("quit", "q", "退出游戏"),
]

# 命令列表展示时，在这些命令前插入空行作为分组分隔
GROUP_BREAK_BEFORE = {
    "list-roster",
    "speak",
    "list-worn",
    "list-items",
    "craft-consumable",
    "help",
}

# 命令名（完整或简写）→ 完整命令名
COMMAND_ALIASES: Dict[str, str] = {
    alias: full for full, short, _ in COMMAND_DEFS for alias in (full, short)
}

# 已实现的基础命令
BASE_COMMANDS = {
    "help",
    "clear",
    "quit",
    "info",
    "logout",
    "browse",
    "stage",
    "session",
    "advance",
    "switch",
    "speak",
    "list-roster",
    "add-roster",
    "remove-roster",
    "list-items",
    "to-inventory",
    "to-storage",
    "list-worn",
    "wear",
    "unwear",
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


class HomeScreen(BaseGameScreen):
    """家园模式 Screen：正文区累加展示信息，输入区接收斜杠命令。

    当前为第一步：命令已列出，输入命令后仅写入日志，具体功能后续逐步接入。
    """

    CSS = """
    HomeScreen {
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

        # 空行分隔每条命令产生的输出
        self._write("")
        if canonical in BASE_COMMANDS:
            handler = getattr(self, f"_cmd_{canonical.replace('-', '_')}")
            handler(args)
        else:
            self._placeholder(canonical, args)

    def _placeholder(self, canonical: str, args: str) -> None:
        """第一步占位实现：仅把收到的命令写入正文区，功能后续逐步接入。"""
        suffix = f" {args}" if args else ""
        logger.info(f"HomeScreen: 收到命令 /{canonical}{suffix}（功能待接入）")
        self._write(f"[dim]▶ 已收到命令 [bold]/{canonical}[/]{suffix}，功能待接入。[/]")

    # ── 基础命令处理 ──

    def _cmd_help(self, args: str) -> None:
        self._write(HELP_TEXT)

    def _cmd_clear(self, args: str) -> None:
        self.query_one("#body", RichLog).clear()
        self._write(INTRO_TEXT)

    def _cmd_quit(self, args: str) -> None:
        self.app.exit()

    def _cmd_browse(self, args: str) -> None:
        self._do_browse()

    def _cmd_stage(self, args: str) -> None:
        self._do_stage()

    @work
    async def _do_stage(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        try:
            text = await build_stage_view_text(
                app.session.user_name,
                app.session.game_name,
                app.session.actor_name,
            )
            self._write(text)
        except Exception as e:
            logger.error(f"_do_stage: 获取当前场景失败 error={e}")
            self._write(f"[bold red]❌ 获取当前场景失败: {e}[/]")

    @work
    async def _do_browse(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        try:
            text = await build_entity_browser_text(
                app.session.user_name,
                app.session.game_name,
                app.session.actor_name,
            )
            self._write(text)
        except Exception as e:
            logger.error(f"_do_browse: 获取实体列表失败 error={e}")
            self._write(f"[bold red]❌ 实体列表加载失败: {e}[/]")

    def _cmd_session(self, args: str) -> None:
        self._do_view_messages(args)

    def _cmd_advance(self, args: str) -> None:
        self._do_advance()

    def _cmd_switch(self, args: str) -> None:
        target = args.strip()
        if target.startswith("@"):
            target = target[1:].strip()
        if not target:
            self._write("[yellow]用法：/switch @场景名[/]")
            return
        self._do_switch(target)

    def _cmd_speak(self, args: str) -> None:
        args = args.strip()
        if not args.startswith("@"):
            self._write("[yellow]用法：/speak @人名 对话内容[/]")
            return
        rest = args[1:].strip()
        if not rest:
            self._write("[yellow]用法：/speak @人名 对话内容[/]")
            return
        parts = rest.split(maxsplit=1)
        target = parts[0]
        content = parts[1].strip() if len(parts) > 1 else ""
        if not content:
            self._write("[yellow]对话内容不能为空，用法：/speak @人名 对话内容[/]")
            return
        self._do_speak(target, content)

    @work
    async def _do_speak(self, target: str, content: str) -> None:
        app = self.game_client
        if app.session is None:
            return
        self._write(f"[dim]▶ 发送对话：{target} ← 「{content}」...[/]")
        try:
            text = await speak_to(
                app.session.user_name,
                app.session.game_name,
                app.session.actor_name,
                target,
                content,
            )
            self._write(text)
        except Exception as e:
            logger.error(f"_do_speak: 发送对话失败 error={e}")
            self._write(f"[bold red]❌ 发送对话失败: {e}[/]")

    @work
    async def _do_switch(self, target: str) -> None:
        app = self.game_client
        if app.session is None:
            return
        self._write(f"[dim]▶ 正在切换到场景：{target}...[/]")
        try:
            text = await switch_stage(
                app.session.user_name,
                app.session.game_name,
                app.session.actor_name,
                target,
            )
            self._write(text)
        except Exception as e:
            logger.error(f"_do_switch: 场景切换请求失败 error={e}")
            self._write(f"[bold red]❌ 场景切换请求失败: {e}[/]")

    @work
    async def _do_advance(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        self._write(
            "[bold yellow]── 推进家园 ──────────────────────────────────────[/]"
        )
        self._write("[dim]▶ 正在推进...[/]")
        try:
            text = await run_home_advance(app.session.user_name, app.session.game_name)
            self._write(text)
        except Exception as e:
            logger.error(f"_do_advance: 推进请求失败 error={e}")
            self._write(f"[bold red]❌ 推进请求失败: {e}[/]")

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

    def _cmd_list_roster(self, args: str) -> None:
        self._do_list_roster()

    def _cmd_add_roster(self, args: str) -> None:
        target = args.strip()
        if target.startswith("@"):
            target = target[1:].strip()
        if not target:
            self._write("[yellow]用法：/add-roster @人名[/]")
            return
        self._do_add_roster(target)

    def _cmd_remove_roster(self, args: str) -> None:
        target = args.strip()
        if target.startswith("@"):
            target = target[1:].strip()
        if not target:
            self._write("[yellow]用法：/remove-roster @人名[/]")
            return
        self._do_remove_roster(target)

    @work
    async def _do_list_roster(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await build_roster_list_text(
            app.session.user_name,
            app.session.game_name,
            app.session.actor_name,
        )
        self._write(text)

    @work
    async def _do_add_roster(self, target: str) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await add_roster_member(
            app.session.user_name,
            app.session.game_name,
            target,
        )
        self._write(text)

    @work
    async def _do_remove_roster(self, target: str) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await remove_roster_member(
            app.session.user_name,
            app.session.game_name,
            target,
        )
        self._write(text)

    def _cmd_list_items(self, args: str) -> None:
        self._do_list_items()

    def _cmd_to_inventory(self, args: str) -> None:
        item_name = args.strip()
        if item_name.startswith("@"):
            item_name = item_name[1:].strip()
        if not item_name:
            self._write("[yellow]用法：/to-inventory @道具名[/]")
            return
        self._do_to_inventory(item_name)

    def _cmd_to_storage(self, args: str) -> None:
        item_name = args.strip()
        if item_name.startswith("@"):
            item_name = item_name[1:].strip()
        if not item_name:
            self._write("[yellow]用法：/to-storage @道具名[/]")
            return
        self._do_to_storage(item_name)

    @work
    async def _do_list_items(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await build_items_list_text(
            app.session.user_name,
            app.session.game_name,
            app.session.actor_name,
        )
        self._write(text)

    @work
    async def _do_to_inventory(self, item_name: str) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await move_item_to_inventory(
            app.session.user_name,
            app.session.game_name,
            item_name,
        )
        self._write(text)

    @work
    async def _do_to_storage(self, item_name: str) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await move_item_to_storage(
            app.session.user_name,
            app.session.game_name,
            item_name,
        )
        self._write(text)

    def _cmd_list_worn(self, args: str) -> None:
        self._do_list_worn()

    def _cmd_wear(self, args: str) -> None:
        parts = args.strip().split()
        if len(parts) < 2:
            self._write("[yellow]用法：/wear @角色名 @时装名[/]")
            return
        actor = parts[0]
        costume = " ".join(parts[1:])
        if not actor.startswith("@") or not costume.startswith("@"):
            self._write("[yellow]用法：/wear @角色名 @时装名[/]")
            return
        actor = actor[1:]
        costume = costume[1:]
        if not actor or not costume:
            self._write("[yellow]用法：/wear @角色名 @时装名[/]")
            return
        self._do_wear(actor, costume)

    def _cmd_unwear(self, args: str) -> None:
        actor = args.strip()
        if actor.startswith("@"):
            actor = actor[1:].strip()
        if not actor:
            self._write("[yellow]用法：/unwear @角色名[/]")
            return
        self._do_unwear(actor)

    @work
    async def _do_list_worn(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await build_worn_list_text(
            app.session.user_name,
            app.session.game_name,
        )
        self._write(text)

    @work
    async def _do_wear(self, actor: str, costume: str) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await wear_costume(
            app.session.user_name,
            app.session.game_name,
            actor,
            costume,
        )
        self._write(text)

    @work
    async def _do_unwear(self, actor: str) -> None:
        app = self.game_client
        if app.session is None:
            return
        text = await remove_costume(
            app.session.user_name,
            app.session.game_name,
            actor,
        )
        self._write(text)

    def _cmd_logout(self, args: str) -> None:
        self._do_logout()

    @work
    async def _do_logout(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        user_name = app.session.user_name
        game_name = app.session.game_name

        self._write("[dim]正在登出...[/]")
        logger.info(f"_do_logout: 开始登出 user_name={user_name} game_name={game_name}")
        try:
            msg = await server_logout(user_name, game_name)
            self._write(f"[bold green]✅ {msg}[/]")
            logger.info(
                f"_do_logout: 登出成功 user_name={user_name} msg={msg} → 清空会话状态 + pop_screen"
            )
            app.clear_session()
            await asyncio.sleep(0.5)
            self.app.pop_screen()
        except Exception as e:
            logger.error(f"_do_logout: 登出失败 user_name={user_name} error={e}")
            self._write(f"[bold red]❌ 登出失败: {e}[/]")

    def _cmd_info(self, args: str) -> None:
        """查看玩家信息 + 上一页（新游戏）展示过的蓝图信息。"""
        session = self.game_client.session
        if session is None:
            self._write("[red]❌ 当前无会话信息。[/]")
            return
        bp = session.blueprint

        actor = display_name(session.actor_name) if session.actor_name else "（未知）"
        self._write("[bold yellow]── 玩家信息 ────────────────────────────────[/]")
        self._write(
            f"[bold green]玩家：[/]{session.user_name}  "
            f"[bold green]游戏：[/]{session.game_name}  "
            f"[bold green]角色：[/][bold cyan]{actor}[/]"
        )
        self._write("")

        self._write("[bold yellow]── 游戏蓝图 ────────────────────────────────[/]")
        self._write(f"[bold green]{bp.name}[/]")
        self._write(f"\n{bp.campaign_setting}\n")

        self._write("[bold cyan]── 玩家角色 ────────────────────────────────[/]")
        self._write(f"  [bold magenta]{display_name(bp.player_actor)}[/]\n")

        self._write("[bold cyan]── 场景与角色 ────────────────────────────────[/]")
        for stage in bp.stages:
            actor_names = [a.name for a in stage.actors]
            if actor_names:
                actors_str = "、".join(
                    f"[{'bold magenta' if a == bp.player_actor else 'green'}]{display_name(a)}[/]"
                    for a in actor_names
                )
            else:
                actors_str = "[dim]（空）[/]"
            self._write(f"  [bold cyan]{display_name(stage.name)}[/] → {actors_str}")

        self._write("")
        self._write("[bold cyan]── 世界 ────────────────────────────────[/]")
        for ws in bp.world_entities:
            comp_names = (
                "、".join(c.name for c in ws.components)
                if ws.components
                else "[dim]（无特殊组件）[/]"
            )
            self._write(
                f"  [bold yellow]{display_name(ws.name)}[/] → [dim]{comp_names}[/]"
            )
