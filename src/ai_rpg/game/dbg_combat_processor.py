"""战斗流程处理模块"""

import random
from typing import Dict, List, Optional, Sequence, Set
from loguru import logger
from ..entitas import Entity, Matcher
from ..models import (
    ActorComponent,
    AddStatusEffectsAction,
    CharacterStats,
    CharacterStatsComponent,
    DeathComponent,
    EquippedGearComponent,
    HumanMessage,
    PhaseType,
    Round,
    RoundStatsComponent,
    PartyMemberComponent,
    MonsterComponent,
    StatusEffect,
    StatusEffectsComponent,
    TargetType,
    GearItem,
    compute_effective_stats,
)
from .dbg_game import DBGGame


#################################################################################################################################################
def get_status_effects_by_phase(entity: Entity, phase: PhaseType) -> List[StatusEffect]:
    """返回实体在指定战斗阶段生效的状态效果列表。"""
    status_comp = entity.get(StatusEffectsComponent)
    assert status_comp is not None, f"角色 {entity.name} 缺少 StatusEffectsComponent！"
    if status_comp is None:
        return []
    return [e for e in status_comp.status_effects if e.phase == phase]


#################################################################################################################################################
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


#################################################################################################################################################
def collect_target_character_stats(
    game: DBGGame, target_names: Sequence[str]
) -> Dict[str, CharacterStats]:
    """按目标名去重保序收集目标最终属性。"""
    target_stats: Dict[str, CharacterStats] = {}
    for target_name in dict.fromkeys(target_names):
        target_entity = game.get_entity_by_name(target_name)
        assert target_entity is not None, f"无法找到目标实体: {target_name}"
        target_stats[target_name] = compute_character_stats(target_entity)
    return target_stats


#################################################################################################################################################
def collect_target_arbitration_effects(
    game: DBGGame, target_names: Sequence[str]
) -> Dict[str, List[StatusEffect]]:
    """按目标名去重保序收集目标仲裁阶段状态效果。"""
    target_arbitration_effects: Dict[str, List[StatusEffect]] = {}
    for target_name in dict.fromkeys(target_names):
        target_entity = game.get_entity_by_name(target_name)
        assert target_entity is not None, f"无法找到目标实体: {target_name}"
        target_arbitration_effects[target_name] = get_status_effects_by_phase(
            target_entity, PhaseType.ARBITRATION
        )
    return target_arbitration_effects


#################################################################################################################################################
def find_equipped_gear_holder(
    game: DBGGame, selected_item: GearItem
) -> Optional[Entity]:
    """返回当前装备了指定 GearItem 的实体；未装备则返回 None。"""
    for holder in game.get_group(Matcher(EquippedGearComponent)).entities:
        if holder.get(EquippedGearComponent).item.uuid == selected_item.uuid:
            return holder
    return None


#################################################################################################################################################
def remove_equipped_gear(game: DBGGame, selected_item: GearItem) -> None:
    """扫描全局：移除所有持有同名装备的 EquippedGearComponent（保证全局唯一）。"""
    # 扫描全局，移除所有持有同名装备的 EquippedGearComponent
    remove_count = 0

    # 使用 copy() 避免在迭代过程中修改集合导致 RuntimeError
    for holder in game.get_group(Matcher(EquippedGearComponent)).entities.copy():

        equipped_gear_comp = holder.get(EquippedGearComponent)
        if equipped_gear_comp.item.uuid != selected_item.uuid:
            continue

        logger.info(
            f"移除 {holder.name} 的 EquippedGearComponent（装备: {equipped_gear_comp.item.name}）"
        )
        holder.remove(EquippedGearComponent)
        remove_count += 1

    # 全局应仅有一个实体装备了 selected_item，若移除数量 > 0，则必须为 1
    if remove_count > 0:
        assert (
            remove_count == 1
        ), f"全局应仅有一个实体装备了 {selected_item.name}，实际移除数量: {remove_count}"


#################################################################################################################################################
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


#################################################################################################################################################
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


#################################################################################################################################################
def get_energy(entity: Entity) -> int:
    """获取角色实体的当前回合剩余行动次数（RoundStatsComponent.energy）。"""
    round_stats = entity.get(RoundStatsComponent)
    return round_stats.energy if round_stats is not None else 0


#################################################################################################################################################
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


#################################################################################################################################################
def give_energy(entity: Entity, amount: int = 1) -> None:
    """改变角色实体的 energy（用于卡牌 energy_delta 效果）。"""
    if not entity.has(RoundStatsComponent):
        return
    entity.replace(
        RoundStatsComponent,
        entity.name,
        max(0, get_energy(entity) + amount),
    )


#################################################################################################################################################
def accumulate_status_effects_action(entity: Entity, task_hints: List[str]) -> None:
    """为实体追加 AddStatusEffectsAction，自动合并已有的 task_hints。"""
    existing = (
        entity.get(AddStatusEffectsAction)
        if entity.has(AddStatusEffectsAction)
        else None
    )
    merged = (existing.task_hints if existing is not None else []) + task_hints
    entity.replace(AddStatusEffectsAction, entity.name, merged)


#################################################################################################################################################
def _format_zero_health_message() -> str:
    """生成 HP 归零时发送给角色的通知消息"""
    return "# 你的HP已归零，失去战斗能力！"


#################################################################################################################################################
def process_zero_health_entities(game: DBGGame) -> None:
    """为 HP 归零且尚未标记死亡的实体添加 DeathComponent。

    Args:
        game: DBG 游戏实例
    """
    defeated_entities = game.get_group(
        Matcher(all_of=[CharacterStatsComponent], none_of=[DeathComponent])
    ).entities.copy()

    for entity in defeated_entities:
        entity_hp = compute_character_stats(entity).hp
        if entity_hp <= 0:
            logger.info(f"{entity.name} 已被击败，HP={entity_hp}")
            game.add_human_message(
                entity, HumanMessage(content=_format_zero_health_message())
            )
            entity.replace(DeathComponent, entity.name)


#################################################################################################################################################
def get_current_turn_actor(game: DBGGame, round: Round) -> Optional[str]:
    """从最新回合快照中找出第一个尚未 pass turn 的角色名。"""
    if not round.action_order:
        return None

    completed = set(round.completed_actors)
    for actor_name in round.action_order:
        if actor_name in completed:
            continue
        actor_entity = game.get_actor_entity(actor_name)
        assert actor_entity is not None, f"无法找到角色实体: {actor_name}"
        if actor_entity.has(DeathComponent):
            continue
        return actor_name

    return None


#################################################################################################################################################
def advance_turn(game: DBGGame, round: Round) -> None:
    """消耗 energy 后重新计算当前 turn 行动者，并写回 round.current_turn_actor_name。"""
    round.current_actor = get_current_turn_actor(game, round)
    logger.debug(
        f"advance_turn: current_turn_actor_name updated to {round.current_actor}"
    )


#################################################################################################################################################
def get_alive_actors_in_stage(game: DBGGame, entity: Entity) -> Set[Entity]:
    """获取指定场景上存活的 Actor 实体。"""
    ret = game.get_actors_in_stage(entity)
    return {actor for actor in ret if not actor.has(DeathComponent)}


#################################################################################################################################################
def get_alive_party_members_in_stage(
    anchor_entity: Entity, dbg_game: DBGGame
) -> List[Entity]:
    """获取锚点实体所在场景中所有存活的远征队成员。"""
    actor_entities = get_alive_actors_in_stage(dbg_game, anchor_entity)
    return [entity for entity in actor_entities if entity.has(PartyMemberComponent)]


#################################################################################################################################################
def get_alive_monsters_in_stage(
    anchor_entity: Entity, dbg_game: DBGGame
) -> List[Entity]:
    """获取锚点实体所在场景中所有存活的怪物。"""
    actor_entities = get_alive_actors_in_stage(dbg_game, anchor_entity)
    return [entity for entity in actor_entities if entity.has(MonsterComponent)]


#################################################################################################################################################
def pick_spread_targets(enemies: List[Entity], hit_count: int) -> List[Entity]:
    """按 hit_count 与候选敌人数量的关系，选取"散射"命中列表（ENEMY_SPREAD 专用）。"""
    if not enemies:
        return []

    if hit_count > len(enemies):
        assigned = list(enemies) + random.choices(enemies, k=hit_count - len(enemies))
        random.shuffle(assigned)
        return assigned

    return random.choices(enemies, k=hit_count)


#################################################################################################################################################
def resolve_targets(
    target_type: TargetType,
    hit_count: int,
    actor_entity: Entity,
    passed_targets: List[str],
    dbg_game: DBGGame,
) -> tuple[List[str], str]:
    """根据 target_type 解析并验证目标。"""

    is_actor_ally = actor_entity.has(PartyMemberComponent)

    def _get_enemies() -> List[Entity]:
        return (
            get_alive_monsters_in_stage(actor_entity, dbg_game)
            if is_actor_ally
            else get_alive_party_members_in_stage(actor_entity, dbg_game)
        )

    match target_type:
        case TargetType.ENEMY_SINGLE:
            enemy_names = {e.name for e in _get_enemies()}
            if len(passed_targets) != 1:
                return (
                    [],
                    f"ENEMY_SINGLE 目标数量必须为 1，实际收到 {len(passed_targets)} 个",
                )
            if passed_targets[0] not in enemy_names:
                return (
                    [],
                    f"目标 '{passed_targets[0]}' 不在存活敌方列表中: {sorted(enemy_names)}",
                )
            return list(passed_targets), ""

        case TargetType.ENEMY_ALL:
            return [e.name for e in _get_enemies()], ""

        case TargetType.ENEMY_SPREAD:
            enemies = _get_enemies()
            if not enemies:
                return [], "ENEMY_SPREAD：场上无存活敌方"
            return [e.name for e in pick_spread_targets(enemies, hit_count)], ""

        case TargetType.SELF_ONLY:
            return [actor_entity.name], ""

        case _:  # ALLY_SINGLE / ALLY_ALL — 不限制目标
            return list(passed_targets), ""


#################################################################################################################################################


def determine_camp_relationship(actor_entity: Entity, other_entity: Entity) -> str:
    """返回两角色间的阵营关系：'友方' 或 '敌方'。"""
    actor_is_ally = actor_entity.has(PartyMemberComponent)
    actor_is_enemy = actor_entity.has(MonsterComponent)
    other_is_ally = other_entity.has(PartyMemberComponent)
    other_is_enemy = other_entity.has(MonsterComponent)

    # 同是友方或同是敌方
    if (actor_is_ally and other_is_ally) or (actor_is_enemy and other_is_enemy):
        return "友方"

    return "敌方"


####################################################################################################################################
def get_max_num_cards(actor: Entity) -> int:
    """返回角色本回合应持有的手牌上限（PartyMember=3，Monster=1）。"""
    if actor.has(PartyMemberComponent):
        return 3
    if actor.has(MonsterComponent):
        return 1
    return 1


####################################################################################################################################
def get_cards_per_combat(actor_entity: Entity) -> int:
    """返回角色在本次战斗中的初始牌库数量（PartyMember=5，Monster=3）。"""
    if actor_entity.has(PartyMemberComponent):
        return 5
    if actor_entity.has(MonsterComponent):
        return 3
    return 3
