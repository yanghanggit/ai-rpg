"""游戏主场景 Screen（Home 状态）"""

from typing import List, Optional
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static
from .base import BaseGameScreen
import asyncio
from loguru import logger

from ..models import StagesStateResponse, StageDescriptionComponent, AppearanceComponent
from .server_client import (
    fetch_session_messages,
    stream_session_messages,
    fetch_stages_state,
    fetch_entities_details,
    watch_task_until_done,
    TaskFailedError,
    home_advance as server_home_advance,
    logout as server_logout,
)
from .utils import display_name, format_agent_event

MENU_TEXT = """\
[bold yellow]可用操作（输入编号执行）：[/]

[bold cyan]── 查看（系统级 / 幂等） ──────────────────────[/]
  [bold green]1[/]  实体浏览器    列出全部场景与角色

[bold cyan]── 地下城远征 ──────────────────────────────────[/]
  [bold green]2[/]  地下城        查看副本预览并可进入地下城
  [bold green]3[/]  管理远征队    加入/移除远征队成员

[bold cyan]── 角色行动（仅当前角色可执行） ────────────────[/]
  [bold green]4[/]  与NPC对话     与当前场景 NPC 对话
  [bold green]5[/]  切换场景      移动到其他场景

[bold cyan]── 核心行动 ────────────────────────────────────[/]
  [bold green]6[/]  推进家园      home内所有 NPC角色 触发*规划*与*行动*，并生成消息
  [bold green]7[/]  穿戴时装      为目标安装/移除时装

[bold cyan]── 道具与工坊 ──────────────────────────────────[/]
  [bold green]8[/]  道具管理      背包与储物箱道具移动
  [bold green]9[/]  制造工坊      合成消耗品
  [bold green]10[/] 工坊锻造      用材料锻造装备
  [bold green]11[/] 工坊制衣      用材料制作时装

[bold cyan]── 消息 ──────────────────────────────────────[/]
  [bold green]/session[/] [sequence_id]  查看指定序号之后的消息（留空则查看最新未读消息，简写：/ss）
  [bold green]/stage[/]  查看玩家当前所在场景描述与场景内全部角色外观（简写：/st）

[bold cyan]── 系统 ──────────────────────────────────────[/]
  [bold green]0[/]  显示此菜单
  [bold dim]Escape[/]  登出并返回主菜单

"""


def _get_player_stage_actors(
    stages_resp: StagesStateResponse, player_actor: Optional[str]
) -> List[str]:
    """从场景状态中找到 player_actor 所在的场景，返回该场景内的全部角色（含玩家自身）。

    若无法确定玩家所在场景，返回空列表。
    """
    if not player_actor:
        return []
    for actors in stages_resp.mapping.values():
        if player_actor in actors:
            return actors
    return []


def _get_all_actors(stages_resp: StagesStateResponse) -> List[str]:
    """返回全部场景中出现过的全部角色（跨场景去重，保持首次出现顺序）。"""
    all_actors: List[str] = []
    seen: set[str] = set()
    for actors in stages_resp.mapping.values():
        for actor in actors:
            if actor not in seen:
                seen.add(actor)
                all_actors.append(actor)
    return all_actors


class HomeScreen(BaseGameScreen):
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

    #home-notify {
        height: 1;
        content-align: left middle;
        padding: 0 1;
    }

    #home-input-row {
        height: 3;
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

    def __init__(self) -> None:
        super().__init__()

    def compose(self) -> ComposeResult:
        yield RichLog(id="home-log", highlight=True, markup=True, wrap=True)
        yield Static("", id="home-notify")
        with Horizontal(id="home-input-row"):
            yield Static("> ", id="home-prompt")
            yield Input(placeholder="输入编号执行操作...", id="home-input")

    def on_mount(self) -> None:
        _app = self.game_client
        self._reset_log()
        if _app.session:
            logger.info(
                f"HomeScreen: 进入主场景 user_name={_app.session.user_name}"
                f" game_name={_app.session.game_name}"
            )
        self.query_one(Input).focus()
        self._watch_notifications()

    def on_unmount(self) -> None:
        logger.info("HomeScreen: on_unmount")

    def on_screen_suspend(self) -> None:
        """推入子 Screen 时触发，仅用于日志记录。"""
        logger.info("HomeScreen: on_screen_suspend")

    def on_screen_resume(self) -> None:
        """从子 Screen 返回时，重新挂载通知监听（未读数量），消息内容仅通过命令 12 手动获取。"""
        logger.info("HomeScreen: on_screen_resume，重新挂载通知监听")
        self._watch_notifications()
        self.query_one(Input).focus()

    def action_logout(self) -> None:
        """ESC 触发登出。"""
        self._do_logout()

    def _write_header(self, log: RichLog) -> None:
        """写入顶部基础信息（玩家/游戏/角色），合入主 log，会话期间不会变化，只需写入一次。"""
        session = self.game_client.session
        if session is None:
            # log.write("[bold cyan]AI RPG DBG  游戏主场景[/]")
            return
        actor_text = (
            display_name(session.actor_name) if session.actor_name else "（未知）"
        )
        log.write(
            # "[bold cyan]AI RPG DBG  游戏主场景[/]\n"
            f"[bold green]▶ 玩家：[/][bold]{session.user_name}[/]  "
            f"[bold green]游戏：[/][bold]{session.game_name}[/]  "
            f"[bold green]角色：[/][bold cyan]{actor_text}[/]"
            f"\n\n"
        )

    def _reset_log(self) -> None:
        """清空主 log 并重新写入基础信息 + 命令菜单，用于清空累积的事件记录。"""
        log = self.query_one(RichLog)
        log.clear()
        self._write_header(log)
        log.write(MENU_TEXT)

    @on(Input.Submitted, "#home-input")
    def handle_command(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if cmd == "0":
            self._reset_log()
            return

        if not cmd:
            return

        parts = cmd.split(maxsplit=1)
        if parts[0].lower() in ("/session", "/ss"):
            arg = parts[1].strip() if len(parts) > 1 else ""
            self._do_view_messages(arg)
            return

        if parts[0].lower() in ("/stage", "/st"):
            self._do_view_stage()
            return

        log.write(f"[dim]> {cmd}[/]")
        logger.debug(f"HomeScreen: 收到命令 cmd={cmd}")

        if cmd == "1":
            from .home_entity_browser import HomeEntityBrowserScreen

            self.app.push_screen(HomeEntityBrowserScreen())
        elif cmd == "2":
            from .dungeon_overview import DungeonOverviewScreen

            self.app.push_screen(DungeonOverviewScreen())
        elif cmd == "3":
            from .home_party_roster_management import HomePartyRosterManagementScreen

            self.app.push_screen(HomePartyRosterManagementScreen())
        elif cmd == "4":
            from .speak import SpeakScreen

            self.app.push_screen(SpeakScreen())
        elif cmd == "5":
            from .switch_stage import SwitchStageScreen

            self.app.push_screen(SwitchStageScreen())
        elif cmd == "6":
            self._do_advance()
        elif cmd == "7":
            from .home_wear_costume import HomeWearCostumeScreen

            self.app.push_screen(HomeWearCostumeScreen())
        elif cmd == "8":
            from .home_item_management import HomeItemManagementScreen

            self.app.push_screen(HomeItemManagementScreen())
        elif cmd == "9":
            from .craft_consumable_item import CraftConsumableItemScreen

            self.app.push_screen(CraftConsumableItemScreen())
        elif cmd == "10":
            from .craft_gear_item import CraftGearItemScreen

            self.app.push_screen(CraftGearItemScreen())
        elif cmd == "11":
            from .craft_costume_item import CraftCostumeItemScreen

            self.app.push_screen(CraftCostumeItemScreen())
        else:
            log.write(f"[red]未知输入：{cmd}，输入 0 查看操作菜单。[/]")

    @work
    async def _do_advance(self) -> None:
        """执行一轮家园推进（home pipeline），推进期间禁用输入框并轮询任务状态。

        对全部场景中的全部角色（含玩家自身）发起集体推进，让所有角色本轮都触发行动规划。
        """
        app = self.game_client
        if app.session is None:
            return
        user_name = app.session.user_name
        game_name = app.session.game_name

        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True
        log.write("[bold yellow]── 推进家园 ──────────────────────────────────────[/]")
        log.write("[dim]▶ 正在推进...[/]")
        logger.info(
            f"_do_advance: 开始推进 user_name={user_name} game_name={game_name}"
        )

        task_id: str = ""
        try:
            stages_resp = await fetch_stages_state(user_name, game_name)
            actor_names = _get_all_actors(stages_resp)

            if not actor_names:
                log.write("[bold red]❌ 当前没有可推进的角色[/]")
                logger.error("_do_advance: 没有可推进的角色")
                inp.disabled = False
                inp.focus()
                return

            resp = await server_home_advance(user_name, game_name, actor_names)
            task_id = resp.task_id
            log.write(f"[dim]任务已创建：{task_id}[/]")
            logger.info(f"_do_advance: 任务已创建 task_id={task_id}")

        except Exception as e:
            logger.error(f"_do_advance: 触发推进失败 error={e}")
            log.write(f"[bold red]❌ 推进请求失败: {e}[/]")
            inp.disabled = False
            inp.focus()
            return

        try:
            await watch_task_until_done(task_id)
            logger.info(f"_do_advance: 任务完成 task_id={task_id}")
            log.write(f"[bold green]✅ 任务完成 task_id={task_id}[/]")
        except TaskFailedError as e:
            log.write(f"[bold red]❌ 推进失败: {e}[/]")
            logger.error(f"_do_advance: 任务失败 task_id={task_id} error={e}")
        except TimeoutError:
            log.write("[bold yellow]⚠️ 推进超时，请检查服务器状态[/]")
            logger.warning(f"_do_advance: 任务轮询超时 task_id={task_id}")
        except Exception as e:
            logger.warning(f"_do_advance: 等待任务失败 error={e}")

        inp.disabled = False
        inp.focus()

    async def _pull_messages(self, start_sequence_id: Optional[int] = None) -> int:
        """单次拉取指定起点（默认为当前 last_sequence_id）之后的会话消息，写入日志并推进 last_sequence_id。

        相比之前基于 SSE 的常驻轮询，改为“任务完成 / 返回主场景时单次拉取”，
        既避免了背景连接的重复建立，也让事件文本与“任务完成”提示的先后顺序确定。

        Returns:
            本次实际写入日志的消息条数。
        """
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
                app.session.user_name,
                app.session.game_name,
                since,
            )
        except Exception as e:
            logger.warning(f"_pull_new_messages: 拉取失败 error={e}")
            return 0

        log = self.query_one(RichLog)
        count = 0
        for msg in resp.session_messages:
            if app.session is None:
                break
            if msg.sequence_id > app.session.last_sequence_id:
                app.session.last_sequence_id = msg.sequence_id
            if msg.agent_event is None:
                continue
            log.write(format_agent_event(msg.agent_event))
            log.write("--------------------------------------")
            count += 1
            logger.debug(f"_pull_new_messages: 写入消息 seq={msg.sequence_id}")
        self._update_notify_badge()
        return count

    @work
    async def _do_view_messages(self, raw: str) -> None:
        """响应 /session 命令：获取最新未读消息，或指定 sequence_id 查看该点之后的消息。"""
        log = self.query_one(RichLog)
        raw = raw.strip()
        start_seq: Optional[int] = None
        if raw:
            try:
                start_seq = int(raw)
            except ValueError:
                log.write(f"[bold red]❌ 无效的 sequence_id：{raw}，已取消[/]")
                return
            log.write(f"[dim]▶ 拉取 sequence_id > {start_seq} 的消息...[/]")
        else:
            log.write("[dim]▶ 拉取最新未读消息...[/]")

        count = await self._pull_messages(start_seq)
        if count == 0:
            log.write("[dim](没有更多消息)[/]")

    @work
    async def _do_view_stage(self) -> None:
        """响应 /stage 命令：查看玩家当前所在场景的描述（StageDescriptionComponent.narrative）
        与场景内全部角色的外观（AppearanceComponent.appearance）。"""
        log = self.query_one(RichLog)
        app = self.game_client
        if app.session is None:
            return
        actor_name = app.session.actor_name

        try:
            stages_resp = await fetch_stages_state(
                app.session.user_name, app.session.game_name
            )
        except Exception as e:
            logger.error(f"_do_view_stage: 获取场景列表失败 error={e}")
            log.write(f"[bold red]❌ 获取场景列表失败: {e}[/]")
            return

        stage_name: Optional[str] = None
        actor_names: List[str] = []
        for name, actors in stages_resp.mapping.items():
            if actor_name in actors:
                stage_name = name
                actor_names = actors
                break

        if stage_name is None:
            log.write("[yellow]无法确定玩家当前所在场景。[/]")
            return

        try:
            details_resp = await fetch_entities_details(
                app.session.user_name,
                app.session.game_name,
                [stage_name] + actor_names,
            )
        except Exception as e:
            logger.error(f"_do_view_stage: 获取实体详情失败 error={e}")
            log.write(f"[bold red]❌ 获取实体详情失败: {e}[/]")
            return

        components_by_entity = {
            entity.name: entity.components
            for entity in details_resp.entities_serialization
        }

        log.write(
            f"[bold yellow]── 当前场景：{display_name(stage_name)} ──────────────────────────────────────[/]"
        )
        narrative: Optional[str] = None
        for comp in components_by_entity.get(stage_name, []):
            if comp.name == StageDescriptionComponent.__name__:
                narrative = StageDescriptionComponent(**comp.data).narrative
                break
        log.write(f"  {narrative}" if narrative else "  [dim]（该场景暂无描述）[/]")

        log.write("")
        log.write(
            "[bold yellow]── 场景内角色 ──────────────────────────────────────[/]"
        )
        if not actor_names:
            log.write("  [dim]（场景内暂无角色）[/]")
        for name in actor_names:
            appearance: Optional[str] = None
            for comp in components_by_entity.get(name, []):
                if comp.name == AppearanceComponent.__name__:
                    appearance = AppearanceComponent(**comp.data).appearance
                    break
            suffix = "  [dim](玩家)[/]" if name == actor_name else ""
            log.write(f"  [bold cyan]{display_name(name)}[/]{suffix}")
            log.write(
                f"    {appearance}"
                if appearance
                else "    [dim]（未持有 AppearanceComponent）[/]"
            )
        log.write("")

    def _update_notify_badge(self) -> None:
        """根据通知流探测到的最高 sequence_id 与当前已读 last_sequence_id 的差值，更新未读提示。

        同时始终显示本地已读游标（last_sequence_id）与服务器当前最高 sequence_id
        （notify_last_sequence_id），便于对照。
        """
        app = self.game_client
        badge = self.query_one("#home-notify", Static)
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
                f" —— 输入 [bold green]/session[/bold green] 查看"
            )
        else:
            badge.update(seq_info)

    @work(exclusive=True)
    async def _watch_notifications(self) -> None:
        """常驻监听会话消息 SSE 流，仅用于统计未读数量（高水位线，存于 GameSession），不写入日志、不推进 last_sequence_id。

        真正的内容展示由 `_pull_new_messages` / `_do_view_messages` 主动拉取完成，
        这里只负责让用户知道“服务器有新消息”，实现先有限披露（通知）再主动获取的模式。
        """
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

    @work
    async def _do_logout(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        user_name = app.session.user_name
        game_name = app.session.game_name

        log = self.query_one(RichLog)
        log.write("[dim]正在登出...[/]")
        logger.info(f"_do_logout: 开始登出 user_name={user_name} game_name={game_name}")
        try:
            msg = await server_logout(user_name, game_name)
            log.write(f"[bold green]✅ {msg}[/]")
            logger.info(
                f"_do_logout: 登出成功 user_name={user_name} msg={msg} → 清空会话状态 + pop_screen"
            )
            app.clear_session()
            await asyncio.sleep(0.5)
            self.app.pop_screen()
        except Exception as e:
            logger.error(f"_do_logout: 登出失败 user_name={user_name} error={e}")
            log.write(f"[bold red]❌ 登出失败: {e}[/]")
