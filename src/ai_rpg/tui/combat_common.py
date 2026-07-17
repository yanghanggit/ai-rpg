"""CombatRoomScreen 与 CombatOngoingScreen 共用的渲染 / 查找辅助函数。

纯函数集合，不依赖 Screen 实例，便于两个页面复用同一套「战斗宏观状态」与
「场景内角色有效属性」渲染逻辑，避免重复实现。
"""

from typing import Any, Dict, List, Optional

from textual.widgets import RichLog

from ..models import (
    CharacterStats,
    CharacterStatsComponent,
    Combat,
    DeathComponent,
    EntitySerialization,
    EquippedGearComponent,
    HandComponent,
    MonsterComponent,
    NPCComponent,
    PlayerComponent,
    RoundStatsComponent,
    StatusEffectsComponent,
    compute_effective_stats,
)
from .utils import display_name, render_card, render_status_effect


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
def is_alive(entity: EntitySerialization) -> bool:
    """实体是否存活（未挂载 DeathComponent）。"""
    return find_component_data(entity, DeathComponent.__name__) is None


###############################################################################################################################################
def compute_effective_stats_for(
    entity: EntitySerialization,
) -> Optional[CharacterStats]:
    """计算实体的有效属性（聚合状态效果 + 已装备加成）；缺少 CharacterStatsComponent 时返回 None。"""
    stats_data = find_component_data(entity, CharacterStatsComponent.__name__)
    if stats_data is None:
        return None

    status_data = find_component_data(entity, StatusEffectsComponent.__name__)
    equipped_gear_data = find_component_data(entity, EquippedGearComponent.__name__)
    status_comp = (
        StatusEffectsComponent(**status_data) if status_data is not None else None
    )
    equipped_gear = (
        EquippedGearComponent(**equipped_gear_data).item
        if equipped_gear_data is not None
        else None
    )
    return compute_effective_stats(
        CharacterStatsComponent(**stats_data).stats,
        status_comp.status_effects if status_comp is not None else None,
        equipped_gear,
    )


###############################################################################################################################################
def resolve_current_energy(
    entity: EntitySerialization, effective_stats: Optional[CharacterStats]
) -> int:
    """解析实体本回合剩余可用 energy。

    优先读取 `RoundStatsComponent.energy`——这是本回合真正剩余的行动次数，由
    `CombatRoundTransitionSystem._start_new_round` 在回合开始时以
    `compute_character_stats(actor).energy` 初始化，此后随出牌/装备/过牌等消耗
    动作实时递减，只在回合开始的瞬间与 `effective_stats.energy` 相等。

    若实体尚未挂载该组件（如 INITIALIZATION 阶段战斗尚未进入任何回合），退回调用方
    已计算好的 `effective_stats.energy` 作为近似；`effective_stats` 为 None 时返回 0。
    """
    round_stats_data = find_component_data(entity, RoundStatsComponent.__name__)
    if round_stats_data is not None:
        return RoundStatsComponent(**round_stats_data).energy
    return effective_stats.energy if effective_stats is not None else 0


###############################################################################################################################################
def write_actor_detail(
    log: RichLog,
    entity: EntitySerialization,
    index_label: str = "",
) -> None:
    """渲染单个角色的有效属性 + 状态效果 + 手牌完整详情，供出牌 / 怪物回合等
    需要展示当前 turn 角色详情的页面复用，避免各自重复实现。

    index_label: 非空时与角色名写在同一行前面（如目标候选列表的编号）。
    """
    effective_stats = compute_effective_stats_for(entity)
    if effective_stats is None:
        log.write(
            f"  {index_label}[yellow]{display_name(entity.name)} 缺少属性组件，跳过[/]"
        )
        return

    status_data = find_component_data(entity, StatusEffectsComponent.__name__)
    hand_data = find_component_data(entity, HandComponent.__name__)

    status_comp = (
        StatusEffectsComponent(**status_data) if status_data is not None else None
    )
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
        f"能量:{resolve_current_energy(entity, effective_stats)}  速度:{effective_stats.speed}"
    )

    if status_comp is not None and status_comp.status_effects:
        log.write(f"    状态效果（{len(status_comp.status_effects)}）：")
        for effect in status_comp.status_effects:
            log.write(render_status_effect(effect, entity.name))
    else:
        log.write("    状态效果： [dim]（无）[/]")

    if hand_comp is not None and hand_comp.cards:
        log.write(f"    手牌（{len(hand_comp.cards)}）：")
        for card in hand_comp.cards:
            log.write(render_card(card))
    else:
        log.write("    手牌： [dim]（无）[/]")


###############################################################################################################################################
def render_combat_summary(
    log: RichLog,
    name: str,
    state_name: str,
    result_name: str,
    retreated: bool,
    total_rounds: Optional[int] = None,
) -> None:
    """渲染战斗宏观信息。

    total_rounds: 不为 None 时附加显示总局数（len(combat.rounds)）；用于战斗已
    结束的页面（如 CombatPostCombatScreen），此时不再展示「当前回合」细节，仅需
    知道总共打了多少局即可。ONGOING 阶段的页面通常单独渲染当前回合详情，无需
    传入此参数。
    """
    log.write("[bold yellow]── 战斗宏观状态 ─────────────────────────────────[/]")
    log.write(f"  名称：   [bold]{name}[/]")
    log.write(f"  状态：   [cyan]{state_name}[/]")
    log.write(f"  结果：   [magenta]{result_name}[/]")
    log.write(f"  已撤退： {'[red]是[/]' if retreated else '[green]否[/]'}")
    if total_rounds is not None:
        log.write(f"  总局数： [bold]{total_rounds}[/]")
    log.write("")


###############################################################################################################################################
def render_round_info(log: RichLog, combat: Combat) -> None:
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
        current_energy = resolve_current_energy(entity, effective_stats)
        label = role_label(entity)
        is_dead = find_component_data(entity, DeathComponent.__name__) is not None
        death_mark = "  [bold red]（已战死）[/]" if is_dead else ""
        line = (
            f"  {label} [bold]{display_name(entity.name)}[/]{death_mark}  "
            f"HP:[yellow]{effective_stats.hp}/{effective_stats.max_hp}[/]  "
            f"攻:{effective_stats.attack}  防:{effective_stats.defense}  "
            f"能量:{current_energy}  速度:{effective_stats.speed}"
        )

        hand_data = find_component_data(entity, HandComponent.__name__)
        if hand_data is not None:
            line += f"  手牌:{len(HandComponent(**hand_data).cards)}"

        if status_effects is not None:
            line += f"  状态效果:{len(status_effects)}"

        log.write(line)
    log.write("")
