"""
实体级操作函数

从 DBGGame 中提取的纯函数，仅依赖 Entity 对象，不依赖游戏状态。
"""

from typing import List
from loguru import logger
from ..entitas import Entity
from ..models import (
    ActorComponent,
    AddStatusEffectsAction,
    CharacterStats,
    CharacterStatsComponent,
    EquippedGearComponent,
    PhaseType,
    RoundStatsComponent,
    StatusEffect,
    StatusEffectsComponent,
    compute_effective_stats,
)


def get_status_effects_by_phase(entity: Entity, phase: PhaseType) -> List[StatusEffect]:
    """返回实体在指定战斗阶段生效的状态效果列表。"""
    status_comp = entity.get(StatusEffectsComponent)
    assert status_comp is not None, f"角色 {entity.name} 缺少 StatusEffectsComponent！"
    if status_comp is None:
        return []
    return [e for e in status_comp.status_effects if e.phase == phase]


def compute_character_stats(entity: Entity) -> CharacterStats:
    """计算角色的最终有效属性，聚合基础属性与已装备物品的属性加成。"""
    assert entity.has(ActorComponent), f"{entity.name} 缺少 ActorComponent"
    assert entity.has(
        CharacterStatsComponent
    ), f"{entity.name} 缺少 CharacterStatsComponent"

    stats_comp = entity.get(CharacterStatsComponent)
    return compute_effective_stats(
        stats_comp.stats,
        (
            entity.get(StatusEffectsComponent).status_effects
            if entity.has(StatusEffectsComponent)
            else None
        ),
        (
            entity.get(EquippedGearComponent).item
            if entity.has(EquippedGearComponent)
            else None
        ),
    )


def set_character_hp(entity: Entity, hp: int) -> CharacterStats:
    """设置角色的当前 HP，自动 clamp 至 [0, max_hp]。"""
    assert entity.has(ActorComponent), f"{entity.name} 缺少 ActorComponent"
    assert entity.has(
        CharacterStatsComponent
    ), f"{entity.name} 缺少 CharacterStatsComponent"

    stats_comp = entity.get(CharacterStatsComponent)
    max_hp = compute_character_stats(entity).max_hp
    clamped = max(0, min(hp, max_hp))
    stats_comp.stats.hp = clamped

    return compute_character_stats(entity)


def apply_status_effect_patch(
    entity: Entity, status_effect_name: str, counter: int
) -> None:
    """更新实体上指定状态效果的 counter，并记录更新日志。"""
    assert entity.has(
        StatusEffectsComponent
    ), f"{entity.name} 缺少 StatusEffectsComponent，无法回写状态效果计数器"
    status_comp = entity.get(StatusEffectsComponent)
    effect_map = {e.name: e for e in status_comp.status_effects}
    if status_effect_name in effect_map:
        old_counter = effect_map[status_effect_name].counter
        effect_map[status_effect_name].counter = counter
        logger.info(
            f"更新 {entity.name} 状态效果「{status_effect_name}」 counter: "
            f"{old_counter} → {counter}"
        )
    else:
        logger.warning(
            f"status_effect_patches 中的效果「{status_effect_name}」"
            f"在 {entity.name} 的 StatusEffectsComponent 中不存在，跳过"
        )


def get_energy(entity: Entity) -> int:
    """获取角色实体的当前回合剩余行动次数（RoundStatsComponent.energy）。"""
    round_stats = entity.get(RoundStatsComponent)
    return round_stats.energy if round_stats is not None else 0


def consume_energy(entity: Entity, amount: int = 1) -> None:
    """消耗角色实体指定点数的 energy。"""
    assert entity.has(RoundStatsComponent), f"{entity.name} 缺少 RoundStatsComponent"
    assert (
        get_energy(entity) > 0
    ), f"{entity.name} 能量不足！当前 energy={get_energy(entity)}"
    entity.replace(
        RoundStatsComponent,
        entity.name,
        max(0, get_energy(entity) - amount),
    )


def give_energy(entity: Entity, amount: int = 1) -> None:
    """改变角色实体的 energy（用于卡牌 energy_delta 效果）。"""
    if not entity.has(RoundStatsComponent):
        return
    entity.replace(
        RoundStatsComponent,
        entity.name,
        max(0, get_energy(entity) + amount),
    )


def accumulate_status_effects_action(entity: Entity, task_hints: List[str]) -> None:
    """为实体追加 AddStatusEffectsAction，自动合并已有的 task_hints。"""
    existing = (
        entity.get(AddStatusEffectsAction)
        if entity.has(AddStatusEffectsAction)
        else None
    )
    merged = (existing.task_hints if existing is not None else []) + task_hints
    entity.replace(AddStatusEffectsAction, entity.name, merged)
