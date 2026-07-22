"""游戏主场景 Screen（Home 状态）"""

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static
from .base import BaseGameScreen
import asyncio
from loguru import logger

from .server_client import (
    stream_session_messages,
    fetch_stages_state,
    watch_task_until_done,
    TaskFailedError,
    home_advance as server_home_advance,
    logout as server_logout,
)
from ..models.agent_event import (
    AnyAgentEvent,
    SpeakEvent,
    WhisperEvent,
    AnnounceEvent,
    MindEvent,
    QueryEvent,
    TransStageEvent,
    CombatInitiationEvent,
    CombatArbitrationEvent,
    CombatArchiveEvent,
    AppearanceUpdateEvent,
)
from .utils import display_name

MENU_TEXT = """\
[bold yellow]可用操作（输入编号执行）：[/]

[bold cyan]── 查看 ──────────────────────────────────────[/]
  [bold green]1[/]  实体浏览器    列出全部场景与角色
  [bold green]2[/]  地下城总览    列出全部副本预览

[bold cyan]── 行动 ──────────────────────────────────────[/]
  [bold green]3[/]  推进家园      执行一轮 home pipeline
  [bold green]4[/]  与NPC对话     与当前场景 NPC 对话
  [bold green]5[/]  切换场景      移动到其他场景
  [bold green]6[/]  道具管理      背包与储物箱道具移动
  [bold green]7[/]  管理远征队    加入/移除远征队成员
  [bold green]8[/]  穿戴时装      为目标安装/移除时装
  [bold green]9[/]  制造工坊      合成消耗品
  [bold green]10[/] 工坊锻造      用材料锻造装备
  [bold green]11[/] 工坊制衣      用材料制作时装
[bold cyan]── 系统 ──────────────────────────────────────[/]
  [bold green]0[/]  显示此菜单
  [bold dim]Escape[/]  登出并返回主菜单

"""


def _format_agent_event(event: AnyAgentEvent) -> str:
    """将 AnyAgentEvent 渲染为 Rich markup 字符串。"""
    match event:
        case SpeakEvent():
            return (
                f"[bold yellow]{event.actor}[/] 对 [yellow]{event.target}[/] 说：\n"
                f"  「{event.content}」"
            )
        case WhisperEvent():
            return (
                f"[dim]{event.actor} 悄悄向 {event.target} 耳语：「{event.content}」[/]"
            )
        case AnnounceEvent():
            return f"[bold magenta]【{event.actor}】[/] 在 {event.stage} 宣告：{event.content}"
        case MindEvent():
            return f"[dim italic]（{event.actor} 心想：{event.content}）[/]"
        case QueryEvent():
            return f"[dim]{event.actor} 询问：{event.question}[/]"
        case TransStageEvent():
            return f"[cyan]▶ {event.actor}  {event.stage} → {event.target}[/]"
        case CombatInitiationEvent():
            return f"[bold red]⚔ {event.actor} 发起战斗！[/]"
        case CombatArbitrationEvent():
            return f"[bold]{event.narrative}[/]"
        case CombatArchiveEvent():
            return f"[dim]{event.actor} 战斗归档：{event.summary}[/]"
        case AppearanceUpdateEvent():
            return (
                f"[bold green]✨ {event.actor} 外观已更新：[/]\n"
                f"  [dim]{event.appearance}[/]"
            )
        case _:
            return f"[dim cyan]{event.message}[/]"


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
        with Horizontal(id="home-input-row"):
            yield Static("> ", id="home-prompt")
            yield Input(placeholder="输入编号执行操作...", id="home-input")

    def on_mount(self) -> None:
        _app = self.game_client
        log = self.query_one(RichLog)
        self._write_header(log)
        log.write(MENU_TEXT)
        if _app.session:
            logger.info(
                f"HomeScreen: 进入主场景 user_name={_app.session.user_name}"
                f" game_name={_app.session.game_name}"
            )
        self.query_one(Input).focus()
        self._poll_messages()

    def on_unmount(self) -> None:
        logger.info("HomeScreen: on_unmount，停止轮询")

    def on_screen_suspend(self) -> None:
        """推入子 Screen 时暂停轮询。"""
        logger.info("HomeScreen: on_screen_suspend，暂停轮询")

    def on_screen_resume(self) -> None:
        """从子 Screen 返回时恢复轮询。"""
        logger.info("HomeScreen: on_screen_resume，恢复轮询")
        self._poll_messages()
        self.query_one(Input).focus()

    def action_logout(self) -> None:
        """ESC 触发登出。"""
        self._do_logout()

    def _write_header(self, log: RichLog) -> None:
        """写入顶部基础信息（玩家/游戏/角色），合入主 log，会话期间不会变化，只需写入一次。"""
        session = self.game_client.session
        if session is None:
            #log.write("[bold cyan]AI RPG DBG  游戏主场景[/]")
            return
        actor_text = (
            display_name(session.actor_name) if session.actor_name else "（未知）"
        )
        log.write(
            #"[bold cyan]AI RPG DBG  游戏主场景[/]\n"
            f"[bold green]▶ 玩家：[/][bold]{session.user_name}[/]  "
            f"[bold green]游戏：[/][bold]{session.game_name}[/]  "
            f"[bold green]角色：[/][bold cyan]{actor_text}[/]"
            f"\n\n"
        )

    @on(Input.Submitted, "#home-input")
    def handle_command(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if not cmd:
            return

        log.write(f"[dim]> {cmd}[/]")
        logger.debug(f"HomeScreen: 收到命令 cmd={cmd}")

        if cmd == "0":
            log.write(MENU_TEXT)
        elif cmd == "1":
            from .entity_browser import EntityBrowserScreen

            self.app.push_screen(EntityBrowserScreen())
        elif cmd == "2":
            from .dungeon_overview import DungeonOverviewScreen

            self.app.push_screen(DungeonOverviewScreen())
        elif cmd == "3":
            self._do_advance()
        elif cmd == "4":
            from .speak import SpeakScreen

            self.app.push_screen(SpeakScreen())
        elif cmd == "5":
            from .switch_stage import SwitchStageScreen

            self.app.push_screen(SwitchStageScreen())
        elif cmd == "6":
            from .item_management import ItemManagementScreen

            self.app.push_screen(ItemManagementScreen())
        elif cmd == "7":
            from .roster import RosterScreen

            self.app.push_screen(RosterScreen())
        elif cmd == "8":
            from .wear_costume import WearCostumeScreen

            self.app.push_screen(WearCostumeScreen())
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

        推进前先查询场景状态，确定玩家当前所在场景内的全部角色（含玩家自身），
        将其作为 actors 传给服务端，让这些角色本轮真正触发行动规划。
        """
        app = self.game_client
        if app.session is None:
            return
        user_name = app.session.user_name
        game_name = app.session.game_name
        player_actor = app.session.actor_name

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

            # 找到 player_actor 所在 stage，取出该场景内的全部角色（含玩家自身）
            current_stage: str = ""
            if player_actor:
                for stage, actors in stages_resp.mapping.items():
                    if player_actor in actors:
                        current_stage = stage
                        break

            if not current_stage:
                log.write("[bold red]❌ 无法确定玩家当前所在场景，推进已取消[/]")
                logger.error("_do_advance: 无法确定玩家当前所在场景")
                inp.disabled = False
                inp.focus()
                return

            actor_names = stages_resp.mapping.get(current_stage, [])
            if not actor_names:
                log.write("[bold red]❌ 当前场景没有可推进的角色[/]")
                logger.error(f"_do_advance: 场景 {current_stage} 没有角色")
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
            log.write("[bold green]✅ 推进完成[/]")
            logger.info(f"_do_advance: 任务完成 task_id={task_id}")
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

    @work(exclusive=True)
    async def _poll_messages(self) -> None:
        app = self.game_client
        if app.session is None:
            return
        user_name = app.session.user_name
        game_name = app.session.game_name
        logger.info(
            f"_poll_messages: 启动 SSE 流 user_name={user_name} game_name={game_name}"
        )
        try:
            async for msg in stream_session_messages(
                user_name,
                game_name,
                app.session.last_sequence_id,
            ):
                if app.session is None:
                    break
                if msg.sequence_id > app.session.last_sequence_id:
                    app.session.last_sequence_id = msg.sequence_id
                if msg.agent_event is None:
                    continue
                log = self.query_one(RichLog)
                log.write(_format_agent_event(msg.agent_event))
                log.write("--------------------------------------")
                logger.debug(f"_poll_messages: 收到消息 seq={msg.sequence_id}")
        except Exception as e:
            logger.warning(f"_poll_messages: SSE 流中断 error={e}")
        logger.info(f"_poll_messages: SSE 流已停止 user_name={user_name}")

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
