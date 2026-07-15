"""战斗进行中 Screen（CombatOngoingScreen）

CombatState.ONGOING 阶段的专属页面。战斗核心交互（出牌/抽牌/使用道具/装备等）
后续逐步补充；当前先提供与 CombatRoomScreen 类似的基础信息展示：
    1) 战斗宏观状态：name / state / result / retreated
    2) 场景名字 + 场景内所有 actor 的有效属性（含手牌数量 / 状态效果数量）
    3) 当前回合信息：局数 + 最新一局的 completed_actors / action_order /
       current_actor / is_completed / draw_completed / consumable_use_count /
       gear_use_count
    4) 查阅型（GET）命令：查阅牌组（双方）/ 查阅我方背包 / 查阅指定实体信息

由 CombatRoomScreen 在战斗初始化成功后 switch_screen 至此。
"""

from typing import List, Tuple, final

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from ..models import Combat, CombatRoom, CombatState
from .base import BaseGameScreen
from .combat_common import (
    find_stage_of_actor,
    render_combat_summary,
    render_stage_actors,
)
from .combat_data_access import (
    get_dungeon_room,
    get_entities_details,
    get_stages_state,
    resolve_identity,
)
from .combat_deck_view import CombatDeckViewScreen
from .combat_entity_inspect import CombatEntityInspectScreen
from .combat_inventory_view import CombatInventoryViewScreen

BASE_INFO_HEADER = """\
[bold cyan]── 战斗进行中（ONGOING） ──────────────────────────────────────[/]

[dim]核心战斗交互（出牌 / 抽牌 / 使用道具与装备等）开发中；当前显示基础信息。[/]
"""

ONGOING_COMMANDS_MENU = """\
[bold yellow]── 可用操作（ONGOING 阶段） ─────────────[/]
  [bold green]1[/]  查阅牌组（双方）
  [bold green]2[/]  查阅我方背包
  [bold green]3[/]  查阅指定实体信息（场景 / 角色）
"""


def _render_round_info(log: RichLog, combat: Combat) -> None:
    """渲染当前局数 + 最新一局的基本信息。"""
    round_count = len(combat.rounds)
    log.write("[bold yellow]── 回合信息 ─────────────────────────────────────[/]")
    log.write(f"  当前局数：   [bold]{round_count}[/]")

    latest = combat.latest_round
    if latest is None:
        log.write("  [dim]（尚无回合数据）[/]")
        log.write("")
        return

    completed_str = (
        "、".join(latest.completed_actors)
        if latest.completed_actors
        else "[dim]（无）[/]"
    )
    order_str = (
        "  →  ".join(latest.action_order) if latest.action_order else "[dim]（无）[/]"
    )
    current_actor_str = latest.current_actor or "[dim]（无）[/]"

    log.write(f"  已出手角色： {completed_str}")
    log.write(f"  行动顺序：   {order_str}")
    log.write(f"  当前 turn：  [bold yellow]{current_actor_str}[/]")
    log.write(
        f"  回合已结束： {'[green]是[/]' if latest.is_completed else '[yellow]否[/]'}"
    )
    log.write(
        f"  抽牌已完成： {'[green]是[/]' if latest.draw_completed else '[yellow]否[/]'}"
    )
    log.write(f"  消耗品使用次数： [bold]{latest.consumable_use_count}[/]")
    log.write(f"  装备使用次数：   [bold]{latest.gear_use_count}[/]")
    log.write("")


@final
class CombatOngoingScreen(BaseGameScreen):
    """战斗 ONGOING 阶段页面：展示基础信息，并提供查阅型（GET）指令入口。"""

    CSS = """
    CombatOngoingScreen {
        align: center middle;
    }

    #combat-ongoing-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #combat-ongoing-input-row {
        height: 3;
        dock: bottom;
    }

    #combat-ongoing-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #combat-ongoing-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "app.quit", "退出"),
    ]

    def compose(self) -> ComposeResult:
        yield RichLog(id="combat-ongoing-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="combat-ongoing-input-row"):
            yield Static("> ", id="combat-ongoing-prompt")
            yield Input(placeholder="输入指令编号...", id="combat-ongoing-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(BASE_INFO_HEADER)
        self._load_base_info()
        self.query_one(Input).focus()

    ########################################################################################################################
    @work
    async def _load_base_info(self) -> None:
        """加载并渲染战斗宏观状态 + 回合信息 + 场景内角色有效属性（含手牌/状态效果数量）。"""
        log = self.query_one(RichLog)
        logger.info("CombatOngoingScreen._load_base_info: 开始加载")

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
            logger.error(f"CombatOngoingScreen._load_base_info: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载战斗基础信息失败：{e}[/]")
            return

        render_combat_summary(
            log, combat.name, combat.state.name, combat.result.name, combat.retreated
        )
        _render_round_info(log, combat)
        render_stage_actors(log, stage_name, entities_resp.entities_serialization)

        if combat.state == CombatState.ONGOING:
            log.write(ONGOING_COMMANDS_MENU)
        else:
            log.write(
                f"[dim]当前战斗状态为 {combat.state.name}，本页仅处理 "
                "ONGOING 阶段的操作。[/]"
            )

    ########################################################################################################################
    @on(Input.Submitted, "#combat-ongoing-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        if not raw:
            return
        self._dispatch_command(raw)

    ########################################################################################################################
    @work
    async def _dispatch_command(self, raw: str) -> None:
        """指令分发：每次都重新 GET 校验战斗状态与场景花名册，避免使用过期数据做出
        错误判断或跳转。"""
        log = self.query_one(RichLog)

        if raw not in ("1", "2", "3"):
            log.write("[red]无效指令，请输入 1-3[/]")
            return

        try:
            _, _, actor_name = resolve_identity(self.game_client)
            room_resp = await get_dungeon_room(self.game_client)
            room = room_resp.room
            assert isinstance(
                room, CombatRoom
            ), f"当前房间不是战斗房间：type={room.type}"
            assert room.type == "combat"
            combat = room.combat
        except Exception as e:
            logger.error(
                f"CombatOngoingScreen._dispatch_command: 校验战斗状态失败 error={e}"
            )
            log.write(f"[bold red]❌ 校验战斗状态失败：{e}[/]")
            return

        if combat.state != CombatState.ONGOING:
            log.write(
                f"[yellow]当前战斗状态为 {combat.state.name}，暂不支持这些指令。[/]"
            )
            return

        try:
            stages_resp = await get_stages_state(self.game_client)
            stage_name = find_stage_of_actor(stages_resp.mapping, actor_name)
            assert (
                stage_name is not None
            ), f"未能在场景映射中找到玩家角色所在场景：actor={actor_name}"
            participant_names = list(stages_resp.mapping[stage_name])
        except Exception as e:
            logger.error(
                f"CombatOngoingScreen._dispatch_command: 获取场景花名册失败 error={e}"
            )
            log.write(f"[bold red]❌ 获取场景花名册失败：{e}[/]")
            return

        if raw == "1":
            self.app.push_screen(CombatDeckViewScreen(participant_names))
        elif raw == "2":
            self.app.push_screen(CombatInventoryViewScreen())
        elif raw == "3":
            candidates: List[Tuple[str, str]] = [(stage_name, "场景")]
            candidates.extend((name, "角色") for name in participant_names)
            self.app.push_screen(CombatEntityInspectScreen(candidates))
