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

输入编号 toggle 成员（未在队 → 加入，在队 → 移除），[bold]0[/] 清屏，[bold]Escape[/] 返回。
"""


class HomePartyRosterManagementScreen(BaseGameScreen):
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

    def compose(self) -> ComposeResult:
        yield RichLog(id="roster-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="roster-input-row"):
            yield Static("> ", id="roster-prompt")
            yield Input(placeholder="输入编号 toggle ...", id="roster-input")
        # yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(ROSTER_HEADER)
        self._refresh()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def _render_list(self, npc_list: List[str], current_roster: Set[str]) -> None:
        log = self.query_one(RichLog)
        log.write(
            "[bold yellow]── 当前盟友列表 ──────────────────────────────────────[/]"
        )
        for i, npc in enumerate(npc_list, 1):
            in_roster = npc in current_roster
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

        if raw == "0":
            log.clear()
            log.write(ROSTER_HEADER)
            self._refresh()
            return

        if not raw.isdigit():
            log.write("[red]请输入有效的编号。[/]")
            return

        self._toggle_member(int(raw) - 1)

    async def _fetch_npc_list(self, user_name: str, game_name: str) -> List[str]:
        """从全部场景实际存在的 NPC 中获取盟友列表（持有 NPCComponent 且非 PlayerComponent，不含玩家自身）。"""
        stages_resp = await fetch_stages_state(user_name, game_name)
        all_actor_names: List[str] = [
            actor_name
            for actor_names in stages_resp.mapping.values()
            for actor_name in actor_names
        ]

        npc_list: List[str] = []
        if all_actor_names:
            entities_resp = await fetch_entities_details(
                user_name, game_name, all_actor_names
            )
            for entity in entities_resp.entities_serialization:
                component_names = {comp.name for comp in entity.components}
                if (
                    NPCComponent.__name__ in component_names
                    and PlayerComponent.__name__ not in component_names
                ):
                    npc_list.append(entity.name)
        return npc_list

    async def _fetch_current_roster(
        self, user_name: str, game_name: str, player_actor_name: str
    ) -> Set[str]:
        """读取玩家实体的 PartyRosterComponent，取得当前远征队名单。"""
        resp = await fetch_entities_details(user_name, game_name, [player_actor_name])
        for entity in resp.entities_serialization:
            for comp in entity.components:
                if comp.name == PartyRosterComponent.__name__:
                    return set(PartyRosterComponent(**comp.data).members)
        return set()

    @work
    async def _refresh(self) -> None:
        """通过实时 GET 重新拉取盟友列表与当前远征队名单并渲染，不做任何本地缓存。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在加载远征队信息...[/]")

        app = self.game_client
        if app.session is None:
            log.write("[red]⚠ 无法取得会话信息。[/]")
            return
        user_name = app.session.user_name
        game_name = app.session.game_name
        player_actor_name = app.session.actor_name

        try:
            npc_list = await self._fetch_npc_list(user_name, game_name)
        except Exception as e:
            logger.error(f"RosterScreen._refresh: 查询 NPC 列表失败 error={e}")
            log.write(f"[bold red]❌ 读取盟友列表失败: {e}[/]")
            return

        if not npc_list:
            log.write("[yellow]没有可加入远征队的盟友。[/]")
            return

        try:
            current_roster = await self._fetch_current_roster(
                user_name, game_name, player_actor_name
            )
        except Exception as e:
            logger.error(f"RosterScreen._refresh: 查询当前远征队失败 error={e}")
            log.write(f"[bold red]❌ 读取当前远征队失败: {e}[/]")
            return

        logger.info(
            f"RosterScreen._refresh: 加载完成 npc_list={npc_list} roster={current_roster}"
        )
        self._render_list(npc_list, current_roster)

    @work
    async def _toggle_member(self, idx: int) -> None:
        """根据编号切换成员的远征队状态；编号范围与在队状态均通过实时 GET 判定，不使用本地缓存。"""
        log = self.query_one(RichLog)

        app = self.game_client
        if app.session is None:
            log.write("[red]⚠ 无法取得会话信息。[/]")
            return
        user_name = app.session.user_name
        game_name = app.session.game_name
        player_actor_name = app.session.actor_name

        try:
            npc_list = await self._fetch_npc_list(user_name, game_name)
        except Exception as e:
            logger.error(f"RosterScreen._toggle_member: 查询 NPC 列表失败 error={e}")
            log.write(f"[bold red]❌ 读取盟友列表失败: {e}[/]")
            return

        if not npc_list:
            log.write("[yellow]没有可加入远征队的盟友。[/]")
            return

        if idx < 0 or idx >= len(npc_list):
            log.write(f"[red]编号超出范围，请输入 1 ~ {len(npc_list)}。[/]")
            return

        npc_name = npc_list[idx]

        try:
            current_roster = await self._fetch_current_roster(
                user_name, game_name, player_actor_name
            )
        except Exception as e:
            logger.error(f"RosterScreen._toggle_member: 查询当前远征队失败 error={e}")
            log.write(f"[bold red]❌ 读取当前远征队失败: {e}[/]")
            return

        inp = self.query_one(Input)
        inp.disabled = True
        try:
            if npc_name in current_roster:
                await self._remove_member(user_name, game_name, npc_name)
            else:
                await self._add_member(user_name, game_name, npc_name)
        finally:
            inp.disabled = False
            inp.focus()

        self._refresh()

    async def _add_member(self, user_name: str, game_name: str, npc_name: str) -> None:
        log = self.query_one(RichLog)
        log.write(f"[dim]▶ 正在将 {display_name(npc_name)} 加入远征队...[/]")
        logger.info(f"RosterScreen._add_member: npc_name={npc_name}")

        try:
            await home_roster_add(user_name, game_name, npc_name)
            log.write(f"[bold green]✅ {display_name(npc_name)} 已加入远征队[/]")
            logger.info(f"RosterScreen._add_member: 成功 npc_name={npc_name}")
        except Exception as e:
            logger.error(
                f"RosterScreen._add_member: 失败 npc_name={npc_name} error={e}"
            )
            log.write(f"[bold red]❌ 加入失败: {e}[/]")

    async def _remove_member(
        self, user_name: str, game_name: str, npc_name: str
    ) -> None:
        log = self.query_one(RichLog)
        log.write(f"[dim]▶ 正在将 {display_name(npc_name)} 从远征队移除...[/]")
        logger.info(f"RosterScreen._remove_member: npc_name={npc_name}")

        try:
            await home_roster_remove(user_name, game_name, npc_name)
            log.write(f"[bold green]✅ {display_name(npc_name)} 已从远征队移除[/]")
            logger.info(f"RosterScreen._remove_member: 成功 npc_name={npc_name}")
        except Exception as e:
            logger.error(
                f"RosterScreen._remove_member: 失败 npc_name={npc_name} error={e}"
            )
            log.write(f"[bold red]❌ 移除失败: {e}[/]")
