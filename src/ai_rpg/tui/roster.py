"""远征队管理 Screen"""

from typing import List, Set
from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static
from .base import BaseGameScreen
from ..models import NPCComponent, PartyRosterComponent, PlayerComponent
from .server_client import (
    fetch_entities_details,
    fetch_stages_state,
    home_roster_add,
    home_roster_remove,
)
from .utils import display_name

ROSTER_HEADER = """\
[bold cyan]── 远征队管理 ──────────────────────────────────────[/]

输入编号 toggle 成员（未在队 → 加入，在队 → 移除），[bold]Escape[/] 返回。
"""


class RosterScreen(BaseGameScreen):
    """远征队管理 Screen：列出可加入的盟友，用编号 toggle 加入/移除远征队。"""

    CSS = """
    RosterScreen {
        align: center middle;
    }

    #roster-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #roster-input-row {
        height: 3;
        dock: bottom;
    }

    #roster-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #roster-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._npc_list: List[str] = []
        self._current_roster: Set[str] = set()

    def compose(self) -> ComposeResult:
        yield RichLog(id="roster-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="roster-input-row"):
            yield Static("> ", id="roster-prompt")
            yield Input(placeholder="输入编号 toggle ...", id="roster-input")
        # yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(ROSTER_HEADER)
        self._load_roster()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def _render_list(self) -> None:
        log = self.query_one(RichLog)
        log.write(
            "[bold yellow]── 当前盟友列表 ──────────────────────────────────────[/]"
        )
        for i, npc in enumerate(self._npc_list, 1):
            in_roster = npc in self._current_roster
            marker = "[bold green][✓][/]" if in_roster else "[ ]"
            log.write(f"  [bold green]{i}.[/] {marker} [cyan]{display_name(npc)}[/]")
        log.write("")
        log.write("[dim]输入编号切换成员状态：[/]")

    @on(Input.Submitted, "#roster-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if not raw:
            return

        if not self._npc_list:
            log.write("[yellow]盟友列表尚未加载，请稍候...[/]")
            return

        if not raw.isdigit():
            log.write("[red]请输入有效的编号。[/]")
            return

        idx = int(raw) - 1
        if idx < 0 or idx >= len(self._npc_list):
            log.write(f"[red]编号超出范围，请输入 1 ~ {len(self._npc_list)}。[/]")
            return

        npc_name = self._npc_list[idx]
        if npc_name in self._current_roster:
            self._do_remove(npc_name)
        else:
            self._do_add(npc_name)

    @work
    async def _load_roster(self) -> None:
        """从全部场景实际存在的 NPC 中获取盟友列表，从服务器读取当前远征队名单。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在加载远征队信息...[/]")

        app = self.game_client
        if app.session is None:
            log.write("[red]⚠ 无法取得会话信息。[/]")
            return
        user_name = app.session.user_name
        game_name = app.session.game_name
        player_actor_name = app.session.actor_name

        # 1. 获取全部场景分布，汇总场景内出现过的角色名称
        try:
            stages_resp = await fetch_stages_state(user_name, game_name)
        except Exception as e:
            logger.error(
                f"RosterScreen._load_roster: fetch_stages_state 失败 error={e}"
            )
            log.write(f"[bold red]❌ 场景状态查询失败: {e}[/]")
            return

        all_actor_names: List[str] = [
            actor_name
            for actor_names in stages_resp.mapping.values()
            for actor_name in actor_names
        ]

        # 2. 批量查询实体详情，筛选出持有 NPCComponent 且非 PlayerComponent 的角色
        self._npc_list = []
        if all_actor_names:
            try:
                entities_resp = await fetch_entities_details(
                    user_name, game_name, all_actor_names
                )
                for entity in entities_resp.entities_serialization:
                    component_names = {comp.name for comp in entity.components}
                    if (
                        NPCComponent.__name__ in component_names
                        and PlayerComponent.__name__ not in component_names
                    ):
                        self._npc_list.append(entity.name)
            except Exception as e:
                logger.error(f"RosterScreen._load_roster: 查询 NPC 列表失败 error={e}")
                log.write(f"[bold red]❌ 读取盟友列表失败: {e}[/]")
                return

        if not self._npc_list:
            log.write("[yellow]没有可加入远征队的盟友。[/]")
            return

        # 3. 使用玩家控制角色名，读取 PartyRosterComponent，取得当前远征队名单
        try:
            resp = await fetch_entities_details(
                user_name, game_name, [player_actor_name]
            )
            for entity in resp.entities_serialization:
                for comp in entity.components:
                    if comp.name == PartyRosterComponent.__name__:
                        self._current_roster = set(
                            PartyRosterComponent(**comp.data).members
                        )
                        break

            logger.info(
                f"RosterScreen._load_roster: 加载完成 npc_list={self._npc_list} roster={self._current_roster}"
            )
        except Exception as e:
            logger.error(
                f"RosterScreen._load_roster: 查询 player entity 失败 error={e}"
            )
            log.write(f"[bold red]❌ 读取当前远征队失败: {e}[/]")
            return

        self._render_list()

    @work
    async def _do_add(self, npc_name: str) -> None:
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True
        log.write(f"[dim]▶ 正在将 {display_name(npc_name)} 加入远征队...[/]")
        logger.info(f"RosterScreen._do_add: npc_name={npc_name}")

        app = self.game_client
        if app.session is None:
            return
        try:
            await home_roster_add(
                app.session.user_name, app.session.game_name, npc_name
            )
            self._current_roster.add(npc_name)
            log.write(f"[bold green]✅ {display_name(npc_name)} 已加入远征队[/]")
            logger.info(f"RosterScreen._do_add: 成功 npc_name={npc_name}")
        except Exception as e:
            logger.error(f"RosterScreen._do_add: 失败 npc_name={npc_name} error={e}")
            log.write(f"[bold red]❌ 加入失败: {e}[/]")
        finally:
            inp.disabled = False
            inp.focus()
        self._render_list()

    @work
    async def _do_remove(self, npc_name: str) -> None:
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True
        log.write(f"[dim]▶ 正在将 {display_name(npc_name)} 从远征队移除...[/]")
        logger.info(f"RosterScreen._do_remove: npc_name={npc_name}")

        app = self.game_client
        if app.session is None:
            return
        try:
            await home_roster_remove(
                app.session.user_name, app.session.game_name, npc_name
            )
            self._current_roster.discard(npc_name)
            log.write(f"[bold green]✅ {display_name(npc_name)} 已从远征队移除[/]")
            logger.info(f"RosterScreen._do_remove: 成功 npc_name={npc_name}")
        except Exception as e:
            logger.error(f"RosterScreen._do_remove: 失败 npc_name={npc_name} error={e}")
            log.write(f"[bold red]❌ 移除失败: {e}[/]")
        finally:
            inp.disabled = False
            inp.focus()
        self._render_list()
