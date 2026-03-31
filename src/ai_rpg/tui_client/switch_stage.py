"""场景切换动作 Screen（SWITCH_STAGE 玩家动作）"""

import asyncio
from typing import List

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Input, RichLog, Static

from .server_client import (
    fetch_entities_details,
    fetch_stages_state,
    fetch_tasks_status,
    home_player_action as server_home_player_action,
)
from ..models.api import HomePlayerActionType
from ..models.task import TaskStatus

SWITCH_STAGE_HEADER = """\
[bold cyan]── 场景切换 ──────────────────────────────────────[/]

输入编号切换到目标场景，[bold]Escape[/] 取消返回。
"""


class SwitchStageScreen(Screen[None]):
    """场景切换 Screen：列出可前往的场景，输入编号后直接发送切换动作。"""

    CSS = """
    SwitchStageScreen {
        align: center middle;
    }

    #switch-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #switch-input-row {
        height: 3;
        dock: bottom;
    }

    #switch-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #switch-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "Cancel"),
    ]

    def __init__(self, user_name: str, game_name: str) -> None:
        super().__init__()
        self._user_name = user_name
        self._game_name = game_name
        self._stage_list: List[str] = []

    def compose(self) -> ComposeResult:
        yield RichLog(id="switch-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="switch-input-row"):
            yield Static("> ", id="switch-prompt")
            yield Input(placeholder="输入编号切换场景...", id="switch-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(SWITCH_STAGE_HEADER)
        self._load_stages()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Input.Submitted, "#switch-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        log = self.query_one(RichLog)

        if not raw:
            return

        if not self._stage_list:
            log.write("[yellow]场景列表尚未加载，请稍候...[/]")
            return

        if not raw.isdigit():
            log.write("[red]请输入有效的编号。[/]")
            return

        idx = int(raw) - 1
        if idx < 0 or idx >= len(self._stage_list):
            log.write(f"[red]编号超出范围，请输入 1 ~ {len(self._stage_list)}。[/]")
            return

        target_stage = self._stage_list[idx]
        self._do_switch_stage(target_stage)

    @work
    async def _load_stages(self) -> None:
        """加载可前往的场景列表（排除玩家当前场景和玩家专属场景）。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在加载场景列表...[/]")
        logger.info(
            f"SwitchStageScreen._load_stages: user_name={self._user_name} game_name={self._game_name}"
        )

        from .app import GameClient

        app: GameClient = self.app  # type: ignore[assignment]
        bp = app.session_blueprint
        player_actor = bp.player_actor if bp else None
        player_only_stage = bp.player_only_stage if bp else None

        try:
            resp = await fetch_stages_state(self._user_name, self._game_name)

            # 找到 player_actor 当前所在 stage
            current_stage: str | None = None
            if player_actor:
                for stage, actors in resp.mapping.items():
                    if player_actor in actors:
                        current_stage = stage
                        break

            # 排除当前场景和玩家专属场景
            candidates = [
                stage
                for stage in resp.mapping
                if stage != current_stage and stage != player_only_stage
            ]

            # 用 fetch_entities_details 筛选：仅保留拥有 HomeComponent 的场景
            available: list[str] = []
            if candidates:
                try:
                    details_resp = await fetch_entities_details(
                        self._user_name, self._game_name, candidates
                    )
                    home_stages = {
                        entity.name
                        for entity in details_resp.entities_serialization
                        if any(
                            comp.name == "HomeComponent" for comp in entity.components
                        )
                    }
                    available = [s for s in candidates if s in home_stages]
                except Exception as e:
                    logger.warning(
                        f"SwitchStageScreen._load_stages: 过滤 HomeComponent 失败，回退到全部候选 error={e}"
                    )
                    available = candidates

            self._stage_list = available

            if current_stage:
                log.write(
                    f"[bold yellow]当前场景：[bold cyan]{current_stage}[/][bold yellow][/]\n"
                )

            if not self._stage_list:
                log.write("[yellow]没有可切换的场景。[/]")
                return

            log.write("[bold yellow]可前往的场景：[/]")
            for i, stage in enumerate(self._stage_list, 1):
                actors = resp.mapping.get(stage, [])
                actors_str = "、".join(actors) if actors else "[dim]（空）[/]"
                log.write(f"  [bold green]{i}.[/] [cyan]{stage}[/]  → {actors_str}")
            log.write("")
            log.write("[dim]输入编号切换场景：[/]")
            logger.info(
                f"SwitchStageScreen._load_stages: 加载完成 stage_list={self._stage_list}"
            )
        except Exception as e:
            logger.error(f"SwitchStageScreen._load_stages: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载场景列表失败: {e}[/]")

    @work
    async def _do_switch_stage(self, target_stage: str) -> None:
        """发送场景切换动作，等待 pipeline 完成后返回 HomeScreen。"""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        log.write(f"[dim]▶ 正在切换到场景：{target_stage}...[/]")
        logger.info(f"SwitchStageScreen._do_switch_stage: target_stage={target_stage}")

        task_id: str = ""
        success = False
        try:
            resp = await server_home_player_action(
                self._user_name,
                self._game_name,
                HomePlayerActionType.SWITCH_STAGE,
                {"stage_name": target_stage},
            )
            task_id = resp.task_id
            log.write(f"[dim]任务已创建：{task_id}[/]")
            logger.info(
                f"SwitchStageScreen._do_switch_stage: 任务已创建 task_id={task_id}"
            )
        except Exception as e:
            logger.error(f"SwitchStageScreen._do_switch_stage: 发送失败 error={e}")
            log.write(f"[bold red]❌ 场景切换请求失败: {e}[/]")
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
                    log.write("[bold green]✅ 场景切换完成，正在返回主场景...[/]")
                    logger.info(
                        f"SwitchStageScreen._do_switch_stage: 任务完成 task_id={task_id}"
                    )
                    success = True
                    break
                elif task_record.status == TaskStatus.FAILED:
                    error_msg = task_record.error or "未知错误"
                    log.write(f"[bold red]❌ 场景切换失败: {error_msg}[/]")
                    logger.error(
                        f"SwitchStageScreen._do_switch_stage: 任务失败 task_id={task_id} error={error_msg}"
                    )
                    break
            except Exception as e:
                logger.warning(
                    f"SwitchStageScreen._do_switch_stage: 轮询失败 error={e}"
                )
        else:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(
                f"SwitchStageScreen._do_switch_stage: 轮询超时 task_id={task_id}"
            )

        if success:
            await asyncio.sleep(0.5)
            self.app.pop_screen()
        else:
            inp.disabled = False
            inp.focus()
