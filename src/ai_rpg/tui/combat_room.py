"""战斗房间 Screen（CombatRoomScreen）

页面进入即自动加载并显示战斗宏观信息（不含 rounds 细节）：
    1) 战斗宏观状态：name / state / result / retreated（来自 fetch_dungeon_room）
    2) 场景名字 + 场景内所有 actor 的有效属性（compute_effective_stats），
       通过 fetch_stages_state + fetch_entities_details 联动获取。

本 Screen 仅作为战斗房间的入口，且仅处理 CombatState.INITIALIZATION 阶段的操作
（开始战斗 / 查阅牌组 / 查阅背包 / 查阅实体）。INITIALIZATION 之后的 ONGOING 是
战斗核心状态，逻辑复杂，交由专属 Screen 处理（后续开发）。

服务器未启动时（`--dev-screen combat-room` 跳过登录，`session is None`），
改用 mock_data 模块构造的固定数据，数据形状与真实响应完全一致，
故渲染逻辑对两条路径完全复用，无需分支。
"""

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
from .combat_inventory_view import CombatInventoryViewScreen
from .combat_ongoing import CombatOngoingScreen
from .mock_data import set_mock_combat_state
from .server_client import TaskFailedError, dungeon_combat_init, watch_task_until_done

BASE_INFO_HEADER = """\
[bold cyan]── 战斗房间 ──────────────────────────────────────[/]

[dim]页面重构中；当前仅显示基础信息（回合详情另行提供）。[/]
"""

INIT_COMMANDS_MENU = """\
[bold yellow]── 可用操作（INITIALIZATION 阶段） ─────────────[/]
  [bold green]1[/]  开始战斗
  [bold green]2[/]  查阅牌组（双方）
  [bold green]3[/]  查阅我方背包
  [bold green]4[/]  查阅指定实体信息（场景 / 角色）
"""


@final
class CombatRoomScreen(BaseGameScreen):
    """战斗房间 Screen：进入即自动加载并显示战斗宏观信息与场景内角色有效属性；
    仅处理 CombatState.INITIALIZATION 阶段的操作命令。"""

    CSS = """
    CombatRoomScreen {
        align: center middle;
    }

    #combat-room-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }

    #combat-room-input-row {
        height: 3;
        dock: bottom;
    }

    #combat-room-prompt {
        width: 6;
        height: 3;
        content-align: left middle;
        color: $success;
    }

    #combat-room-input {
        width: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "app.quit", "退出"),
    ]

    def compose(self) -> ComposeResult:
        yield RichLog(id="combat-room-log", highlight=True, markup=True, wrap=True)
        with Horizontal(id="combat-room-input-row"):
            yield Static("> ", id="combat-room-prompt")
            yield Input(placeholder="输入指令编号...", id="combat-room-input")

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(BASE_INFO_HEADER)
        self._load_base_info()
        self.query_one(Input).focus()

    ########################################################################################################################
    @work
    async def _load_base_info(self) -> None:
        """加载并渲染战斗宏观状态 + 场景内角色有效属性（不含 rounds 细节）。"""
        log = self.query_one(RichLog)
        logger.info("CombatRoomScreen._load_base_info: 开始加载")

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
            logger.error(f"CombatRoomScreen._load_base_info: 加载失败 error={e}")
            log.write(f"[bold red]❌ 加载战斗基础信息失败：{e}[/]")
            return

        # 注意：此处不缓存 combat.state / stage_name / actor_names 供后续指令使用。
        # 这些数据来自 GET 快照，仅用于当次页面渲染；指令实际派发时（handle_input /
        # _dispatch_command）会重新 GET 校验，避免使用过期状态做出错误判断。
        render_combat_summary(
            log, combat.name, combat.state.name, combat.result.name, combat.retreated
        )
        render_stage_actors(log, stage_name, entities_resp.entities_serialization)

        if combat.state == CombatState.INITIALIZATION:
            log.write(INIT_COMMANDS_MENU)
        else:
            log.write(
                f"[dim]当前战斗状态为 {combat.state.name}，本页仅处理 "
                "INITIALIZATION 阶段的操作；ONGOING 等状态将在专属页面处理（开发中）。[/]"
            )

    ########################################################################################################################
    @on(Input.Submitted, "#combat-room-input")
    def handle_input(self, event: Input.Submitted) -> None:
        raw = event.value.strip()
        event.input.clear()
        if not raw:
            return
        self._dispatch_command(raw)

    ########################################################################################################################
    @work
    async def _dispatch_command(self, raw: str) -> None:
        """指令分发：每次都重新 GET 校验战斗状态与场景花名册，不复用 _load_base_info
        加载时的快照，避免因状态在此期间发生变化（如已推进到 ONGOING、队伍成员变动）
        而依据过期数据做出错误判断或跳转。"""
        log = self.query_one(RichLog)

        if raw not in ("1", "2", "3", "4"):
            log.write("[red]无效指令，请输入 1-4[/]")
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
                f"CombatRoomScreen._dispatch_command: 校验战斗状态失败 error={e}"
            )
            log.write(f"[bold red]❌ 校验战斗状态失败：{e}[/]")
            return

        if combat.state != CombatState.INITIALIZATION:
            log.write(
                f"[yellow]当前战斗状态为 {combat.state.name}，暂不支持这些指令（专属页面开发中）。[/]"
            )
            return

        if raw == "1":
            self._start_combat()
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
                f"CombatRoomScreen._dispatch_command: 获取场景花名册失败 error={e}"
            )
            log.write(f"[bold red]❌ 获取场景花名册失败：{e}[/]")
            return

        if raw == "2":
            self.app.push_screen(CombatDeckViewScreen(participant_names))
        elif raw == "3":
            self.app.push_screen(CombatInventoryViewScreen())
        elif raw == "4":
            candidates: List[Tuple[str, str]] = [(stage_name, "场景")]
            candidates.extend((name, "角色") for name in participant_names)
            self.app.push_screen(CombatEntityInspectScreen(candidates))

    ########################################################################################################################
    @work
    async def _start_combat(self) -> None:
        """直接触发战斗初始化并等待完成，期间在日志中显示等待文字，成功后跳转至
        代表 CombatState.ONGOING 的专属页面。"""
        log = self.query_one(RichLog)
        logger.info("CombatRoomScreen._start_combat: 触发战斗初始化")
        log.write("[dim]正在触发战斗初始化，请稍候...[/]")

        if is_mock_mode(self.game_client):
            log.write(
                "[bold yellow]\\[mock][/] 已模拟触发战斗初始化（未调用真实接口）。"
            )
            set_mock_combat_state(CombatState.ONGOING)
            log.write("[dim]正在进入战斗（ONGOING）...[/]")
            self.app.switch_screen(CombatOngoingScreen())
            return

        try:
            user_name, game_name, _ = resolve_identity(self.game_client)
            resp = await dungeon_combat_init(user_name, game_name)
            log.write(f"[dim]任务已提交：{resp.task_id}，等待完成...[/]")
            record = await watch_task_until_done(resp.task_id)
            log.write(f"[bold green]✅ 战斗初始化完成：{record.status}[/]")
            self.app.switch_screen(CombatOngoingScreen())
        except TaskFailedError as e:
            logger.error(f"CombatRoomScreen._start_combat: 任务失败 error={e}")
            log.write(f"[bold red]❌ 战斗初始化失败：{e}[/]")
        except Exception as e:
            logger.error(f"CombatRoomScreen._start_combat: 请求失败 error={e}")
            log.write(f"[bold red]❌ 请求失败：{e}[/]")
