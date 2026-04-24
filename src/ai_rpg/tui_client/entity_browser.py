"""实体浏览器 Screen"""

import json
from typing import Dict, List, Set, Tuple

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Input, RichLog, Static

from .server_client import fetch_entities_details, fetch_stages_state
from .utils import display_name

BROWSER_HEADER = """\
[bold cyan]── 实体浏览器 ──────────────────────────────────────[/]

输入编号查看实体组件详情，[bold]0[/] 返回列表，[bold]Escape[/] 返回。
"""


class EntityBrowserScreen(Screen[None]):
    """实体浏览器 Screen：列出全部 Stage / Actor，按编号查看组件详情。"""

    CSS = """
    EntityBrowserScreen {
        align: center middle;
    }

    #browser-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #browser-input-row {
        height: 3;
        dock: bottom;
    }

    #browser-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #browser-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        # (entity_name, entity_type) — type is "场景" or "角色"
        self._entity_list: List[Tuple[str, str]] = []
        self._stage_mapping: Dict[str, List[str]] = {}

    def compose(self) -> ComposeResult:
        yield RichLog(id="browser-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="browser-input-row"):
            yield Static("> ", id="browser-prompt")
            yield Input(placeholder="输入编号查看详情...", id="browser-input")
        # yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(BROWSER_HEADER)
        self._load_entities()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Input.Submitted, "#browser-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if not raw:
            return

        if raw == "0":
            log.clear()
            log.write(BROWSER_HEADER)
            self._render_list(log)
            return

        if not self._entity_list:
            log.write("[yellow]实体列表尚未加载，请稍候...[/]")
            return

        if not raw.isdigit():
            log.write("[red]请输入有效编号（数字）[/]")
            return

        idx = int(raw) - 1
        if idx < 0 or idx >= len(self._entity_list):
            log.write(
                f"[red]编号超出范围，请输入 1–{len(self._entity_list)} 之间的数字[/]"
            )
            return

        entity_name, entity_type = self._entity_list[idx]
        log.write(f"[dim]> 查看 {entity_type}：{entity_name}[/]")
        self._show_entity(entity_name)

    def _render_list(self, log: RichLog) -> None:
        """将已缓存的实体列表渲染到 log。"""
        if not self._entity_list:
            log.write("[yellow]实体列表尚未加载，请稍候...[/]")
            return
        log.write(
            "[bold yellow]── 场景 ─────────────────────────────────────────────[/]"
        )
        for i, (name, etype) in enumerate(self._entity_list, start=1):
            if etype == "场景":
                actors_in = self._stage_mapping.get(name, [])
                actors_str = (
                    "、".join(display_name(a) for a in actors_in)
                    if actors_in
                    else "[dim]（空）[/]"
                )
                log.write(
                    f"  [bold]{i}.[/] [bold cyan]{display_name(name)}[/]  → {actors_str}"
                )
        log.write(
            "[bold yellow]── 角色 ─────────────────────────────────────────────[/]"
        )
        for i, (name, etype) in enumerate(self._entity_list, start=1):
            if etype == "角色":
                log.write(f"  [bold]{i}.[/] [green]{display_name(name)}[/]")
        log.write("")

    @work
    async def _load_entities(self) -> None:
        log = self.query_one(RichLog)
        logger.info(f"_load_entities: 加载实体列表")
        try:
            from .app import GameClient

            app: GameClient = self.app  # type: ignore[assignment]
            if app.session is None:
                return
            user_name = app.session.user_name
            game_name = app.session.game_name
            resp = await fetch_stages_state(user_name, game_name)
            self._entity_list.clear()
            self._stage_mapping = dict(resp.mapping)

            stages = list(resp.mapping.keys())
            # collect unique actors in order of appearance
            seen: Set[str] = set()
            actors: List[str] = []
            for actor_list in resp.mapping.values():
                for actor in actor_list:
                    if actor not in seen:
                        seen.add(actor)
                        actors.append(actor)

            for stage in stages:
                self._entity_list.append((stage, "场景"))
            for actor in actors:
                self._entity_list.append((actor, "角色"))

            if not self._entity_list:
                log.write("[yellow]暂无实体数据。[/]")
                return

            self._render_list(log)
            logger.info(f"_load_entities: 加载成功，共 {len(self._entity_list)} 个实体")
        except Exception as e:
            logger.error(f"_load_entities: 加载失败 error={e}")
            log.write(f"[bold red]❌ 实体列表加载失败: {e}[/]")

    @work
    async def _show_entity(self, entity_name: str) -> None:
        log = self.query_one(RichLog)
        log.write(f"[dim]正在查询实体：{entity_name} ...[/]")
        logger.info(f"_show_entity: 查询 entity_name={entity_name}")
        try:
            from .app import GameClient

            app: GameClient = self.app  # type: ignore[assignment]
            if app.session is None:
                return
            resp = await fetch_entities_details(
                app.session.user_name, app.session.game_name, [entity_name]
            )
            if not resp.entities_serialization:
                log.write(f"[yellow]未找到实体：{entity_name}[/]")
                return
            for entity in resp.entities_serialization:
                log.write(
                    f"[bold yellow]── 实体：{display_name(entity.name)} ──────────────────────────────────────[/]"
                )
                for comp in entity.components:
                    data_str = json.dumps(comp.data, ensure_ascii=False, indent=2)
                    log.write(f"  [bold cyan][组件][/] [green]{comp.name}[/]")
                    log.write(f"[dim]{data_str}[/]")
                log.write("")
            logger.info(f"_show_entity: 查询成功 entity_name={entity_name}")
        except Exception as e:
            logger.error(f"_show_entity: 查询失败 entity_name={entity_name} error={e}")
            log.write(f"[bold red]❌ 查询失败: {e}[/]")
