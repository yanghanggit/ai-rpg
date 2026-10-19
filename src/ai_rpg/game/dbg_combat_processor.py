"""战斗流程处理模块"""

import random
from typing import List, Optional, Sequence, Set, Tuple

from loguru import logger

from ..entitas import Entity, Matcher
from ..models import (
    ActorComponent,
    Card,
    CharacterStats,
    CharacterStatsComponent,
    DeathComponent,
    DiscardPileComponent,
    DrawPileComponent,
    EquippedGearComponent,
    ExhaustPileComponent,
    HandComponent,
    MonsterComponent,
    PartyMemberComponent,
    Round,
    RoundStatsComponent,
    StressComponent,
    TargetType,
    compute_effective_stats,
    compute_hand_block,
)
from .dbg_game import DBGGame


#################################################################################################################################################
def compute_character_stats(entity: Entity) -> CharacterStats:
    """返回角色的基础属性（CharacterStats），不含手牌 block 加成。"""
    assert entity.has(ActorComponent), f"{entity.name} 缺少 ActorComponent"
    assert entity.has(
        CharacterStatsComponent
    ), f"{entity.name} 缺少 CharacterStatsComponent"

    stats_comp = entity.get(CharacterStatsComponent)
    equipped_gear = (
        entity.get(EquippedGearComponent) if entity.has(EquippedGearComponent) else None
    )
    return compute_effective_stats(stats_comp.stats, equipped_gear)


#################################################################################################################################################
def compute_character_hand_block(entity: Entity) -> int:
    """计算角色手牌提供的总格挡（block 之和）。"""
    hand = entity.get(HandComponent) if entity.has(HandComponent) else None
    return compute_hand_block(hand)


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
def add_stress(entity: Entity, amount: int = 1) -> int:
    """累加角色压力值（死亡计数），返回累加后的最新值。"""
    current = entity.get(StressComponent).value if entity.has(StressComponent) else 0
    new_value = current + amount
    entity.replace(StressComponent, entity.name, new_value)
    return new_value


#################################################################################################################################################
def mark_dead(entity: Entity) -> CharacterStats:
    """将角色标记为战败：挂载 DeathComponent，并使压力 +1。

    战死 / 超时判负 / 撤退均视为一次战败，统一走此入口。
    DeathComponent 会在复活时移除且无惩罚，故以 StressComponent 累计死亡次数；
    已是死亡状态时重复调用不会重复累加压力。
    """
    assert entity.has(ActorComponent), f"{entity.name} 缺少 ActorComponent"
    assert entity.has(
        CharacterStatsComponent
    ), f"{entity.name} 缺少 CharacterStatsComponent"

    if not entity.has(DeathComponent):
        add_stress(entity)

    entity.replace(DeathComponent, entity.name)

    return compute_character_stats(entity)


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
def get_alive_actors_in_stage(game: DBGGame, entity: Entity) -> Set[Entity]:
    """获取指定场景上存活的 Actor 实体。"""
    return game.get_actors_in_stage(entity, Matcher(none_of=[DeathComponent]))


#################################################################################################################################################
def get_alive_party_members_in_stage(
    anchor_entity: Entity, dbg_game: DBGGame
) -> List[Entity]:
    """获取锚点实体所在场景中所有存活的队伍成员。"""
    return list(
        dbg_game.get_actors_in_stage(
            anchor_entity,
            Matcher(all_of=[PartyMemberComponent], none_of=[DeathComponent]),
        )
    )


#################################################################################################################################################
def get_alive_monsters_in_stage(
    anchor_entity: Entity, dbg_game: DBGGame
) -> List[Entity]:
    """获取锚点实体所在场景中所有存活的怪物。"""
    return list(
        dbg_game.get_actors_in_stage(
            anchor_entity, Matcher(all_of=[MonsterComponent], none_of=[DeathComponent])
        )
    )


#################################################################################################################################################
def _expand_camp_members(
    anchor_target_name: str,
    actor_entity: Entity,
    dbg_game: DBGGame,
) -> Tuple[List[Entity], str]:
    """将单个阵营锚点目标名展开为该锚点所在阵营的全体存活角色。"""
    # 构建当前场景中所有存活角色的映射，便于根据锚点名称快速查找对应实体。
    alive_map = {e.name: e for e in get_alive_actors_in_stage(dbg_game, actor_entity)}
    anchor_entity = alive_map.get(anchor_target_name)
    if anchor_entity is None:
        return (
            [],
            f"目标 '{anchor_target_name}' 不在当前场景存活角色列表中: {sorted(alive_map)}",
        )

    # 根据锚点实体的阵营类型，返回该阵营的全体存活角色。
    if anchor_entity.has(PartyMemberComponent):
        return get_alive_party_members_in_stage(anchor_entity, dbg_game), ""
    if anchor_entity.has(MonsterComponent):
        return get_alive_monsters_in_stage(anchor_entity, dbg_game), ""

    # 如果锚点实体既不属于队伍也不属于怪物阵营，则返回错误。
    return [], f"目标 '{anchor_target_name}' 不属于任何可识别阵营"


#################################################################################################################################################
def resolve_targets(
    target_type: TargetType,
    hit_count: int,
    actor_entity: Entity,
    passed_targets: Sequence[str],
    dbg_game: DBGGame,
) -> Tuple[List[str], str]:
    """根据 target_type 解析并验证目标。SELF 时锁定出牌者自身；其余类型要求 passed_targets 恰好 1 个元素作为锚点。"""

    # SELF：目标锁定为出牌者本人，无需目标名，传入的目标列表被忽略。
    if target_type == TargetType.SELF:
        return [actor_entity.name], ""

    # 其余类型要求 passed_targets 恰好 1 个元素作为锚点
    if len(passed_targets) != 1:
        return (
            [],
            f"{target_type.value.upper()} 目标数量必须为 1（作为目标/阵营锚点），实际收到 {len(passed_targets)} 个",
        )

    # 获取锚点目标名称（passed_targets 中的唯一元素）
    anchor_target_name = passed_targets[0]

    match target_type:

        case TargetType.SINGLE:

            # 获取当前场景中所有存活角色的名称集合
            alive_names = {
                e.name for e in get_alive_actors_in_stage(dbg_game, actor_entity)
            }

            # SINGLE 类型目标必须在当前场景存活角色列表中
            if anchor_target_name not in alive_names:
                return (
                    [],
                    f"目标 '{anchor_target_name}' 不在当前场景存活角色列表中: {sorted(alive_names)}",
                )

            # 返回 SINGLE 类型目标的锚点名称作为目标列表
            return [anchor_target_name], ""

        case TargetType.ALL:

            # 获取阵营。
            camp_members, err = _expand_camp_members(
                anchor_target_name, actor_entity, dbg_game
            )

            # 如果获取阵营成员失败，返回错误
            if err:
                return [], err

            # 如果阵营当前无存活角色，返回错误
            if not camp_members:
                return [], "ALL：锚点所在阵营当前无存活角色"

            # 返回阵营中所有存活角色的名称列表作为目标列表
            return [e.name for e in camp_members], ""

        case TargetType.SPREAD:

            # 获取阵营。
            camp_members, err = _expand_camp_members(
                anchor_target_name, actor_entity, dbg_game
            )

            # 如果获取阵营成员失败，返回错误
            if err:
                return [], err

            # 如果阵营当前无存活角色，返回错误
            if not camp_members:
                return [], "SPREAD：锚点所在阵营当前无存活角色"

            # 每次命中独立随机落到阵营存活角色之一：可重复、可有人一次都没中，
            # 不做「每人至少一次」的保底（命中分配就是击数的直接随机结果）。
            spread_targets = random.choices(camp_members, k=hit_count)

            # 返回最终的 SPREAD 类型目标列表
            return [e.name for e in spread_targets], ""

        case _:
            assert False, f"未知的目标类型：{target_type}"
            # return [], f"未知的目标类型：{target_type}"


#######################################################################################################################################
def clear_round_state(game: DBGGame) -> List[Tuple[Entity, List[Card], List[Card]]]:
    """清除所有角色实体的每回合可变状态（手牌归入弃牌堆 + 回合动态属性）。

    返回每张手牌的去向 `(entity, 进弃牌堆, 进保留队列)`，供调用方写牌堆变更记忆。
    """

    settlements: List[Tuple[Entity, List[Card], List[Card]]] = []

    # 清除所有角色实体的手牌组件（STS 标准：回合末未出牌进弃牌堆）
    for entity in game.get_group(
        Matcher(all_of=[HandComponent, DiscardPileComponent, DrawPileComponent])
    ).entities.copy():

        hand_comp = entity.get(HandComponent)
        discard_pile_comp = entity.get(DiscardPileComponent)
        discard_cards: List[Card] = []
        retain_cards: List[Card] = []

        if hand_comp.cards:

            retain_cards = [c for c in hand_comp.cards if c.retain]
            discard_cards = [c for c in hand_comp.cards if not c.retain]

            # 将非 retain 的手牌归入弃牌堆（战斗子堆均为副本，不会回流 DeckComponent）
            discard_pile_comp.cards.extend(discard_cards)

            # retain 牌暂存到 DrawPile 的保留队列，下回合优先取回手牌
            if retain_cards:
                assert entity.has(
                    DrawPileComponent
                ), f"{entity.name} 缺少 DrawPileComponent，无法存放 retain 牌"
                draw_pile_comp = entity.get(DrawPileComponent)
                draw_pile_comp.retained_cards.extend(retain_cards)
                logger.debug(
                    f"clear hands: {entity.name} 将 {len(retain_cards)} 张 retain 牌转入 DrawPile 保留队列"
                )

            logger.debug(
                f"clear hands: {entity.name} 将 {len(discard_cards)} 张剩余手牌归入 DiscardPile，DiscardPile 累计 {len(discard_pile_comp.cards)} 张"
            )
        else:
            logger.debug(f"clear hands: {entity.name}")

        settlements.append((entity, discard_cards, retain_cards))

        # 无论是否有手牌，回合末统一移除 HandComponent
        entity.remove(HandComponent)

    # 清除所有角色实体的回合动态属性组件
    for entity in game.get_group(Matcher(RoundStatsComponent)).entities.copy():
        logger.debug(f"clear round stats: {entity.name}")
        entity.remove(RoundStatsComponent)

    return settlements


###################################################################################################################################################################
def assert_no_residual_combat_state(dbg_game: DBGGame) -> None:
    """断言战斗临时组件已被 pipeline（CombatRoundCleanupSystem/CombatOutcomeSystem/CombatPileTeardownSystem）清理干净，此函数不做任何清理动作。"""

    residual_entities = dbg_game.get_group(
        Matcher(
            any_of=[
                HandComponent,
                RoundStatsComponent,
                DrawPileComponent,
                DiscardPileComponent,
                ExhaustPileComponent,
            ]
        )
    ).entities

    assert not residual_entities, (
        "检测到残留战斗临时组件，pipeline 理应已清理完毕: "
        f"{[entity.name for entity in residual_entities]}"
    )
