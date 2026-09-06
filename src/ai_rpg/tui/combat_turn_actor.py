"""战斗回合行动 Screen（CombatTurnActorScreen）

对应 CombatState.ONGOING 下「单个 current_actor 执行行动」阶段：正文区 + 输入区，
支持斜杠命令。按当前 turn 角色阵营（我方 / 怪物）展示两套命令：

- 我方：play / use / gear / pass
- 怪物：advance
- 两套共用查询型命令：info / hand / deck / inventory / inspect / session / round
- 通用：help / clear / quit

改变性动作完成后，若触发「换手 / 回合完成 / 战斗出结果」，则渲染仲裁结果并锁定
输入框，玩家按回车切到下一个正确的 Screen。
"""

from typing import Dict, List, Optional, Set, Tuple

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
from .cmd_hand import build_hand_text
from .cmd_round import build_round_detail_text
from .cmd_turn_actor import (
    TO_NEXT_TURN,
    TO_POST_COMBAT,
    TO_ROUND_START,
    TurnActionResult,
    TurnActorOverview,
    advance_monster_turn,
    build_turn_actor_info_text,
    equip_gear,
    load_turn_actor_overview,
    pass_turn,
    play_cards,
    use_consumable,
)
from .combat_data_access import is_mock_mode
from .server_client import fetch_session_messages, stream_session_messages
from .utils import format_agent_event, strip_markup

INTRO_TEXT = """\
[bold cyan]── 回合行动（当前 turn 角色） ──[/]
[dim]输入 [bold]/[/] 查看可用命令。[/]
"""

_QUERY_COMMAND_DEFS: List[Tuple[str, str, str]] = [
    ("info", "i", "战斗宏观状态 + 回合状态 + 当前 turn 详情"),
    ("hand", "hd", "双方手牌 + HP + 能量 + 总格挡 + 抽牌/弃牌/消耗堆"),
    ("deck", "dk", "查阅牌组（双方）"),
    ("inventory", "inv", "查阅我方背包"),
    ("inspect", "insp", "查阅指定实体：/inspect @实体名"),
    ("session", "ss", "查看消息（可带 sequence_id）"),
    ("round", "r", "查阅指定回合完整信息：/round <回合序号>"),
]

_PARTY_ACTION_COMMAND_DEFS: List[Tuple[str, str, str]] = [
    ("play", "p", "出牌：/play <卡牌名> @目标"),
    ("use", "u", "使用消耗品：/use <消耗品名> @目标"),
    ("gear", "g", "使用装备：/gear <装备名>"),
    ("pass", "ps", "过牌（结束当前角色回合）"),
]

_MONSTER_ACTION_COMMAND_DEFS: List[Tuple[str, str, str]] = [
    ("advance", "a", "推进怪物回合（AI 自动出牌/过牌）"),
]

_COMMON_COMMAND_DEFS: List[Tuple[str, str, str]] = [
    ("help", "h", "显示本帮助"),
    ("clear", "c", "清空正文区"),
    ("quit", "q", "退出游戏"),
]


def _command_defs_for_faction(faction: str) -> List[Tuple[str, str, str]]:
    actions = (
        _MONSTER_ACTION_COMMAND_DEFS
        if faction == "monster"
        else _PARTY_ACTION_COMMAND_DEFS
    )
    return [*_QUERY_COMMAND_DEFS, *actions, *_COMMON_COMMAND_DEFS]


def _group_break_before(faction: str) -> Set[str]:
    first_action = (
        _MONSTER_ACTION_COMMAND_DEFS[0][0]
        if faction == "monster"
        else _PARTY_ACTION_COMMAND_DEFS[0][0]
    )
    return {first_action, "help"}


def _build_help_text(defs: List[Tuple[str, str, str]], breaks: Set[str]) -> str:
    lines = ["[bold yellow]可用命令：[/]", ""]
    for full, short, desc in defs:
        if full in breaks and lines[-1] != "":
            lines.append("")
        lines.append(f"  [bold green]/{full}[/] [dim](/{short})[/]  {desc}")
    lines.append("")
    lines.append("[dim]直接输入 [bold]/[/] 亦可显示本帮助。[/]")
    return "\n".join(lines)


def _parse_name_and_targets(args: str) -> Tuple[str, List[str]]:
    """解析 '/play <卡牌名> [@目标...]' / '/use <道具名> @目标' → (名称, [目标...])。"""
    parts = args.split("@")
    name = parts[0].strip()
    targets = [p.strip() for p in parts[1:] if p.strip()]
    return name, targets


class CombatTurnActorScreen(BaseGameScreen):
    """战斗 ONGOING 下「单个 turn actor 执行行动」Screen。"""

    CSS = """
    CombatTurnActorScreen {
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

    BINDINGS = [
        ("enter", "continue", "继续"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._overview: Optional[TurnActorOverview] = None
        self._locked: bool = False
        self._pending_target: Optional[str] = None
        self._faction: str = "unknown"
        self._command_defs: List[Tuple[str, str, str]] = (
            _QUERY_COMMAND_DEFS + _COMMON_COMMAND_DEFS
        )
        self._command_aliases: Dict[str, str] = {}
        self._help_text: str = ""
        self._set_faction("unknown")

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
        self._load_turn_actor()

    def _write(self, text: str) -> None:
        body = self.query_one("#body", TextArea)
        body.text = body.text + strip_markup(text) + "\n"
        body.scroll_end(animate=False)

    # ── 命令集 ──

    def _set_faction(self, faction: str) -> None:
        self._faction = faction
        self._command_defs = _command_defs_for_faction(faction)
        self._command_aliases = {
            alias: full
            for full, short, _ in self._command_defs
            for alias in (full, short)
        }
        self._help_text = _build_help_text(
            self._command_defs, _group_break_before(faction)
        )

    # ── 输入分发 ──

    @on(Input.Submitted, "#command-input")
    def _on_submit(self, event: Input.Submitted) -> None:
        if self._locked:
            event.input.clear()
            return

        raw = event.value.strip()
        event.input.clear()

        if not raw or raw == "/":
            self._write("")
            self._write(self._help_text)
            return

        if not raw.startswith("/"):
            self._write("")
            self._write(f"[dim]未知输入：{raw}，输入 [bold]/[/] 查看可用命令。[/]")
            return

        parts = raw[1:].strip().split(maxsplit=1)
        name = parts[0].lower() if parts else ""
        args = parts[1].strip() if len(parts) > 1 else ""

        canonical = self._command_aliases.get(name)
        if canonical is None:
            self._write("")
            self._write(f"[red]未知命令：/{name}，输入 [bold]/[/] 查看可用命令。[/]")
            return

        handler = getattr(self, f"_cmd_{canonical.replace('-', '_')}", None)
        if handler is not None:
            self._write("")
            handler(args)

    def action_continue(self) -> None:
        """锁定态下按回车 → 切到 pending_target 指定的 Screen。"""
        if not self._locked or self._pending_target is None:
            return
        target = self._pending_target
        self._pending_target = None
        self._locked = False

        if target == TO_POST_COMBAT:
            from .combat_post import CombatPostScreen

            self.app.switch_screen(CombatPostScreen())
        elif target == TO_ROUND_START:
            from .combat_round_start import CombatRoundStartScreen

            self.app.switch_screen(CombatRoundStartScreen())
        elif target == TO_NEXT_TURN:
            self.app.switch_screen(CombatTurnActorScreen())

    # ── 命令处理 ──

    def _cmd_help(self, args: str) -> None:
        self._write(self._help_text)

    def _cmd_clear(self, args: str) -> None:
        self.query_one("#body", TextArea).text = ""
        self._write(INTRO_TEXT)

    def _cmd_quit(self, args: str) -> None:
        self.app.exit()

    def _cmd_info(self, args: str) -> None:
        self._do_info()

    def _cmd_hand(self, args: str) -> None:
        self._do_hand()

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

    def _cmd_play(self, args: str) -> None:
        card_name, targets = _parse_name_and_targets(args)
        if not card_name:
            self._write("[yellow]用法：/play <卡牌名> @目标[/]")
            return
        # 服务端 resolve_targets：非 self_target 卡牌必须恰好 1 个目标作为
        # 目标/阵营锚点（SINGLE / ALL / SPREAD 均如此）。
        if len(targets) != 1:
            self._write("[yellow]出牌需要恰好一个目标：/play <卡牌名> @目标[/]")
            return
        self._do_play(card_name, targets)

    def _cmd_use(self, args: str) -> None:
        item_name, targets = _parse_name_and_targets(args)
        if not item_name:
            self._write("[yellow]用法：/use <消耗品名> @目标[/]")
            return
        self._do_use(item_name, targets)

    def _cmd_gear(self, args: str) -> None:
        item_name = args.strip()
        if not item_name:
            self._write("[yellow]用法：/gear <装备名>[/]")
            return
        self._do_gear(item_name)

    def _cmd_pass(self, args: str) -> None:
        self._do_pass()

    def _cmd_advance(self, args: str) -> None:
        self._do_advance()

    # ── 改变性动作收尾 ──

    def _finish_action(self, result: TurnActionResult) -> None:
        self._write(result.text)
        if result.ok and result.transition is not None:
            self._lock(result.transition)

    def _lock(self, target: str) -> None:
        self._locked = True
        self._pending_target = target
        self.query_one("#command-input", Input).disabled = True
        # 失焦，确保回车键不会被 TextArea 等其它可聚焦组件吃掉，从而触发本页
        # 的 "enter" 绑定（action_continue）。
        self.set_focus(None)
        self.query_one("#notify", Static).update(
            "[bold yellow]🔒 输入已锁定 —— 按回车继续[/]"
        )
        self._write("")
        self._write("[bold yellow]🔒 输入已锁定 —— 按回车继续[/]")

    # ── 后台任务 ──

    @work
    async def _load_turn_actor(self) -> None:
        try:
            overview = await load_turn_actor_overview(self.game_client)
        except Exception as e:
            logger.error(f"_load_turn_actor: 加载失败 error={e}")
            self._write(f"[bold red]❌ 加载回合行动信息失败：{e}[/]")
            return
        self._overview = overview
        self._set_faction(overview.faction)
        self._write(build_turn_actor_info_text(overview))
        self._write("")
        self._write("[dim]输入 [bold]/[/] 查看可用命令。[/]")

    @work
    async def _do_info(self) -> None:
        try:
            overview = await load_turn_actor_overview(self.game_client)
            self._overview = overview
            if overview.faction != self._faction:
                self._set_faction(overview.faction)
            self._write(build_turn_actor_info_text(overview))
        except Exception as e:
            logger.error(f"_do_info: 加载失败 error={e}")
            self._write(f"[bold red]❌ 加载回合行动信息失败：{e}[/]")

    @work
    async def _do_hand(self) -> None:
        text = await build_hand_text(self.game_client)
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
    async def _do_round(self, round_number: int) -> None:
        text = await build_round_detail_text(self.game_client, round_number)
        self._write(text)

    @work
    async def _do_play(self, card_name: str, targets: List[str]) -> None:
        self._write("[bold yellow]── 出牌 ───────────────────────────────[/]")
        self._write("[dim]▶ 正在出牌...[/]")
        result = await play_cards(self.game_client, card_name, targets)
        self._finish_action(result)

    @work
    async def _do_use(self, item_name: str, targets: List[str]) -> None:
        self._write("[bold yellow]── 使用消耗品 ───────────────────────────────[/]")
        self._write("[dim]▶ 正在使用...[/]")
        result = await use_consumable(self.game_client, item_name, targets)
        self._finish_action(result)

    @work
    async def _do_gear(self, item_name: str) -> None:
        self._write("[bold yellow]── 使用装备 ───────────────────────────────[/]")
        self._write("[dim]▶ 正在使用...[/]")
        result = await equip_gear(self.game_client, item_name)
        self._finish_action(result)

    @work
    async def _do_pass(self) -> None:
        self._write("[bold yellow]── 过牌 ───────────────────────────────[/]")
        self._write("[dim]▶ 正在过牌...[/]")
        result = await pass_turn(self.game_client)
        self._finish_action(result)

    @work
    async def _do_advance(self) -> None:
        self._write("[bold yellow]── 推进怪物回合 ───────────────────────────────[/]")
        self._write("[dim]▶ 正在推进...[/]")
        result = await advance_monster_turn(self.game_client)
        self._finish_action(result)

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
