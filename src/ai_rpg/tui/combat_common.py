"""CombatRoomScreen 与 CombatOngoingScreen 共用的渲染 / 查找辅助函数。

纯函数集合，不依赖 Screen 实例，便于两个页面复用同一套「战斗宏观状态」与
「场景内角色有效属性」渲染逻辑，避免重复实现。
"""

from typing import Any, Dict, List, Optional

from textual.widgets import RichLog

from ..models import (
    CharacterStatsComponent,
    DeathComponent,
    EntitySerialization,
    EquippedGearComponent,
    HandComponent,
    MonsterComponent,
    NPCComponent,
    PlayerComponent,
    StatusEffectsComponent,
    compute_effective_stats,
)
from .utils import display_name


###############################################################################################################################################
def find_component_data(
    entity: EntitySerialization, component_name: str
) -> Optional[Dict[str, Any]]:
    """在实体的组件序列化列表中按类名查找组件数据。"""
    for component in entity.components:
        if component.name == component_name:
            return component.data
    return None


###############################################################################################################################################
def find_stage_of_actor(
    mapping: Dict[str, List[str]], actor_name: str
) -> Optional[str]:
    """在场景映射中查找玩家控制角色所在的场景名。"""
    for stage_name, names in mapping.items():
        if actor_name in names:
            return stage_name
    return None


###############################################################################################################################################
def role_label(entity: EntitySerialization) -> str:
    """依据实体挂载的阵营标记组件返回展示标签。"""
    if find_component_data(entity, PlayerComponent.__name__) is not None:
        return "[bold green]👑玩家[/]"
    if find_component_data(entity, NPCComponent.__name__) is not None:
        return "[bold cyan]🤝队友[/]"
    if find_component_data(entity, MonsterComponent.__name__) is not None:
        return "[bold red]👹怪物[/]"
    return "[dim]？[/]"


###############################################################################################################################################
def render_combat_summary(
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


###############################################################################################################################################
def render_stage_actors(
    log: RichLog,
    stage_name: str,
    entities: List[EntitySerialization],
) -> None:
    """渲染场景名 + 场景内所有 actor 的有效属性。

    手牌数量 / 状态效果数量仅在实体实际挂载 HandComponent / StatusEffectsComponent
    时才附加显示（由服务端按战斗阶段决定是否挂载，如 INITIALIZATION 阶段通常尚未
    创建 HandComponent，ONGOING 阶段才会有），本函数只需按存在与否稳健地判断即可，
    无需调用方显式传入阶段相关的开关。
    """
    log.write(f"[bold yellow]── 场景：{display_name(stage_name)} ─────────────[/]")

    actor_entities = [e for e in entities if e.name != stage_name]
    if not actor_entities:
        log.write("  [dim]（场景内暂无角色）[/]")
        log.write("")
        return

    for entity in actor_entities:
        stats_data = find_component_data(entity, CharacterStatsComponent.__name__)
        if stats_data is None:
            log.write(f"  [dim]{display_name(entity.name)}：缺少属性组件，跳过[/]")
            continue

        base_stats = CharacterStatsComponent(**stats_data).stats

        status_effects_data = find_component_data(
            entity, StatusEffectsComponent.__name__
        )
        status_effects = (
            StatusEffectsComponent(**status_effects_data).status_effects
            if status_effects_data is not None
            else None
        )

        equipped_gear_data = find_component_data(entity, EquippedGearComponent.__name__)
        equipped_gear = (
            EquippedGearComponent(**equipped_gear_data).item
            if equipped_gear_data is not None
            else None
        )

        effective_stats = compute_effective_stats(
            base_stats, status_effects, equipped_gear
        )
        label = role_label(entity)
        is_dead = find_component_data(entity, DeathComponent.__name__) is not None
        death_mark = "  [bold red]（已战死）[/]" if is_dead else ""
        line = (
            f"  {label} [bold]{display_name(entity.name)}[/]{death_mark}  "
            f"HP:[yellow]{effective_stats.hp}/{effective_stats.max_hp}[/]  "
            f"攻:{effective_stats.attack}  防:{effective_stats.defense}  "
            f"能量:{effective_stats.energy}  速度:{effective_stats.speed}"
        )

        hand_data = find_component_data(entity, HandComponent.__name__)
        if hand_data is not None:
            line += f"  手牌:{len(HandComponent(**hand_data).cards)}"

        if status_effects is not None:
            line += f"  状态效果:{len(status_effects)}"

        log.write(line)
    log.write("")
