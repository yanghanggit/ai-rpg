"""战斗流程处理模块"""

import random
from typing import Dict, List, Optional, Sequence, Set, Tuple

from loguru import logger

from ..entitas import Entity, Matcher
from ..models import (
    ActorComponent,
    CharacterStats,
    CharacterStatsComponent,
    DeathComponent,
    DiscardPileComponent,
    DrawPileComponent,
    ExhaustPileComponent,
    HandComponent,
    MonsterComponent,
    PartyMemberComponent,
    Round,
    RoundStatsComponent,
    TargetType,
    compute_effective_stats,
)
from .dbg_game import DBGGame


#################################################################################################################################################
def compute_character_stats(entity: Entity) -> CharacterStats:
    """计算角色的最终有效属性，聚合基础属性与手牌格挡。"""
    assert entity.has(ActorComponent), f"{entity.name} 缺少 ActorComponent"
    assert entity.has(
        CharacterStatsComponent
    ), f"{entity.name} 缺少 CharacterStatsComponent"

    stats_comp = entity.get(CharacterStatsComponent)
    return compute_effective_stats(
        stats_comp.stats,
        entity.get(HandComponent) if entity.has(HandComponent) else None,
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
    ret = game.get_actors_in_stage(entity)
    return {actor for actor in ret if not actor.has(DeathComponent)}


#################################################################################################################################################
def get_alive_party_members_in_stage(
    anchor_entity: Entity, dbg_game: DBGGame
) -> List[Entity]:
    """获取锚点实体所在场景中所有存活的队伍成员。"""
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
    self_target: bool = False,
) -> Tuple[List[str], str]:
    """根据 target_type 解析并验证目标。self_target=True 时锁定出牌者自身；否则要求 passed_targets 恰好 1 个元素作为锚点。"""

    if self_target:
        # self_target 为 True 时，目标锁定为出牌者自身
        return [actor_entity.name], ""

    # self_target 为 False 时，要求 passed_targets 恰好 1 个元素作为锚点
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

            # 如果命中数量大于阵营存活角色数量，需要进行重复抽取以满足命中数量
            if hit_count > len(camp_members):

                # 先将阵营中所有存活角色加入目标列表，再随机补足剩余命中数量
                spread_targets = list(camp_members) + random.choices(
                    camp_members, k=hit_count - len(camp_members)
                )

                # 将目标列表打乱顺序，保证随机性
                random.shuffle(spread_targets)
            else:
                # 如果命中数量不超过阵营存活角色数量，直接随机抽取命中数量的目标
                spread_targets = random.choices(camp_members, k=hit_count)

            # 返回最终的 SPREAD 类型目标列表
            return [e.name for e in spread_targets], ""

        case _:
            assert False, f"未知的目标类型：{target_type}"
            # return [], f"未知的目标类型：{target_type}"


#######################################################################################################################################
def clear_round_state(game: DBGGame) -> None:
    """清除所有角色实体的每回合可变状态（手牌归入弃牌堆 + 回合动态属性）。"""

    # 清除所有角色实体的手牌组件（STS 标准：回合末未出牌进弃牌堆）
    for entity in game.get_group(
        Matcher(all_of=[HandComponent, DiscardPileComponent, DrawPileComponent])
    ).entities.copy():

        hand_comp = entity.get(HandComponent)
        discard_pile_comp = entity.get(DiscardPileComponent)

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

        # 无论是否有手牌，回合末统一移除 HandComponent
        entity.remove(HandComponent)

    # 清除所有角色实体的回合动态属性组件
    for entity in game.get_group(Matcher(RoundStatsComponent)).entities.copy():
        logger.debug(f"clear round stats: {entity.name}")
        entity.remove(RoundStatsComponent)


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
