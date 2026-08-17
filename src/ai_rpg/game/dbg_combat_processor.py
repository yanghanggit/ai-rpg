"""战斗流程处理模块"""

import random
from typing import Dict, List, Optional, Sequence, Set
from loguru import logger
from ..entitas import Entity, Matcher
from ..models import (
    ActorComponent,
    AddStatusEffectsAction,
    AffixTrigger,
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
    ConsumableItem,
    InventoryComponent,
    compute_effective_stats,
    HandComponent,
    DiscardPileComponent,
    PartyRosterComponent,
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
def get_gear_modifiers(entity: Entity) -> List[str]:
    """获取实体已装备道具的即时修正词缀；未装备任何道具则返回空列表。"""
    return (
        entity.get(EquippedGearComponent).item.modifiers
        if entity.has(EquippedGearComponent)
        else []
    )


#################################################################################################################################################
def get_gear_on_hit_affixes(entity: Entity) -> List[str]:
    """获取实体已装备道具的 on_hit_affixes（命中时生效的词缀）；未装备任何道具则返回空列表。"""
    return (
        entity.get(EquippedGearComponent).item.on_hit_affixes
        if entity.has(EquippedGearComponent)
        else []
    )


#################################################################################################################################################
def collect_target_gear_modifiers(
    game: DBGGame, target_names: Sequence[str]
) -> Dict[str, List[str]]:
    """按目标名去重保序收集目标已装备道具的即时修正词缀。"""
    target_gear_modifiers: Dict[str, List[str]] = {}
    for target_name in dict.fromkeys(target_names):
        target_entity = game.get_entity_by_name(target_name)
        assert target_entity is not None, f"无法找到目标实体: {target_name}"
        target_gear_modifiers[target_name] = get_gear_modifiers(target_entity)
    return target_gear_modifiers


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
def accumulate_status_effects_action(
    entity: Entity, affixes: List[AffixTrigger]
) -> None:
    """为实体追加 AddStatusEffectsAction，自动合并已有的 affixes。"""
    existing = (
        entity.get(AddStatusEffectsAction)
        if entity.has(AddStatusEffectsAction)
        else None
    )
    merged = (existing.affixes if existing is not None else []) + affixes
    entity.replace(AddStatusEffectsAction, entity.name, merged)


#################################################################################################################################################
def wrap_scene_hints_as_affixes(source: str, hints: List[str]) -> List[AffixTrigger]:
    """将场景/仒裁 LLM 自行判定生成的自由文本提示（已自带描述格式，如"[场景] ..."）
    包装为 AffixTrigger，以接入与卡牌/装备/消耗品词缀相同的唯一通道。

    这类提示本质上也是"延迟触发信号"，只是来源不是预先写在 Card/GearItem/ConsumableItem 上的
    静态词缀，而是 LLM 对当前叙事/交互的临时判断，因此 context 留空，affix 直接携带完整文本。
    """
    return [AffixTrigger(source=source, affix=hint) for hint in hints]


#################################################################################################################################################
def _format_zero_health_message() -> str:
    """生成 HP 归零时发送给角色的通知消息"""
    return "# 你的HP已归零，失去战斗能力！"


#################################################################################################################################################
def process_zero_health_entities(game: DBGGame) -> None:
    """为 HP 归零且尚未标记死亡的实体添加 DeathComponent。"""

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
def pick_spread_targets(camp_members: List[Entity], hit_count: int) -> List[Entity]:
    """按 hit_count 与候选阵营成员数量的关系，选取"散射"命中列表（SPREAD 专用）。"""
    if not camp_members:
        return []

    if hit_count > len(camp_members):
        assigned = list(camp_members) + random.choices(
            camp_members, k=hit_count - len(camp_members)
        )
        random.shuffle(assigned)
        return assigned

    return random.choices(camp_members, k=hit_count)


#################################################################################################################################################
def resolve_targets(
    target_type: TargetType,
    hit_count: int,
    actor_entity: Entity,
    passed_targets: List[str],
    dbg_game: DBGGame,
) -> tuple[List[str], str]:
    """根据 target_type 解析并验证目标。"""

    def _resolve_camp_from_anchor(label: str) -> tuple[List[Entity], str]:
        """校验 passed_targets 恰好 1 个锚点目标，并展开为该锚点所在阵营的全体存活角色。"""
        if len(passed_targets) != 1:
            return (
                [],
                f"{label} 目标数量必须为 1（作为阵营锚点），实际收到 {len(passed_targets)} 个",
            )
        alive_map = {
            e.name: e for e in get_alive_actors_in_stage(dbg_game, actor_entity)
        }
        anchor_name = passed_targets[0]
        anchor_entity = alive_map.get(anchor_name)
        if anchor_entity is None:
            return (
                [],
                f"目标 '{anchor_name}' 不在当前场景存活角色列表中: {sorted(alive_map)}",
            )
        if anchor_entity.has(PartyMemberComponent):
            return get_alive_party_members_in_stage(anchor_entity, dbg_game), ""
        if anchor_entity.has(MonsterComponent):
            return get_alive_monsters_in_stage(anchor_entity, dbg_game), ""
        return [], f"目标 '{anchor_name}' 不属于任何可识别阵营"

    match target_type:
        case TargetType.SINGLE:
            alive_names = {
                e.name for e in get_alive_actors_in_stage(dbg_game, actor_entity)
            }
            if len(passed_targets) != 1:
                return (
                    [],
                    f"SINGLE 目标数量必须为 1，实际收到 {len(passed_targets)} 个",
                )
            if passed_targets[0] not in alive_names:
                return (
                    [],
                    f"目标 '{passed_targets[0]}' 不在当前场景存活角色列表中: {sorted(alive_names)}",
                )
            return list(passed_targets), ""

        case TargetType.ALL:
            camp_members, err = _resolve_camp_from_anchor("ALL")
            if err:
                return [], err
            if not camp_members:
                return [], "ALL：锚点所在阵营当前无存活角色"
            return [e.name for e in camp_members], ""

        case TargetType.SPREAD:
            camp_members, err = _resolve_camp_from_anchor("SPREAD")
            if err:
                return [], err
            if not camp_members:
                return [], "SPREAD：锚点所在阵营当前无存活角色"
            return [e.name for e in pick_spread_targets(camp_members, hit_count)], ""

        case TargetType.SELF:
            return [actor_entity.name], ""


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


#######################################################################################################################################
def deduct_item_from_inventory(entity: Entity, item: ConsumableItem) -> bool:
    """从 InventoryComponent 扣减指定消耗品数量，耗尽则移除该条目。"""
    inventory_comp = entity.get(InventoryComponent)
    updated_items = []
    consumed = False

    # 遍历 InventoryComponent.items，找到匹配的 ConsumableItem 并扣减数量
    for inv_item in inventory_comp.items:
        if not consumed and inv_item.uuid == item.uuid:
            consumed = True
            if inv_item.count > 1:
                # 直接修改 count（MutableComponent 允许就地修改）
                inv_item.count -= 1
                updated_items.append(inv_item)
            # count == 1：不追加，即移除
        else:
            updated_items.append(inv_item)

    # 如果成功扣减，则更新 InventoryComponent.items
    if consumed:
        inventory_comp.items = updated_items

    # 返回是否成功扣减
    return consumed


#######################################################################################################################################
def clear_round_state(game: DBGGame) -> None:
    """清除所有角色实体的每回合可变状态（手牌归入弃牌堆 + 回合动态属性）"""

    # 清除所有角色实体的手牌组件，将剩余手牌归入 DiscardPile（STS 标准：回合末未出牌进弃牌堆）
    for entity in game.get_group(
        Matcher(all_of=[HandComponent, DiscardPileComponent])
    ).entities.copy():
        hand_comp = entity.get(HandComponent)
        discard_pile_comp = entity.get(DiscardPileComponent)

        if hand_comp.cards:
            # 仅归入来源为本角色的卡牌；外来塞入牌（source != actor_name）直接丢弃
            own_cards = [c for c in hand_comp.cards if c.source == entity.name]
            foreign_cards = [c for c in hand_comp.cards if c.source != entity.name]
            discard_pile_comp.cards.extend(own_cards)
            logger.debug(
                f"clear hands: {entity.name} 将 {len(own_cards)} 张剩余手牌归入 DiscardPile，DiscardPile 累计 {len(discard_pile_comp.cards)} 张"
            )
            for fc in foreign_cards:
                logger.debug(
                    f"clear hands: [{entity.name}] 外来牌 [{fc.name}](source={fc.source!r}) 回合结束，source 不匹配，丢弃"
                )
        else:
            logger.debug(f"clear hands: {entity.name}")

        # 移除 HandComponent
        entity.remove(HandComponent)

    # 清除所有角色实体的回合动态属性组件
    for entity in game.get_group(Matcher(RoundStatsComponent)).entities.copy():
        logger.debug(f"clear round stats: {entity.name}")
        entity.remove(RoundStatsComponent)


###################################################################################################################################################################
def clear_combat_state(dbg_game: DBGGame) -> None:
    """清除一次战斗（Combat）结束后的临时状态。"""

    # 清除战斗回合状态
    clear_round_state(dbg_game)

    # 清除所有角色的状态效果
    for entity in dbg_game.get_group(Matcher(StatusEffectsComponent)).entities.copy():
        logger.debug(f"clear status effects: {entity.name}")
        entity.remove(StatusEffectsComponent)

    # 移动语义：装备背包持有者始终是玩家实体，清除装备前必须先将其归还玩家的
    # InventoryComponent，否则装备会随组件一起被丢弃、凭空消失。
    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"
    assert player_entity.has(InventoryComponent), "玩家实体缺少 InventoryComponent"
    player_inventory = player_entity.get(InventoryComponent)

    # 清除所有角色的装备组件，装备物归还玩家背包
    for entity in dbg_game.get_group(Matcher(EquippedGearComponent)).entities.copy():
        equipped_item = entity.get(EquippedGearComponent).item
        player_inventory.items.append(equipped_item)
        entity.remove(EquippedGearComponent)
        logger.debug(
            f"clear equipped gear: {entity.name}，已将装备 {equipped_item.name!r} "
            f"归还玩家 {player_entity.name} 的 InventoryComponent"
        )


###################################################################################################################################################################
def select_party_members(dbg_game: DBGGame) -> Set[Entity]:
    """选择参与副本远征的队伍成员"""

    # 1. 获取玩家实体
    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "玩家实体不存在！"

    # 2. 默认仅玩家自己参与；若存在 PartyRosterComponent 则按名单加入盟友
    party_members: Set[Entity] = {player_entity}
    logger.info(f"玩家 {player_entity.name} 将参与远征")
    if player_entity.has(PartyRosterComponent):
        for member_name in player_entity.get(PartyRosterComponent).members:
            member_entity = dbg_game.get_actor_entity(member_name)
            assert (
                member_entity is not None
            ), f"远征队名单中的成员 {member_name!r} 不存在！"
            party_members.add(member_entity)
            logger.info(f"按名单将 {member_name} 加入远征队")

    # 打印最终选定的远征队成员名单
    logger.info(
        f"最终远征队成员 ({len(party_members)}): {[e.name for e in party_members]}"
    )

    # 3. 为所有选中成员挂载 PartyMemberComponent
    for party_member in party_members:
        party_member.replace(
            PartyMemberComponent,
            party_member.name,
        )
        logger.debug(
            f"将 {party_member.name} 添加 PartyMemberComponent 组件，标记为远征队成员"
        )

    return party_members
