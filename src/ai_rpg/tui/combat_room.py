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

from typing import Any, Dict, List, Optional, Tuple, final

from loguru import logger
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, RichLog, Static

from ..models import (
    CharacterStatsComponent,
    CombatRoom,
    CombatState,
    EntitySerialization,
    EquippedGearComponent,
    MonsterComponent,
    NPCComponent,
    PlayerComponent,
    StatusEffectsComponent,
    compute_effective_stats,
)
from .base import BaseGameScreen
from .combat_data_access import (
    get_dungeon_room,
    get_entities_details,
    get_stages_state,
    resolve_identity,
)
from .combat_deck_view import CombatDeckViewScreen
from .combat_entity_inspect import CombatEntityInspectScreen
from .combat_inventory_view import CombatInventoryViewScreen
from .combat_start_action import CombatStartActionScreen
from .utils import display_name

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

            stage_name = self._find_stage_of_actor(stages_resp.mapping, actor_name)
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
        self._render_combat_summary(
            log, combat.name, combat.state.name, combat.result.name, combat.retreated
        )
        self._render_stage_actors(log, stage_name, entities_resp.entities_serialization)

        if combat.state == CombatState.INITIALIZATION:
            log.write(INIT_COMMANDS_MENU)
        else:
            log.write(
                f"[dim]当前战斗状态为 {combat.state.name}，本页仅处理 "
                "INITIALIZATION 阶段的操作；ONGOING 等状态将在专属页面处理（开发中）。[/]"
            )

    ########################################################################################################################
    @staticmethod
    def _find_stage_of_actor(
        mapping: Dict[str, List[str]], actor_name: str
    ) -> Optional[str]:
        """在场景映射中查找玩家控制角色所在的场景名。"""
        for stage_name, names in mapping.items():
            if actor_name in names:
                return stage_name
        return None

    ########################################################################################################################
    @staticmethod
    def _find_component_data(
        entity: EntitySerialization, component_name: str
    ) -> Optional[Dict[str, Any]]:
        """在实体的组件序列化列表中按类名查找组件数据。"""
        for component in entity.components:
            if component.name == component_name:
                return component.data
        return None

    ########################################################################################################################
    def _render_combat_summary(
        self,
        log: RichLog,
        name: str,
        state_name: str,
        result_name: str,
        retreated: bool,
    ) -> None:
        """渲染战斗宏观信息（不含 rounds 细节）。"""
        log.write("[bold yellow]── 战斗宏观状态 ─────────────────────────────────[/]")
        log.write(f"  名称：   [bold]{name}[/]")
        log.write(f"  状态：   [cyan]{state_name}[/]")
        log.write(f"  结果：   [magenta]{result_name}[/]")
        log.write(f"  已撤退： {'[red]是[/]' if retreated else '[green]否[/]'}")
        log.write("")

    ########################################################################################################################
    def _render_stage_actors(
        self,
        log: RichLog,
        stage_name: str,
        entities: List[EntitySerialization],
    ) -> None:
        """渲染场景名 + 场景内所有 actor 的有效属性。"""
        log.write(f"[bold yellow]── 场景：{display_name(stage_name)} ─────────────[/]")

        actor_entities = [e for e in entities if e.name != stage_name]
        if not actor_entities:
            log.write("  [dim]（场景内暂无角色）[/]")
            log.write("")
            return

        for entity in actor_entities:
            stats_data = self._find_component_data(
                entity, CharacterStatsComponent.__name__
            )
            if stats_data is None:
                log.write(f"  [dim]{display_name(entity.name)}：缺少属性组件，跳过[/]")
                continue

            base_stats = CharacterStatsComponent(**stats_data).stats

            status_effects_data = self._find_component_data(
                entity, StatusEffectsComponent.__name__
            )
            status_effects = (
                StatusEffectsComponent(**status_effects_data).status_effects
                if status_effects_data is not None
                else None
            )

            equipped_gear_data = self._find_component_data(
                entity, EquippedGearComponent.__name__
            )
            equipped_gear = (
                EquippedGearComponent(**equipped_gear_data).item
                if equipped_gear_data is not None
                else None
            )

            effective_stats = compute_effective_stats(
                base_stats, status_effects, equipped_gear
            )
            role_label = self._role_label(entity)
            log.write(
                f"  {role_label} [bold]{display_name(entity.name)}[/]  "
                f"HP:[yellow]{effective_stats.hp}/{effective_stats.max_hp}[/]  "
                f"攻:{effective_stats.attack}  防:{effective_stats.defense}  "
                f"能量:{effective_stats.energy}  速度:{effective_stats.speed}"
            )
        log.write("")

    ########################################################################################################################
    def _role_label(self, entity: EntitySerialization) -> str:
        """依据实体挂载的阵营标记组件返回展示标签。"""
        if self._find_component_data(entity, PlayerComponent.__name__) is not None:
            return "[bold green]👑玩家[/]"
        if self._find_component_data(entity, NPCComponent.__name__) is not None:
            return "[bold cyan]🤝队友[/]"
        if self._find_component_data(entity, MonsterComponent.__name__) is not None:
            return "[bold red]👹怪物[/]"
        return "[dim]？[/]"

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
            self.app.push_screen(CombatStartActionScreen())
            return

        try:
            stages_resp = await get_stages_state(self.game_client)
            stage_name = self._find_stage_of_actor(stages_resp.mapping, actor_name)
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
