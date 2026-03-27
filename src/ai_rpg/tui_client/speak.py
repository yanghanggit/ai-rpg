"""对话动作 Screen（SPEAK 玩家动作）"""

import asyncio
from typing import List, Literal

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Input, RichLog, Static

from .server_client import (
    fetch_stages_state,
    fetch_tasks_status,
    home_player_action as server_home_player_action,
)
from ..models.api import HomePlayerActionType
from ..models.task import TaskStatus

SPEAK_HEADER = """\
[bold cyan]── 对话 ──────────────────────────────────────[/]

输入编号选择对话目标，[bold]Escape[/] 取消返回。
"""


class SpeakScreen(Screen[None]):
    """对话 Screen：列出当前场景可交谈的 NPC，选目标后输入说话内容发送。"""

    CSS = """
    SpeakScreen {
        align: center middle;
    }

    #speak-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #speak-input-row {
        height: 3;
        dock: bottom;
    }

    #speak-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #speak-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "取消返回"),
    ]

    def __init__(self, user_name: str, game_name: str) -> None:
        super().__init__()
        self._user_name = user_name
        self._game_name = game_name
        self._actor_list: List[str] = []
        self._selected_target: str = ""
        self._state: Literal["select", "input"] = "select"

    def compose(self) -> ComposeResult:
        yield RichLog(id="speak-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="speak-input-row"):
            yield Static("> ", id="speak-prompt")
            yield Input(placeholder="输入编号选择对话目标...", id="speak-input")
        yield Footer()

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(SPEAK_HEADER)
        self._load_targets()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Input.Submitted, "#speak-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if not raw:
            return

        if self._state == "select":
            if not self._actor_list:
                log.write("[yellow]NPC 列表尚未加载，请稍候...[/]")
                return

            if not raw.isdigit():
                log.write("[red]请输入有效的编号。[/]")
                return

            idx = int(raw) - 1
            if idx < 0 or idx >= len(self._actor_list):
                log.write(f"[red]编号超出范围，请输入 1 ~ {len(self._actor_list)}。[/]")
                return

            self._selected_target = self._actor_list[idx]
            self._state = "input"
            log.write(
                f"[bold green]已选目标：[bold cyan]{self._selected_target}[/][bold green]"
                f"[/]\n[dim]请输入说话内容，按 Enter 发送：[/]"
            )
            inp = self.query_one(Input)
            inp.placeholder = "输入说话内容..."

        else:  # _state == "input"
            if not raw:
                return
            self._do_speak(raw)

    @work
    async def _load_targets(self) -> None:
        """加载当前场景中可交谈的 NPC 列表（过滤 player_actor 自身）。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在加载当前场景 NPC...[/]")
        logger.info(
            f"SpeakScreen._load_targets: user_name={self._user_name} game_name={self._game_name}"
        )

        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        bp = app.session_blueprint
        player_actor = bp.player_actor if bp else None

        try:
            resp = await fetch_stages_state(self._user_name, self._game_name)

            # 找到 player_actor 所在 stage
            current_stage: str | None = None
            if player_actor:
                for stage, actors in resp.mapping.items():
                    if player_actor in actors:
                        current_stage = stage
                        break

            if not current_stage:
                log.write("[yellow]无法确定玩家当前所在场景，显示所有 NPC。[/]")
                all_actors = [
                    a
                    for actors in resp.mapping.values()
                    for a in actors
                    if a != player_actor
                ]
                self._actor_list = all_actors
            else:
                stage_actors = resp.mapping.get(current_stage, [])
                self._actor_list = [a for a in stage_actors if a != player_actor]
                log.write(
                    f"[bold yellow]── 当前场景：[bold cyan]{current_stage}[/][bold yellow] ──[/]"
                )

            if not self._actor_list:
                log.write("[yellow]当前场景没有可交谈的 NPC。[/]")
                return

            log.write("[bold yellow]可对话的 NPC：[/]")
            for i, actor in enumerate(self._actor_list, 1):
                log.write(f"  [bold green]{i}.[/] {actor}")
            log.write("")
            log.write("[dim]输入编号选择对话目标：[/]")
            logger.info(
                f"SpeakScreen._load_targets: 加载完成 actor_list={self._actor_list}"
            )
        except Exception as e:
            logger.error(f"SpeakScreen._load_targets: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载 NPC 列表失败: {e}[/]")

    @work
    async def _do_speak(self, content: str) -> None:
        """发送对话动作，等待 pipeline 完成后返回 HomeScreen。"""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        log.write(f"[dim]▶ 发送对话：{self._selected_target} ← 「{content}」...[/]")
        logger.info(
            f"SpeakScreen._do_speak: target={self._selected_target} content={content}"
        )

        task_id: str = ""
        success = False
        try:
            resp = await server_home_player_action(
                self._user_name,
                self._game_name,
                HomePlayerActionType.SPEAK,
                {"target": self._selected_target, "content": content},
            )
            task_id = resp.task_id
            log.write(f"[dim]任务已创建：{task_id}[/]")
            logger.info(f"SpeakScreen._do_speak: 任务已创建 task_id={task_id}")
        except Exception as e:
            logger.error(f"SpeakScreen._do_speak: 发送失败 error={e}")
            log.write(f"[bold red]❌ 发送对话失败: {e}[/]")
            inp.disabled = False
            inp.focus()
            return

        # 轮询任务状态（最多 120 秒）
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
                    log.write("[bold green]✅ 对话完成，正在返回主场景...[/]")
                    logger.info(f"SpeakScreen._do_speak: 任务完成 task_id={task_id}")
                    success = True
                    break
                elif task_record.status == TaskStatus.FAILED:
                    error_msg = task_record.error or "未知错误"
                    log.write(f"[bold red]❌ 对话失败: {error_msg}[/]")
                    logger.error(
                        f"SpeakScreen._do_speak: 任务失败 task_id={task_id} error={error_msg}"
                    )
                    break
            except Exception as e:
                logger.warning(f"SpeakScreen._do_speak: 轮询失败 error={e}")
        else:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(f"SpeakScreen._do_speak: 轮询超时 task_id={task_id}")

        if success:
            await asyncio.sleep(0.5)
            self.app.pop_screen()
        else:
            inp.disabled = False
            inp.focus()
