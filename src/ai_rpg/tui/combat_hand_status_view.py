"""查看当前参战角色手牌与状态效果的 Screen。"""

from typing import List, Optional, final

from loguru import logger
from textual import work
from textual.app import ComposeResult
from textual.widgets import RichLog

from ..models import (
    CharacterStatsComponent,
    DeathComponent,
    EntitySerialization,
    EquippedGearComponent,
    HandComponent,
    StatusEffectsComponent,
    compute_effective_stats,
)
from .base import BaseGameScreen
from .combat_common import find_component_data, resolve_current_energy, role_label
from .combat_data_access import get_entities_details
from .utils import display_name, render_card, render_status_effect

HEADER = """\
[bold cyan]── 查看手牌 + 状态效果 ──────────────────────────────────────[/]

[dim]显示当前战斗所有参战角色的有效属性、状态效果与手牌详情。[bold]Escape[/] 返回。[/]
"""


ACTOR_DIVIDER = "[bold cyan]══════════════════════════════════════════════════[/]"


@final
class CombatHandStatusViewScreen(BaseGameScreen):
    """展示当前参战 actor 的有效属性、状态效果与手牌详情。"""

    CSS = """
    CombatHandStatusViewScreen {
        align: center middle;
    }

    #combat-hand-status-log {
        border: solid $primary;
        padding: 0 1;
        height: 1fr;
    }
    """

    BINDINGS = [
        ("escape", "go_back", "返回"),
    ]

    def __init__(self, participant_names: List[str]) -> None:
        super().__init__()
        self._participant_names = list(dict.fromkeys(participant_names))

    def compose(self) -> ComposeResult:
        yield RichLog(
            id="combat-hand-status-log", highlight=True, markup=True, wrap=True
        )

    def on_mount(self) -> None:
        log = self.query_one(RichLog)
        log.write(HEADER)
        self._load_details()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    @work
    async def _load_details(self) -> None:
        log = self.query_one(RichLog)
        logger.info(
            "CombatHandStatusViewScreen._load_details: participants={} ",
            self._participant_names,
        )

        if not self._participant_names:
            log.write("[yellow]当前战斗暂无参战角色。[/]")
            return

        try:
            resp = await get_entities_details(self.game_client, self._participant_names)
        except Exception as e:
            logger.error(
                f"CombatHandStatusViewScreen._load_details: 查询失败 error={e}"
            )
            log.write(f"[bold red]❌ 加载手牌与状态效果失败：{e}[/]")
            return

        entity_map = {
            entity.name: entity
            for entity in resp.entities_serialization
            if entity.name in self._participant_names
        }

        for i, actor_name in enumerate(self._participant_names):
            if i > 0:
                log.write(ACTOR_DIVIDER)
            entity = entity_map.get(actor_name)
            if entity is None:
                log.write(f"[yellow]未找到参战角色：{display_name(actor_name)}[/]")
                log.write("")
                continue
            self._write_actor(log, entity)

    def _write_actor(self, log: RichLog, entity: EntitySerialization) -> None:
        stats_data = find_component_data(entity, CharacterStatsComponent.__name__)
        if stats_data is None:
            log.write(
                f"[yellow]{display_name(entity.name)} 缺少 CharacterStatsComponent，跳过。[/]"
            )
            log.write("")
            return

        status_data = find_component_data(entity, StatusEffectsComponent.__name__)
        hand_data = find_component_data(entity, HandComponent.__name__)
        equipped_gear_data = find_component_data(entity, EquippedGearComponent.__name__)

        status_comp = (
            StatusEffectsComponent(**status_data) if status_data is not None else None
        )
        hand_comp = HandComponent(**hand_data) if hand_data is not None else None
        equipped_gear = (
            EquippedGearComponent(**equipped_gear_data).item
            if equipped_gear_data is not None
            else None
        )

        effective_stats = compute_effective_stats(
            CharacterStatsComponent(**stats_data).stats,
            status_comp.status_effects if status_comp is not None else None,
            equipped_gear,
        )

        death_mark = (
            "  [bold red]（已战死）[/]"
            if find_component_data(entity, DeathComponent.__name__) is not None
            else ""
        )

        # ── 角色标题 + 有效属性（格式与 render_stage_actors 一致） ──
        log.write(
            f"{role_label(entity)} [bold]{display_name(entity.name)}[/]{death_mark}"
        )
        log.write(
            f"  HP:[yellow]{effective_stats.hp}/{effective_stats.max_hp}[/]  "
            f"攻:{effective_stats.attack}  防:{effective_stats.defense}  "
            f"能量:{resolve_current_energy(entity, effective_stats)}  速度:{effective_stats.speed}"
        )
        log.write("")

        self._write_status_effects(log, status_comp, entity.name)
        log.write("")
        self._write_hand(log, hand_comp)
        log.write("")

    def _write_status_effects(
        self,
        log: RichLog,
        status_comp: Optional[StatusEffectsComponent],
        entity_name: str,
    ) -> None:
        if status_comp is None:
            log.write("  [bold]状态效果：[/]  [dim]（无）[/]")
            return

        effects = status_comp.status_effects
        log.write(f"  [bold]状态效果（{len(effects)}）：[/]")
        if not effects:
            log.write("    [dim]（无状态效果）[/]")
            return
        for effect in effects:
            log.write(render_status_effect(effect, entity_name))

    def _write_hand(self, log: RichLog, hand_comp: Optional[HandComponent]) -> None:
        if hand_comp is None:
            log.write("  [bold]手牌：[/]  [dim]（无）[/]")
            return

        log.write(f"  [bold]手牌（{len(hand_comp.cards)}）：[/]")
        if not hand_comp.cards:
            log.write("    [dim]（手牌为空）[/]")
            return
        for card in hand_comp.cards:
            log.write(render_card(card))
