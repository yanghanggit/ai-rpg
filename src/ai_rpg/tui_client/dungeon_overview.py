"""地下城总览 Screen"""

import asyncio
from typing import List, Optional

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Input, RichLog, Static

from ..models import Dungeon
from ..models.task import TaskStatus
from .server_client import (
    fetch_dungeon_list,
    fetch_entities_details,
    fetch_tasks_status,
    home_enter_dungeon as server_home_enter_dungeon,
)
from .server_client import home_generate_dungeon as server_home_generate_dungeon

OVERVIEW_HEADER = """\
[bold cyan]── 地下城总览 ──────────────────────────────────────[/]

输入编号查看副本详情，[bold]/list[/] 返回列表，[bold]/generate[/] 生成新地下城，[bold]/enter[/] 进入选中副本，[bold]Escape[/] 返回。
"""


class DungeonOverviewScreen(Screen[None]):
    """地下城总览 Screen：列出全部地下城副本，按编号查看详情。"""

    CSS = """
    DungeonOverviewScreen {
        align: center middle;
    }

    #dungeon-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #dungeon-input-row {
        height: 3;
        dock: bottom;
    }

    #dungeon-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #dungeon-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def __init__(self, user_name: str, game_name: str) -> None:
        super().__init__()
        self._user_name = user_name
        self._game_name = game_name
        self._dungeons: List[Dungeon] = []
        self._selected_dungeon: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield RichLog(id="dungeon-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="dungeon-input-row"):
            yield Static("> ", id="dungeon-prompt")
            yield Input(placeholder="输入编号查看副本详情...", id="dungeon-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(OVERVIEW_HEADER)
        self._load_dungeons()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Input.Submitted, "#dungeon-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if not raw:
            return

        if raw.lower() == "/list":
            log.clear()
            log.write(OVERVIEW_HEADER)
            self._render_list(log)
            return

        if raw.lower() == "/generate":
            self._do_generate_dungeon()
            return

        if raw.lower() == "/enter":
            if self._selected_dungeon is None:
                log.write("[yellow]请先输入编号选择一个地下城副本。[/]")
            else:
                self._do_enter_dungeon(self._selected_dungeon)
            return

        if not self._dungeons:
            log.write("[yellow]地下城列表尚未加载，请稍候...[/]")
            return

        if not raw.isdigit():
            log.write("[red]请输入有效编号（数字）或 /list 返回列表[/]")
            return

        idx = int(raw) - 1
        if idx < 0 or idx >= len(self._dungeons):
            log.write(
                f"[red]编号超出范围，请输入 1–{len(self._dungeons)} 之间的数字[/]"
            )
            return

        dungeon = self._dungeons[idx]
        self._selected_dungeon = dungeon.name
        log.write(f"[dim]> 查看副本：{dungeon.name}[/]")
        self._show_dungeon(dungeon, log)
        log.write(f"[dim]输入 /enter 进入此副本：[bold cyan]{dungeon.name}[/][/]")

    def _render_list(self, log: RichLog) -> None:
        """将已缓存的地下城列表渲染到 log。"""
        if not self._dungeons:
            log.write("[yellow]地下城列表尚未加载，请稍候...[/]")
            return
        log.write("[bold yellow]── 可用副本 ──────────────────────────────────────[/]")
        for i, dungeon in enumerate(self._dungeons, start=1):
            preview = dungeon.ecology[:40].replace("\n", " ")
            room_count = len(dungeon.rooms)
            log.write(
                f"  [bold]{i}.[/] [bold cyan]{dungeon.name}[/]"
                f"  [dim]{preview}…  ({room_count} 个房间)[/]"
            )
        log.write("")

    def _show_dungeon(self, dungeon: Dungeon, log: RichLog) -> None:
        """内联渲染地下城详情（纯同步，数据已在内存中）。"""
        log.write(
            f"[bold yellow]── 副本：{dungeon.name} ──────────────────────────────────────[/]"
        )
        log.write(f"  [bold]生态环境：[/] {dungeon.ecology}")
        log.write(f"  [bold]房间数：[/]   {len(dungeon.rooms)}")
        log.write("")

        for i, room in enumerate(dungeon.rooms, start=1):
            stage = room.stage
            log.write(f"  [bold cyan]房间 {i}：[/][green]{stage.name}[/]")
            if stage.actors:
                for actor in stage.actors:
                    stats = actor.character_stats
                    log.write(
                        f"    · [bold]{actor.name}[/]"
                        f"  HP:[yellow]{stats.max_hp}[/]"
                        f"  ATK:[red]{stats.attack}[/]"
                        f"  DEF:[blue]{stats.defense}[/]"
                    )
            else:
                log.write("    [dim]（无敌人）[/]")
        log.write("")

    @work
    async def _do_enter_dungeon(self, dungeon_name: str) -> None:
        """调用 home_enter_dungeon，成功后 push DungeonRoomScreen。"""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        log.write(f"[dim]▶ 正在进入地下城：{dungeon_name}...[/]")
        logger.info(f"DungeonOverviewScreen._do_enter_dungeon: dungeon={dungeon_name}")

        try:
            await server_home_enter_dungeon(
                self._user_name, self._game_name, dungeon_name
            )
            log.write(f"[bold green]✅ 已进入地下城：{dungeon_name}[/]")
            logger.info(
                f"DungeonOverviewScreen._do_enter_dungeon: 进入成功 dungeon={dungeon_name}"
            )
            from .dungeon_room import DungeonRoomScreen

            self.app.push_screen(DungeonRoomScreen(self._user_name, self._game_name))
        except Exception as e:
            logger.error(f"DungeonOverviewScreen._do_enter_dungeon: 进入失败 error={e}")
            log.write(f"[bold red]❌ 进入地下城失败: {e}[/]")
            inp.disabled = False
            inp.focus()

    @work
    async def _do_generate_dungeon(self) -> None:
        """触发地下城生成 pipeline，等待完成后刷新列表。"""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        log.write("[dim]▶ 正在触发地下城生成流程...[/]")
        logger.info(
            f"DungeonOverviewScreen._do_generate_dungeon: user={self._user_name} game={self._game_name}"
        )

        task_id: str = ""
        success = False
        try:
            resp = await server_home_generate_dungeon(self._user_name, self._game_name)
            task_id = resp.task_id
            log.write(f"[dim]任务已创建：{task_id}[/]")
            logger.info(
                f"DungeonOverviewScreen._do_generate_dungeon: 任务已创建 task_id={task_id}"
            )
        except Exception as e:
            logger.error(
                f"DungeonOverviewScreen._do_generate_dungeon: 请求失败 error={e}"
            )
            log.write(f"[bold red]❌ 地下城生成请求失败: {e}[/]")
            inp.disabled = False
            inp.focus()
            return

        _POLL_INTERVAL = 1.0
        _MAX_POLLS = 120
        for _ in range(_MAX_POLLS):
            await asyncio.sleep(_POLL_INTERVAL)
            try:
                status_resp = await fetch_tasks_status([task_id])
                if not status_resp.tasks:
                    continue
                task_record = status_resp.tasks[0]
                if task_record.status == TaskStatus.COMPLETED:
                    log.write("[bold green]✅ 地下城生成完成，正在刷新列表...[/]")
                    logger.info(
                        f"DungeonOverviewScreen._do_generate_dungeon: 任务完成 task_id={task_id}"
                    )
                    success = True
                    break
                elif task_record.status == TaskStatus.FAILED:
                    error_msg = task_record.error or "未知错误"
                    log.write(f"[bold red]❌ 地下城生成失败: {error_msg}[/]")
                    logger.error(
                        f"DungeonOverviewScreen._do_generate_dungeon: 任务失败 task_id={task_id} error={error_msg}"
                    )
                    break
            except Exception as e:
                logger.warning(
                    f"DungeonOverviewScreen._do_generate_dungeon: 轮询失败 error={e}"
                )
        else:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(
                f"DungeonOverviewScreen._do_generate_dungeon: 轮询超时 task_id={task_id}"
            )

        inp.disabled = False
        inp.focus()
        if success:
            self._load_dungeons()

    @work
    async def _load_dungeons(self) -> None:
        log = self.query_one(RichLog)
        logger.info("_load_dungeons: 正在获取地下城列表...")

        # 显示远征队名单
        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        bp = app.session_blueprint
        player_actor = bp.player_actor if bp else None
        if player_actor:
            try:
                resp = await fetch_entities_details(
                    self._user_name, self._game_name, [player_actor]
                )
                members: list[str] = []
                for entity in resp.entities_serialization:
                    for comp in entity.components:
                        if comp.name == "ExpeditionRosterComponent":
                            members = list(comp.data.get("members", []))
                            break
                roster = [player_actor] + members
                log.write(
                    "[bold yellow]── 当前远征队 ──────────────────────────────────────[/]"
                )
                for member in roster:
                    tag = "  [bold magenta][玩家][/]" if member == player_actor else ""
                    log.write(f"  · [bold cyan]{member}[/]{tag}")
                log.write("")
                logger.info(f"_load_dungeons: 远征队 roster={roster}")
            except Exception as e:
                logger.warning(f"_load_dungeons: 读取远征队失败 error={e}")

        try:
            resp2 = await fetch_dungeon_list()
            self._dungeons = resp2.dungeons
            if self._dungeons:
                self._render_list(log)
            else:
                log.write("[yellow]服务器暂无可用地下城。[/]")
            logger.info(f"_load_dungeons: 获取成功，共 {len(self._dungeons)} 个地下城")
        except Exception as e:
            logger.error(f"_load_dungeons: 获取失败 error={e}")
            log.write(f"[bold red]❌ 地下城列表加载失败: {e}[/]")
