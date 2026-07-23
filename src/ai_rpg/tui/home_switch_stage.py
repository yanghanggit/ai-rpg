"""场景切换动作 Screen（SWITCH_STAGE 玩家动作）"""

import asyncio
from typing import Dict, List, Optional, Tuple

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from .base import BaseGameScreen

from ..models import AppearanceComponent, HomeComponent, StageDescriptionComponent
from .server_client import (
    fetch_entities_details,
    fetch_stages_state,
    watch_task_until_done,
    TaskFailedError,
    home_player_action as server_home_player_action,
)
from .utils import display_name
from ..models.api import HomePlayerActionType

SWITCH_STAGE_HEADER = """\
[bold cyan]── 场景切换 ──────────────────────────────────────[/]

输入编号切换到目标场景，[bold]0[/] 清屏，[bold]Escape[/] 取消返回。
"""


class HomeSwitchStageScreen(BaseGameScreen):
    """场景切换 Screen：列出可前往的场景，输入编号后直接发送切换动作。"""

    CSS = """
    HomeSwitchStageScreen {
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

    def compose(self) -> ComposeResult:
        yield RichLog(id="switch-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="switch-input-row"):
            yield Static("> ", id="switch-prompt")
            yield Input(placeholder="输入编号切换场景...", id="switch-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(SWITCH_STAGE_HEADER)
        self._show_stage_menu()
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

        if raw == "0":
            log.clear()
            log.write(SWITCH_STAGE_HEADER)
            self._show_stage_menu()
            return

        if not raw.isdigit():
            log.write("[red]请输入有效的编号。[/]")
            return

        self._switch_stage_by_index(raw)

    ########################################################################################################################
    async def _fetch_switch_stage_data(self, log: RichLog) -> Optional[
        Tuple[
            Optional[str],
            Optional[str],
            Dict[str, Optional[str]],
            List[str],
            Dict[str, List[str]],
        ]
    ]:
        """一次性拉取当前场景（名字 + StageDescriptionComponent.narrative +
        场景内各 actor 的 AppearanceComponent.appearance）与可前往场景列表
        （仅场景名 + 其内部 actor 名，宏观信息）。不做任何缓存，每次调用都重新
        从服务端获取。失败时返回 None（错误信息已写入 log）。

        Returns:
            (current_stage, narrative, appearance_by_actor,
             available_stages, actors_by_stage)
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
                f"HomeSwitchStageScreen._fetch_switch_stage_data: 获取场景列表失败 error={e}"
            )
            log.write(f"[bold red]❌ 获取场景列表失败: {e}[/]")
            return None

        current_stage: Optional[str] = None
        for stage, actors in stages_resp.mapping.items():
            if player_actor in actors:
                current_stage = stage
                break

        all_stages = list(stages_resp.mapping.keys())
        current_stage_actors = (
            stages_resp.mapping.get(current_stage, []) if current_stage else []
        )

        entity_names = list(all_stages)
        for actor in current_stage_actors:
            if actor not in entity_names:
                entity_names.append(actor)

        try:
            details_resp = await fetch_entities_details(
                user_name, game_name, entity_names
            )
        except Exception as e:
            logger.error(
                f"HomeSwitchStageScreen._fetch_switch_stage_data: 获取实体详情失败 error={e}"
            )
            log.write(f"[bold red]❌ 获取实体详情失败: {e}[/]")
            return None

        components_by_entity = {
            entity.name: entity.components
            for entity in details_resp.entities_serialization
        }

        narrative: Optional[str] = None
        if current_stage is not None:
            for comp in components_by_entity.get(current_stage, []):
                if comp.name == StageDescriptionComponent.__name__:
                    narrative = StageDescriptionComponent(**comp.data).narrative
                    break

        appearance_by_actor: Dict[str, Optional[str]] = {}
        for actor in current_stage_actors:
            appearance: Optional[str] = None
            for comp in components_by_entity.get(actor, []):
                if comp.name == AppearanceComponent.__name__:
                    appearance = AppearanceComponent(**comp.data).appearance
                    break
            appearance_by_actor[actor] = appearance

        home_stages = {
            entity.name
            for entity in details_resp.entities_serialization
            if any(comp.name == HomeComponent.__name__ for comp in entity.components)
        }

        available_stages = [
            stage
            for stage in all_stages
            if stage in home_stages and stage != current_stage
        ]
        actors_by_stage = {
            stage: stages_resp.mapping.get(stage, []) for stage in available_stages
        }

        return (
            current_stage,
            narrative,
            appearance_by_actor,
            available_stages,
            actors_by_stage,
        )

    ########################################################################################################################
    @work
    async def _show_stage_menu(self) -> None:
        """拉取并渲染当前场景（详细：narrative + 场景内 actor 的 appearance）
        与可前往场景列表（宏观：仅场景名 + actor 名），编号供选择使用。"""
        log = self.query_one(RichLog)
        log.write("[dim]正在加载场景列表...[/]")
        logger.info("HomeSwitchStageScreen._show_stage_menu")

        result = await self._fetch_switch_stage_data(log)
        if result is None:
            return
        (
            current_stage,
            narrative,
            appearance_by_actor,
            available_stages,
            actors_by_stage,
        ) = result

        if current_stage is not None:
            log.write(
                f"[bold yellow]── 当前场景：[bold cyan]{display_name(current_stage)}[/][bold yellow] ──[/]"
            )
            log.write(f"  {narrative}" if narrative else "  [dim]（该场景暂无描述）[/]")
            if appearance_by_actor:
                log.write("[bold yellow]场景内角色：[/]")
                for actor, appearance in appearance_by_actor.items():
                    log.write(f"  [cyan]{display_name(actor)}[/]")
                    log.write(
                        f"    {appearance}"
                        if appearance
                        else "    [dim]（未持有 AppearanceComponent）[/]"
                    )
            log.write("")

        if not available_stages:
            log.write("[yellow]没有可切换的场景。[/]")
            return

        log.write("[bold yellow]可前往的场景：[/]")
        for i, stage in enumerate(available_stages, 1):
            actors = actors_by_stage.get(stage, [])
            actors_str = (
                "、".join(display_name(a) for a in actors)
                if actors
                else "[dim]（空）[/]"
            )
            log.write(
                f"  [bold green]{i}.[/] [cyan]{display_name(stage)}[/]  → {actors_str}"
            )
        log.write("")
        log.write("[dim]输入编号切换场景（0 清屏）：[/]")
        logger.info(
            f"SwitchStageScreen._show_stage_menu: 加载完成 available_stages={available_stages}"
        )

    ########################################################################################################################
    @work
    async def _switch_stage_by_index(self, raw: str) -> None:
        """指令：将编号解析为目标场景。重新拉取一次可前往场景列表，
        确保选取时对照的是最新状态（不复用任何缓存）。"""
        log = self.query_one(RichLog)

        result = await self._fetch_switch_stage_data(log)
        if result is None:
            return
        _, _, _, available_stages, _ = result

        if not available_stages:
            log.write("[yellow]没有可切换的场景。[/]")
            return

        idx = int(raw) - 1
        if idx < 0 or idx >= len(available_stages):
            log.write(f"[red]编号超出范围，请输入 1 ~ {len(available_stages)}。[/]")
            return

        target_stage = available_stages[idx]
        self._do_switch_stage(target_stage)

    @work
    async def _do_switch_stage(self, target_stage: str) -> None:
        """发送场景切换动作，等待 pipeline 完成后返回 HomeScreen。"""
        log = self.query_one(RichLog)
        inp = self.query_one(Input)
        inp.disabled = True

        log.write(f"[dim]▶ 正在切换到场景：{display_name(target_stage)}...[/]")
        logger.info(f"SwitchStageScreen._do_switch_stage: target_stage={target_stage}")

        app = self.game_client
        if app.session is None:
            inp.disabled = False
            inp.focus()
            return
        user_name = app.session.user_name
        game_name = app.session.game_name

        task_id: str = ""
        success = False
        try:
            resp = await server_home_player_action(
                user_name,
                game_name,
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

        try:
            await watch_task_until_done(task_id)
            log.write("[bold green]✅ 场景切换完成，正在返回主场景...[/]")
            logger.info(
                f"SwitchStageScreen._do_switch_stage: 任务完成 task_id={task_id}"
            )
            success = True
        except TaskFailedError as e:
            log.write(f"[bold red]❌ 场景切换失败: {e}[/]")
            logger.error(
                f"SwitchStageScreen._do_switch_stage: 任务失败 task_id={task_id} error={e}"
            )
        except TimeoutError:
            log.write("[bold yellow]⚠️ 等待超时，请检查服务器状态[/]")
            logger.warning(
                f"SwitchStageScreen._do_switch_stage: 轮询超时 task_id={task_id}"
            )
        except Exception as e:
            logger.warning(
                f"SwitchStageScreen._do_switch_stage: 等待任务失败 error={e}"
            )

        if success:
            await asyncio.sleep(0.5)
            self.app.pop_screen()
        else:
            inp.disabled = False
            inp.focus()
