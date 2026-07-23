"""对话动作 Screen（SPEAK 玩家动作）"""

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from .base import BaseGameScreen

from .server_client import (
    fetch_stages_state,
    fetch_entities_details,
    watch_task_until_done,
    TaskFailedError,
    home_player_action as server_home_player_action,
)
from .utils import display_name
from ..models import AppearanceComponent, StageDescriptionComponent
from ..models.api import HomePlayerActionType

SPEAK_HEADER = """\
[bold cyan]── 对话 ──────────────────────────────────────[/]

输入编号选择对话目标，[bold]0[/] 返回上一级（根部即清屏重载），[bold]Escape[/] 取消返回。
"""


###################################################################################################################################################################
@dataclass
class _SpeakFlowState:
    """对话流程状态：`selected_target` 为 None 表示处于「选择目标」步骤，
    非 None 表示已选定目标、处于「输入对话内容」步骤。"""

    selected_target: Optional[str] = None


class HomeSpeakScreen(BaseGameScreen):
    """对话 Screen：列出当前场景可交谈的 NPC，选目标后输入说话内容发送。"""

    CSS = """
    HomeSpeakScreen {
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
        ("escape", "go_back", "Cancel"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._flow = _SpeakFlowState()

    def compose(self) -> ComposeResult:
        yield RichLog(id="speak-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="speak-input-row"):
            yield Static("> ", id="speak-prompt")
            yield Input(placeholder="输入编号选择对话目标...", id="speak-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(SPEAK_HEADER)
        self._show_select_menu()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @on(Input.Submitted, "#speak-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()

        if not raw:
            return

        if self._flow.selected_target is None:
            self._handle_select_command(raw)
            return

        # 已选定目标，处于「输入对话内容」步骤
        if raw == "0":
            self._flow.selected_target = None
            inp = self.query_one(Input)
            inp.placeholder = "输入编号选择对话目标..."
            self._show_select_menu()
            return

        self._do_speak(raw)

    ########################################################################################################################
    def _handle_select_command(self, raw: str) -> None:
        log = self.query_one(RichLog)

        if raw == "0":
            log.clear()
            log.write(SPEAK_HEADER)
            self._flow = _SpeakFlowState()
            self._show_select_menu()
            return

        if not raw.isdigit():
            log.write("[red]请输入有效的编号。[/]")
            return

        self._select_target_by_index(raw)

    ########################################################################################################################
    async def _fetch_current_scene(
        self, log: RichLog
    ) -> Optional[Tuple[str, Optional[str], List[str], Dict[str, Optional[str]]]]:
        """一次性临时 GET：拉取玩家 `actor_name` 当前所在场景的描述
        （StageDescriptionComponent.narrative）与场景内可交谈 NPC 列表（过滤玩家自身，
        附带各自 AppearanceComponent.appearance）。不做任何缓存，每次调用都重新从
        服务端获取。失败或无法确定场景时返回 None（错误信息已写入 log）。

        Returns:
            (stage_name, narrative, actor_names, appearance_by_actor)
        """
        app = self.game_client
        if app.session is None:
            return None
        user_name = app.session.user_name
        game_name = app.session.game_name
        player_actor = app.session.actor_name

        try:
            stages_resp = await fetch_stages_state(user_name, game_name)
        except Exception as e:
            logger.error(
                f"HomeSpeakScreen._fetch_current_scene: 获取场景列表失败 error={e}"
            )
            log.write(f"[bold red]❌ 获取场景列表失败: {e}[/]")
            return None

        current_stage: Optional[str] = None
        for stage, actors in stages_resp.mapping.items():
            if player_actor in actors:
                current_stage = stage
                break

        if current_stage is None:
            log.write("[yellow]无法确定玩家当前所在场景。[/]")
            return None

        stage_actors = stages_resp.mapping.get(current_stage, [])
        actor_names = [a for a in stage_actors if a != player_actor]

        try:
            details_resp = await fetch_entities_details(
                user_name, game_name, [current_stage] + actor_names
            )
        except Exception as e:
            logger.error(
                f"SpeakScreen._fetch_current_scene: 获取实体详情失败 error={e}"
            )
            log.write(f"[bold red]❌ 获取实体详情失败: {e}[/]")
            return None

        components_by_entity = {
            entity.name: entity.components
            for entity in details_resp.entities_serialization
        }

        narrative: Optional[str] = None
        for comp in components_by_entity.get(current_stage, []):
            if comp.name == StageDescriptionComponent.__name__:
                narrative = StageDescriptionComponent(**comp.data).narrative
                break

        appearance_by_actor: Dict[str, Optional[str]] = {}
        for actor in actor_names:
            appearance: Optional[str] = None
            for comp in components_by_entity.get(actor, []):
                if comp.name == AppearanceComponent.__name__:
                    appearance = AppearanceComponent(**comp.data).appearance
                    break
            appearance_by_actor[actor] = appearance

        return current_stage, narrative, actor_names, appearance_by_actor

    ########################################################################################################################
    @work
    async def _show_select_menu(self) -> None:
        """拉取并渲染当前场景描述与可对话 NPC 列表（含各自 appearance），编号供选择使用。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在加载当前场景...[/]")
        logger.info("SpeakScreen._show_select_menu")

        result = await self._fetch_current_scene(log)
        if result is None:
            return
        stage_name, narrative, actor_names, appearance_by_actor = result

        log.write(
            f"[bold yellow]── 当前场景：[bold cyan]{display_name(stage_name)}[/][bold yellow] ──[/]"
        )
        log.write(f"  {narrative}" if narrative else "  [dim]（该场景暂无描述）[/]")

        if not actor_names:
            log.write("[yellow]当前场景没有可交谈的 NPC。[/]")
            return

        log.write("[bold yellow]可对话的 NPC：[/]")
        for i, actor in enumerate(actor_names, 1):
            appearance = appearance_by_actor.get(actor)
            log.write(f"  [bold green]{i}.[/] {display_name(actor)}")
            log.write(
                f"    {appearance}"
                if appearance
                else "    [dim]（未持有 AppearanceComponent）[/]"
            )
        log.write("")
        log.write("[dim]输入编号选择对话目标（0 返回上一级）：[/]")
        logger.info(
            f"SpeakScreen._show_select_menu: 加载完成 actor_names={actor_names}"
        )

    ########################################################################################################################
    @work
    async def _select_target_by_index(self, raw: str) -> None:
        """指令：将编号解析为对话目标。重新拉取一次当前场景 NPC 列表，
        确保选取时对照的是最新状态（不复用任何缓存）。"""
        log = self.query_one(RichLog)

        result = await self._fetch_current_scene(log)
        if result is None:
            return
        _, _, actor_names, _ = result

        if not actor_names:
            log.write("[yellow]当前场景没有可交谈的 NPC。[/]")
            return

        idx = int(raw) - 1
        if idx < 0 or idx >= len(actor_names):
            log.write(f"[red]编号超出范围，请输入 1 ~ {len(actor_names)}。[/]")
            return

        target = actor_names[idx]
        self._flow.selected_target = target
        log.write(
            f"[bold green]已选目标：[bold cyan]{display_name(target)}[/][bold green]"
            f"[/]\n[dim]请输入说话内容，按 Enter 发送（输入 0 返回上一级）：[/]"
        )
        inp = self.query_one(Input)
        inp.placeholder = "输入说话内容..."

    ########################################################################################################################
    @work
    async def _do_speak(self, content: str) -> None:
        """发送对话动作，等待 pipeline 完成后返回 HomeScreen。"""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        target = self._flow.selected_target
        assert target is not None

        log.write(f"[dim]▶ 发送对话：{display_name(target)} ← 「{content}」...[/]")
        logger.info(f"SpeakScreen._do_speak: target={target} content={content}")

        task_id: str = ""
        success = False
        try:
            app = self.game_client
            if app.session is None:
                inp.disabled = False
                inp.focus()
                return
            resp = await server_home_player_action(
                app.session.user_name,
                app.session.game_name,
                HomePlayerActionType.SPEAK,
                {"target": target, "content": content},
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

        try:
            await watch_task_until_done(task_id)
            log.write("[bold green]✅ 对话完成，正在返回主场景...[/]")
            logger.info(f"SpeakScreen._do_speak: 任务完成 task_id={task_id}")
            success = True
        except TaskFailedError as e:
            log.write(f"[bold red]❌ 对话失败: {e}[/]")
            logger.error(f"SpeakScreen._do_speak: 任务失败 task_id={task_id} error={e}")
        except TimeoutError:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(f"SpeakScreen._do_speak: 轮询超时 task_id={task_id}")
        except Exception as e:
            logger.warning(f"SpeakScreen._do_speak: 等待任务失败 error={e}")

        if success:
            await asyncio.sleep(0.5)
            self.app.pop_screen()
        else:
            inp.disabled = False
            inp.focus()
