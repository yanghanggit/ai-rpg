"""CombatInitScreen 与 CombatOngoingScreen 共用的渲染 / 查找辅助函数。

纯函数集合，不依赖 Screen 实例，便于两个页面复用同一套「战斗宏观状态」与
「场景内角色有效属性」渲染逻辑，避免重复实现。
"""

from typing import Any, Dict, List, Optional

from textual.widgets import RichLog

from ..models import (
    CharacterStats,
    CharacterStatsComponent,
    DeathComponent,
    EntitySerialization,
    HandComponent,
    MonsterComponent,
    NPCComponent,
    PlayerComponent,
    RoundStatsComponent,
    compute_effective_stats,
)
from .utils import display_name, render_card


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
def classify_faction(entity: Optional[EntitySerialization]) -> str:
    """依据阵营标记组件返回 "party"（玩家 + 队友）/ "monster"（怪物）/ "unknown"。

    供出牌 / 使用消耗品等需要按 TargetType 解析目标候选的页面共用，避免各自
    重复实现同一套阵营判断逻辑。
    """
    if entity is None:
        return "unknown"
    if find_component_data(entity, PlayerComponent.__name__) is not None:
        return "party"
    if find_component_data(entity, NPCComponent.__name__) is not None:
        return "party"
    if find_component_data(entity, MonsterComponent.__name__) is not None:
        return "monster"
    return "unknown"


###############################################################################################################################################
def compute_effective_stats_for(
    entity: EntitySerialization,
) -> Optional[CharacterStats]:
    """计算实体的基础属性；缺少 CharacterStatsComponent 时返回 None。"""
    stats_data = find_component_data(entity, CharacterStatsComponent.__name__)
    if stats_data is None:
        return None

    return compute_effective_stats(CharacterStatsComponent(**stats_data).stats)


###############################################################################################################################################
def resolve_current_energy(
    entity: EntitySerialization, effective_stats: Optional[CharacterStats]
) -> int:
    """解析实体本回合剩余可用 energy。"""
    round_stats_data = find_component_data(entity, RoundStatsComponent.__name__)
    if round_stats_data is not None:
        return RoundStatsComponent(**round_stats_data).energy
    return 0


###############################################################################################################################################
def write_actor_detail(
    log: RichLog,
    entity: EntitySerialization,
    index_label: str = "",
) -> None:
    """渲染单个角色的有效属性 + 手牌完整详情，供出牌 / 怪物回合等
    需要展示当前 turn 角色详情的页面复用，避免各自重复实现。

    index_label: 非空时与角色名写在同一行前面（如目标候选列表的编号）。
    """
    effective_stats = compute_effective_stats_for(entity)
    if effective_stats is None:
        log.write(
            f"  {index_label}[yellow]{display_name(entity.name)} 缺少属性组件，跳过[/]"
        )
        return

    hand_data = find_component_data(entity, HandComponent.__name__)

    hand_comp = HandComponent(**hand_data) if hand_data is not None else None
    death_mark = (
        "  [bold red]（已战死）[/]"
        if find_component_data(entity, DeathComponent.__name__) is not None
        else ""
    )

    log.write(
        f"  {index_label}{role_label(entity)} [bold]{display_name(entity.name)}[/]{death_mark}"
    )
    log.write(
        f"    HP:[yellow]{effective_stats.hp}/{effective_stats.max_hp}[/]  "
        f"攻:{effective_stats.attack}  防:{effective_stats.defense}  "
        f"能量:{resolve_current_energy(entity, effective_stats)}"
    )

    if hand_comp is not None and hand_comp.cards:
        log.write(f"    手牌（{len(hand_comp.cards)}）：")
        for card in hand_comp.cards:
            log.write(render_card(card))
    else:
        log.write("    手牌： [dim]（无）[/]")


###############################################################################################################################################
def render_stage_actors(
    log: RichLog,
    stage_name: str,
    entities: List[EntitySerialization],
) -> None:
    """渲染场景名 + 场景内所有 actor 的有效属性。

    手牌数量仅在实体实际挂载 HandComponent 时才附加显示（由服务端按战斗阶段决定是否挂载，
    如 INITIALIZATION 阶段通常尚未创建 HandComponent，ONGOING 阶段才会有），本函数只需按存在与否稳健地判断即可，
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

        hand_data = find_component_data(entity, HandComponent.__name__)
        hand_component = HandComponent(**hand_data) if hand_data is not None else None

        effective_stats = compute_effective_stats(base_stats)
        current_energy = resolve_current_energy(entity, effective_stats)
        label = role_label(entity)
        is_dead = find_component_data(entity, DeathComponent.__name__) is not None
        death_mark = "  [bold red]（已战死）[/]" if is_dead else ""
        line = (
            f"  {label} [bold]{display_name(entity.name)}[/]{death_mark}  "
            f"HP:[yellow]{effective_stats.hp}/{effective_stats.max_hp}[/]  "
            f"攻:{effective_stats.attack}  防:{effective_stats.defense}  "
            f"能量:{current_energy}"
        )

        if hand_component is not None:
            line += f"  手牌:{len(hand_component.cards)}"

        log.write(line)
    log.write("")
