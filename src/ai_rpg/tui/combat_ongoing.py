"""战斗进行中 Screen（CombatOngoingScreen）"""

from typing import List, Tuple, final

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from ..models import CombatRoom, CombatState
from .base import BaseGameScreen
from .combat_common import (
    find_stage_of_actor,
    render_combat_summary,
    render_round_info,
    render_stage_actors,
)
from .combat_data_access import (
    get_dungeon_room,
    get_entities_details,
    get_stages_state,
    is_mock_mode,
    resolve_identity,
)
from .combat_deck_view import CombatDeckViewScreen
from .combat_entity_inspect import CombatEntityInspectScreen
from .combat_hand_status_view import CombatHandStatusViewScreen
from .combat_inventory_view import CombatInventoryViewScreen
from .combat_post_combat import CombatPostCombatScreen
from .combat_round_history import CombatRoundHistoryScreen
from .home import HomeScreen
from .server_client import (
    TaskFailedError,
    dungeon_combat_retreat,
    watch_task_until_done,
)

BASE_INFO_HEADER = """\
[bold cyan]── 战斗进行中（ONGOING） ──────────────────────────────────────[/]

[dim]核心战斗交互（出牌 / 抽牌 / 使用道具与装备等）开发中；当前显示基础信息。[/]
"""

ONGOING_COMMANDS_MENU = """\
[bold yellow]── 可用操作 ─────────[/]
  [bold green]1[/]  查阅牌组（双方）
  [bold green]2[/]  查阅我方背包
  [bold green]3[/]  查阅指定实体信息（场景 / 角色）
  [bold green]4[/]  查阅历史回合详情"""

RETREAT_COMMAND_LINE = "\n  [bold green]5[/]  战斗中撤退"
POST_COMBAT_COMMAND_LINE = "\n  [bold green]5[/]  结束战斗"
HAND_STATUS_COMMAND_LINE = "\n  [bold green]6[/]  查看手牌 + 状态效果"


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
        render_round_info(log, combat)
        render_stage_actors(log, stage_name, entities_resp.entities_serialization)

        # 1-4 为查阅型（GET）指令，从不改变任何状态，无论战斗处于哪个阶段都可用；
        # 指令 5 依 combat.state 而变：ONGOING 阶段为「战斗中撤退」，
        # COMPLETE / POST_COMBAT 阶段为「结束战斗」，其余阶段不显示。
        menu = ONGOING_COMMANDS_MENU
        if combat.state == CombatState.ONGOING:
            menu += RETREAT_COMMAND_LINE
        elif combat.state in (CombatState.COMPLETE, CombatState.POST_COMBAT):
            menu += POST_COMBAT_COMMAND_LINE
        else:
            logger.info(
                "CombatOngoingScreen._load_base_info: 战斗处于其它阶段，隐藏指令 5"
            )

        menu += HAND_STATUS_COMMAND_LINE

        log.write(menu)

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
        错误判断或跳转。
        """
        log = self.query_one(RichLog)

        if raw not in ("1", "2", "3", "4", "5", "6"):
            log.write("[red]无效指令，请输入 1-6[/]")
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

        if raw == "5":
            if combat.state == CombatState.ONGOING:
                self._do_retreat()
            elif combat.state in (CombatState.COMPLETE, CombatState.POST_COMBAT):
                self.app.push_screen(CombatPostCombatScreen())
            else:
                log.write(f"[yellow]还没有实现。[/]")
            return

        if raw == "4":
            self.app.push_screen(CombatRoundHistoryScreen(combat.rounds))
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
        elif raw == "6":
            self.app.push_screen(CombatHandStatusViewScreen(participant_names))

    ########################################################################################################################
    @work
    async def _do_retreat(self) -> None:
        """战斗中撤退（仅 CombatState.ONGOING 阶段可用）：调用"""
        log = self.query_one(RichLog)

        if is_mock_mode(self.game_client):
            logger.info("CombatOngoingScreen._do_retreat: mock 模式，直接退出应用")
            log.write("[dim]mock 模式：无真实会话可撤退，直接退出应用[/]")
            self.app.exit()
            return

        inp = self.query_one(Input)
        inp.disabled = True
        log.write("[dim]▶ 正在撤退...[/]")

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)
            resp = await dungeon_combat_retreat(user_name, game_name)
            log.write(f"[dim]任务已提交：{resp.task_id}，等待完成...[/]")
            await watch_task_until_done(resp.task_id)
        except TaskFailedError as e:
            logger.error(f"CombatOngoingScreen._do_retreat: 撤退任务失败 error={e}")
            log.write(f"[bold red]❌ 撤退失败：{e}[/]")
            inp.disabled = False
            inp.focus()
            return
        except Exception as e:
            logger.error(f"CombatOngoingScreen._do_retreat: 撤退请求失败 error={e}")
            log.write(f"[bold red]❌ 撤退请求失败：{e}[/]")
            inp.disabled = False
            inp.focus()
            return

        log.write("[bold green]✅ 撤退成功[/]")
        logger.info("CombatOngoingScreen._do_retreat: 撤退成功，返回家园")

        self.app.switch_screen(HomeScreen())
