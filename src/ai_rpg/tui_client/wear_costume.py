"""穿戴时装 Screen：为目标角色安装或移除时装。"""

from typing import List, Literal

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from .base import BaseGameScreen
from .server_client import (
    fetch_entities_details,
    fetch_stages_state,
    home_wear_costume,
    watch_task_until_done,
    TaskFailedError,
)
from .utils import display_name
from ..models import StorageComponent

WEAR_COSTUME_HEADER = """\
[bold cyan]── 穿戴时装 ──────────────────────────────────────[/]

选择时装后再选择目标角色，[bold]Escape[/] 返回。
"""


class WearCostumeScreen(BaseGameScreen):
    """穿戴时装 Screen：两步操作，先选时装再选目标角色。"""

    CSS = """
    WearCostumeScreen {
        align: center middle;
    }

    #costume-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #costume-input-row {
        height: 3;
        dock: bottom;
    }

    #costume-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #costume-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Back"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._costume_list: List[str] = []  # names of CostumeItem in storage
        self._target_list: List[str] = []  # "" = player self, others = NPC names
        self._step: Literal["select_costume", "select_target"] = "select_costume"
        self._selected_item: str = ""  # chosen costume name (empty = remove)

    def compose(self) -> ComposeResult:
        yield RichLog(id="costume-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="costume-input-row"):
            yield Static("> ", id="costume-prompt")
            yield Input(placeholder="输入编号...", id="costume-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(WEAR_COSTUME_HEADER)
        self._load_data()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Input.Submitted, "#costume-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if not raw:
            return

        if not raw.isdigit():
            log.write("[red]请输入有效的编号。[/]")
            return

        idx = int(raw)

        if self._step == "select_costume":
            self._handle_costume_selection(idx)
        else:
            self._handle_target_selection(idx)

    def _handle_costume_selection(self, idx: int) -> None:
        log = self.query_one(RichLog)

        if not self._costume_list and idx != 0:
            log.write("[yellow]时装列表尚未加载，请稍候...[/]")
            return

        # 0 = 移除时装，1..N = costume
        max_idx = len(self._costume_list)
        if idx < 0 or idx > max_idx:
            log.write(f"[red]编号超出范围，请输入 0 ~ {max_idx}。[/]")
            return

        if idx == 0:
            self._selected_item = ""
            log.write("[dim]✓ 选择：移除当前时装[/]")
        else:
            self._selected_item = self._costume_list[idx - 1]
            log.write(
                f"[dim]✓ 选择时装：[bold magenta]{display_name(self._selected_item)}[/][/]"
            )

        self._step = "select_target"
        self._show_target_list()

    def _handle_target_selection(self, idx: int) -> None:
        log = self.query_one(RichLog)

        # 1 = player self (target_name=""), 2..M = NPCs
        max_idx = 1 + len(self._target_list)
        if idx < 1 or idx > max_idx:
            log.write(f"[red]编号超出范围，请输入 1 ~ {max_idx}。[/]")
            return

        if idx == 1:
            target_name = ""
            log.write("[dim]✓ 目标：玩家自身[/]")
        else:
            target_name = self._target_list[idx - 2]
            log.write(f"[dim]✓ 目标：[bold cyan]{display_name(target_name)}[/][/]")

        self._do_wear_costume(self._selected_item, target_name)

    def _show_costume_list(self) -> None:
        log = self.query_one(RichLog)
        log.write("[bold yellow]── 可用时装 ──────────────────────────────────────[/]")
        log.write("  [bold green]0.[/] [dim]移除当前时装（恢复基础外观）[/]")
        if self._costume_list:
            for i, name in enumerate(self._costume_list, 1):
                log.write(f"  [bold green]{i}.[/] [magenta]{display_name(name)}[/]")
        else:
            log.write("  [dim]（储物箱中暂无时装）[/]")
        log.write("")
        log.write("[dim]输入编号选择时装（0 = 移除时装）：[/]")

    def _show_target_list(self) -> None:
        log = self.query_one(RichLog)
        log.write("[bold yellow]── 选择目标角色 ──────────────────────────────────[/]")
        log.write("  [bold green]1.[/] [cyan]玩家自身[/]")
        for i, name in enumerate(self._target_list, 2):
            log.write(f"  [bold green]{i}.[/] [cyan]{display_name(name)}[/]")
        log.write("")
        log.write("[dim]输入编号选择目标角色：[/]")

    @work
    async def _load_data(self) -> None:
        """加载储物箱时装列表与当前场景角色列表。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在加载时装与角色信息...[/]")

        app = self.game_client
        if app.session is None:
            log.write("[red]⚠ 无法取得会话信息。[/]")
            return

        user_name = app.session.user_name
        game_name = app.session.game_name
        player_actor = app.session.blueprint.player_actor
        storage_entity = app.session.blueprint.storage_entity

        # --- 加载时装（from StorageComponent）---
        try:
            details_resp = await fetch_entities_details(
                user_name, game_name, [player_actor, storage_entity]
            )
            for entity in details_resp.entities_serialization:
                for comp in entity.components:
                    if comp.name == StorageComponent.__name__:
                        self._costume_list = [
                            item["name"]
                            for item in comp.data.get("items", [])
                            if item.get("type") == "CostumeItem"
                        ]
        except Exception as e:
            logger.warning(f"WearCostumeScreen._load_data: 加载时装失败 error={e}")
            log.write(f"[yellow]⚠ 加载时装列表失败: {e}[/]")

        # --- 加载当前场景 NPC ---
        try:
            stages_resp = await fetch_stages_state(user_name, game_name)
            for stage, actors in stages_resp.mapping.items():
                if player_actor and player_actor in actors:
                    self._target_list = [a for a in actors if a != player_actor]
                    break
        except Exception as e:
            logger.warning(f"WearCostumeScreen._load_data: 加载场景角色失败 error={e}")
            log.write(f"[yellow]⚠ 加载场景角色失败: {e}[/]")

        logger.info(
            f"WearCostumeScreen._load_data: costumes={self._costume_list} targets={self._target_list}"
        )
        self._show_costume_list()

    @work
    async def _do_wear_costume(self, item_name: str, target_name: str) -> None:
        """发送穿戴时装请求并等待任务完成。"""
        app = self.game_client
        if app.session is None:
            return
        user_name = app.session.user_name
        game_name = app.session.game_name

        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        action_label = (
            f"移除时装 → {display_name(target_name) if target_name else '玩家自身'}"
            if not item_name
            else f"穿戴「{display_name(item_name)}」→ {display_name(target_name) if target_name else '玩家自身'}"
        )
        log.write(f"[bold yellow]── 外观更新 ──────────────────────────────────────[/]")
        log.write(f"[dim]▶ {action_label}...[/]")
        logger.info(
            f"WearCostumeScreen._do_wear_costume: user={user_name} item={item_name!r} target={target_name!r}"
        )

        try:
            resp = await home_wear_costume(user_name, game_name, item_name, target_name)
            task_id = resp.task_id
            log.write(f"[dim]任务已创建：{task_id}[/]")
        except Exception as e:
            logger.error(f"WearCostumeScreen._do_wear_costume: 请求失败 error={e}")
            log.write(f"[bold red]❌ 请求失败: {e}[/]")
            inp.disabled = False
            inp.focus()
            return

        try:
            await watch_task_until_done(task_id)
            log.write("[bold green]✅ 外观更新完成[/]")
            logger.info(
                f"WearCostumeScreen._do_wear_costume: 任务完成 task_id={task_id}"
            )
        except TaskFailedError as e:
            log.write(f"[bold red]❌ 外观更新失败: {e}[/]")
            logger.error(
                f"WearCostumeScreen._do_wear_costume: 任务失败 task_id={task_id} error={e}"
            )
        except TimeoutError:
            log.write("[bold yellow]⚠️ 外观更新超时，请检查服务器状态[/]")
            logger.warning(
                f"WearCostumeScreen._do_wear_costume: 任务轮询超时 task_id={task_id}"
            )
        except Exception as e:
            log.write(f"[bold red]❌ 等待任务失败: {e}[/]")
            logger.warning(
                f"WearCostumeScreen._do_wear_costume: 等待任务失败 error={e}"
            )

        inp.disabled = False
        inp.focus()
        self.app.pop_screen()
