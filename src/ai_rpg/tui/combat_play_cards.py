"""战斗出牌 Screen（CombatPlayCardsScreen）"""

from typing import Optional, final

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from ..models import CombatRoom
from .base import BaseGameScreen
from .combat_common import find_stage_of_actor, render_stage_actors
from .combat_data_access import (
    get_dungeon_room,
    get_entities_details,
    get_stages_state,
    resolve_identity,
)
from .utils import display_name

BASE_INFO_HEADER = """\
[bold cyan]── 出牌 ──────────────────────────────────────[/]

[dim]核心出牌交互（选择卡牌 / 目标等）开发中；当前显示基础信息。[/]
"""

COMMANDS_MENU_TEMPLATE = """\
[bold yellow]── 可用操作 ─────────[/]
  [bold green]1[/]  {current_actor_label} 出牌
  [bold green]2[/]  清屏（刷新基础信息 + 清除历史信息）"""


@final
class CombatPlayCardsScreen(BaseGameScreen):
    """战斗 ONGOING 阶段、抽牌已完成后的出牌页面：展示当前 turn 角色 + 场景内角色
    有效属性，并提供出牌 / 清屏指令入口。"""

    CSS = """
    CombatPlayCardsScreen {
        align: center middle;
    }

    #combat-play-cards-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #combat-play-cards-input-row {
        height: 3;
        dock: bottom;
    }

    #combat-play-cards-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #combat-play-cards-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._current_actor: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield RichLog(
            id="combat-play-cards-log", highlight=True, markup=True, wrap=True
        )
        with Horizontal(id="combat-play-cards-input-row"):
            yield Static("> ", id="combat-play-cards-prompt")
            yield Input(placeholder="输入指令编号...", id="combat-play-cards-input")

    def on_mount(self) -> None:
        self._load_base_info()
        self.query_one(Input).focus()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    ########################################################################################################################
    @work
    async def _load_base_info(self) -> None:
        """加载并渲染当前 turn 角色 + 场景内角色有效属性。

        「清屏」指令会重新调用本方法：每次调用都会先清空 RichLog 再重新写入全部
        内容（重新 GET 最新数据 + 默认 2 个指令），既刷新了基础信息，也清除了此前
        的操作历史信息，避免内容不断追加、重复堆叠。
        """
        log = self.query_one(RichLog)
        log.clear()
        log.write(BASE_INFO_HEADER)
        logger.info("CombatPlayCardsScreen._load_base_info: 开始加载")

        try:
            _, _, actor_name = resolve_identity(self.game_client)

            room_resp = await get_dungeon_room(self.game_client)
            stages_resp = await get_stages_state(self.game_client)

            room = room_resp.room
            assert isinstance(
                room, CombatRoom
            ), f"当前房间不是战斗房间：type={room.type}"
            assert room.type == "combat"
            combat = room.combat

            stage_name = find_stage_of_actor(stages_resp.mapping, actor_name)
            assert (
                stage_name is not None
            ), f"未能在场景映射中找到玩家角色所在场景：actor={actor_name}"
            actor_names = stages_resp.mapping[stage_name]
            entity_names = [stage_name, *actor_names]

            entities_resp = await get_entities_details(self.game_client, entity_names)
        except Exception as e:
            logger.error(f"CombatPlayCardsScreen._load_base_info: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载出牌基础信息失败：{e}[/]")
            return

        latest_round = combat.latest_round
        self._current_actor = (
            latest_round.current_actor if latest_round is not None else None
        )

        log.write("[bold yellow]── 当前 turn ─────────────────────────────────[/]")
        log.write(
            f"  当前出牌角色： [bold yellow]"
            f"{display_name(self._current_actor) if self._current_actor else '（无）'}[/]"
        )
        log.write("")

        render_stage_actors(log, stage_name, entities_resp.entities_serialization)

        current_actor_label = (
            display_name(self._current_actor) if self._current_actor else "（无）"
        )
        log.write(
            COMMANDS_MENU_TEMPLATE.format(current_actor_label=current_actor_label)
        )

    ########################################################################################################################
    @on(Input.Submitted, "#combat-play-cards-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        if not raw:
            return
        self._dispatch_command(raw)

    ########################################################################################################################
    def _dispatch_command(self, raw: str) -> None:
        log = self.query_one(RichLog)

        if raw not in ("1", "2"):
            log.write("[red]无效指令，请输入 1-2[/]")
            return

        if raw == "1":
            # 出牌流程（选择手牌 / 目标、提交出牌请求、展示战斗日志与叙事反馈等）
            # 尚未实现；后续接入后，流程信息与反馈将以历史信息形式追加到本页
            # RichLog 中（而非清空后重写）。
            actor_label = (
                display_name(self._current_actor) if self._current_actor else "（无）"
            )
            log.write(f"[yellow]{actor_label} 出牌功能还没有实现。[/]")
        elif raw == "2":
            self._load_base_info()
