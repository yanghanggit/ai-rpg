"""
地下城战斗动作模块
"""

from typing import List, Tuple, Optional
from loguru import logger
from ..game.dbg_game import DBGGame
from ..game.dbg_combat_processor import (
    find_equipped_gear_holder,
    get_alive_party_members_in_stage,
    get_alive_monsters_in_stage,
    get_energy,
    resolve_targets,
)
from ..models import (
    DrawCardsAction,
    HandComponent,
    PlayCardsAction,
    PassTurnAction,
    PartyMemberComponent,
    MonsterComponent,
    DeathComponent,
    RetreatAction,
    MonsterTurnAction,
    HandComponent,
    InventoryComponent,
    CombatLootComponent,
    UseGearItemAction,
    UseConsumableItemAction,
    GearItem,
    ConsumableItem,
    TargetType,
)
from ..entitas import Entity, Matcher


###################################################################################################################################################################
def activate_all_card_draws(
    dbg_game: DBGGame,
) -> Tuple[bool, str]:
    """
    为当前场景中所有存活的战斗角色（远征队成员 + 敌方）激活抽牌动作。
    """

    # 检查当前是否在玩家所在的地下城场景中
    if not dbg_game.is_player_in_dungeon_stage:
        error_msg = "只能在玩家所在的地下城场景中使用该操作"
        logger.error(error_msg)
        return False, error_msg

    # 检查当前地下城是否处于进行中的战斗状态
    if not dbg_game.current_combat_room.combat.is_ongoing:
        error_msg = "只能在战斗中使用is_ongoing"
        logger.error(error_msg)
        return False, error_msg

    # 获取玩家实体，作为锚点来定位当前场景中的所有存活战斗角色
    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "activate_all_card_draws: player_entity is None"

    # 获取当前场景中所有存活的战斗角色，包括远征队成员和怪物
    all_entities = get_alive_party_members_in_stage(
        player_entity, dbg_game
    ) + get_alive_monsters_in_stage(player_entity, dbg_game)

    # 如果当前场景中没有存活的战斗角色，则返回错误信息
    if len(all_entities) == 0:
        error_msg = "激活全员抽牌失败: 场景中没有存活的战斗角色"
        logger.error(error_msg)
        return False, error_msg

    # 为每个存活的战斗角色添加抽牌动作组件，如果该角色已经有抽牌动作组件，则会被新的组件覆盖
    for entity in all_entities:
        assert not entity.has(
            DrawCardsAction
        ), f"Entity {entity.name} already has DrawCardsAction, so will be overwritten by new DrawCardsAction"

        # 添加抽牌动作组件，组件的标识使用实体的名称
        entity.replace(DrawCardsAction, entity.name)

    return True, f"成功为 {len(all_entities)} 个战斗角色激活抽牌动作"


###################################################################################################################################################################
def _validate_play_turn(
    dbg_game: DBGGame,
    actor_name: str,
) -> Tuple[Optional[Entity], str]:
    """校验当前是否轮到指定角色出牌，并返回其实体。"""

    # 获取当前回合信息，检查是否存在进行中的回合，以及当前角色是否在行动快照中。
    latest_round = dbg_game.current_combat_room.combat.latest_round
    if latest_round is None:
        return None, "当前没有进行中的回合"

    # 获取当前回合的行动顺序，确保该角色在其中，以验证其是否有资格出牌。
    action_order = latest_round.action_order

    # 检查该角色是否在当前回合的行动顺序中，如果不在，则说明该角色没有资格出牌。
    if actor_name not in action_order:
        return (
            None,
            f"角色 {actor_name} 不在本回合行动顺序中: {action_order}",
        )

    # 检查当前回合的行动顺序，确保该角色是当前应出牌的角色。
    next_actor = latest_round.current_actor
    if next_actor != actor_name:
        return None, f"现在不是 {actor_name} 的回合，当前应由 {next_actor} 出牌"

    # 获取该角色的实体，确保其存在，并且是战斗角色（PartyMember 或 Monster），且未死亡且拥有手牌组件。
    entity = dbg_game.get_actor_entity(actor_name)
    assert entity is not None, f"找不到角色 {actor_name}"
    assert entity.has(PartyMemberComponent) or entity.has(
        MonsterComponent
    ), f"角色 {actor_name} 不是战斗角色（非 PartyMember 或 Monster）"

    # 检查该角色是否已死亡，如果已死亡则无法出牌。
    if entity.has(DeathComponent):
        return None, f"角色 {actor_name} 已死亡，无法出牌"

    # 检查该角色是否拥有手牌组件，如果没有则无法出牌。
    if not entity.has(HandComponent):
        return None, f"角色 {actor_name} 没有 HandComponent"

    return entity, ""


###################################################################################################################################################################
async def activate_play_cards_specified(
    dbg_game: DBGGame,
    actor_name: str,
    card_name: str,
    targets: List[str],
) -> Tuple[bool, str]:
    """
    让指定远征队员打出指定名称的手牌。
    """

    # 检查当前是否在远征阶段，如果不在则无法出牌。
    if not dbg_game.is_player_in_dungeon_stage:
        msg = "当前不在远征阶段，无法出牌"
        logger.error(msg)
        return False, msg

    # 校验当前是否轮到该角色出牌，并获取其实体。如果不符合出牌条件，则返回错误信息。
    entity, error_msg = _validate_play_turn(dbg_game, actor_name)
    if entity is None:
        logger.error(f"activate_play_cards_specified: {error_msg}")
        return False, error_msg

    assert entity.has(PartyMemberComponent), f"角色 {actor_name} 不是远征队员"

    # 获取角色的手牌组件，并尝试在手牌中找到指定名称的卡牌。
    hand_comp = entity.get(HandComponent)
    selected_card = next((c for c in hand_comp.cards if c.name == card_name), None)
    if selected_card is None:
        msg = f"角色 {actor_name} 手牌中找不到卡牌 '{card_name}'，当前手牌: {[c.name for c in hand_comp.cards]}"
        logger.error(msg)
        return False, msg

    # 检查所选卡牌是否可出牌，如果不可出牌则返回错误信息。
    if not selected_card.playable:
        return False, "该卡牌不可出牌"

    # 检查角色当前 energy 是否足以支付卡牌费用，不足则禁止出牌。
    current_energy = get_energy(entity)
    if current_energy < selected_card.cost:
        return (
            False,
            f"能量不足，无法出牌『{card_name}』（需要{selected_card.cost}点，当前剩余{current_energy}点）",
        )

    # 解析卡牌的目标，根据卡牌的目标类型和命中次数，结合玩家提供的目标名称列表，解析出实际的目标实体列表。
    resolved_targets, resolve_err = resolve_targets(
        selected_card.target_type, selected_card.hit_count, entity, targets, dbg_game
    )
    if resolve_err:
        logger.error(f"activate_play_cards_specified: {resolve_err}")
        return False, resolve_err

    logger.debug(
        f"为角色 {actor_name} 激活出牌动作，卡牌: {selected_card.name} 目标: {resolved_targets}"
    )

    # 将出牌动作添加到实体中，PlayCardsAction 组件会被系统监听并处理实际的出牌逻辑。
    entity.replace(
        PlayCardsAction,
        entity.name,
        selected_card,
        resolved_targets,
    )

    # 返回成功信息，表示已经成功为角色激活了出牌动作。
    return True, f"成功为角色 {actor_name} 激活出牌动作（卡牌: {card_name}）"


###################################################################################################################################################################
def activate_monster_play_trigger(
    dbg_game: DBGGame,
    actor_name: str,
) -> Tuple[bool, str]:
    """
    触发指定怪物的出牌决策流程。
    """

    # 检查当前是否处于玩家的地下城阶段，如果不是则无法触发怪物的出牌决策。
    if not dbg_game.is_player_in_dungeon_stage:
        error_msg = "激活怪物出牌触发失败: 当前不在玩家的地下城阶段"
        logger.error(error_msg)
        return False, error_msg

    entity, error_msg = _validate_play_turn(dbg_game, actor_name)
    if entity is None:
        logger.error(f"activate_monster_play_trigger: {error_msg}")
        return False, error_msg

    assert entity.has(MonsterComponent), f"角色 {actor_name} 不是怪物"
    logger.debug(f"为怪物 {actor_name} 触发出牌决策，由 MonsterPrePlaySystem 自动选牌")

    # 添加 MonsterTurnAction 标记，触发 MonsterPrePlaySystem 的决策流程
    entity.replace(MonsterTurnAction, entity.name)

    return True, f"成功为怪物 {actor_name} 触发出牌决策"


###################################################################################################################################################################
def activate_retreat(
    dbg_game: DBGGame,
) -> Tuple[bool, str]:
    """
    为所有远征队成员激活撤退动作。
    """

    # 检查当前是否处于玩家的地下城阶段，如果不是则无法激活撤退动作。
    if not dbg_game.is_player_in_dungeon_stage:
        error_msg = "激活撤退动作失败: 当前不在玩家的地下城阶段"
        logger.error(error_msg)
        return False, error_msg

    # 检查当前地下城是否处于进行中状态，如果不是则无法激活撤退动作。
    if not dbg_game.current_combat_room.combat.is_ongoing:
        error_msg = "激活撤退动作失败: 只能在战斗进行中使用"
        logger.error(error_msg)
        return False, error_msg

    # 获取当前地下城中所有远征队成员实体，用于为他们添加撤退动作组件。
    party_member_entities = dbg_game.get_group(
        Matcher(all_of=[PartyMemberComponent])
    ).entities
    assert (
        len(party_member_entities) > 0
    ), "激活撤退动作失败: 没有找到远征队成员, 至少有一个player"

    # 为每个远征队成员添加撤退动作组件
    for party_member_entity in party_member_entities:
        assert party_member_entity.has(
            PartyMemberComponent
        ), f"Entity {party_member_entity.name} must have PartyMemberComponent"

        # 为每个远征队成员添加撤退动作组件，触发 RetreatActionSystem 的处理逻辑
        party_member_entity.replace(
            RetreatAction,
            party_member_entity.name,
        )
        logger.debug(f"为角色 {party_member_entity.name} 添加撤退动作组件")

    return (
        True,
        f"成功为 {len(party_member_entities)} 个远征队成员激活撤退动作",
    )


###################################################################################################################################################################
def activate_use_consumable(
    dbg_game: DBGGame,
    item_name: str,
    targets: List[str],
) -> Tuple[bool, str]:
    """使用队伍背包内的指定消耗品。"""

    # 检查玩家是否在地下城阶段，如果不是则无法使用消耗品。
    if not dbg_game.is_player_in_dungeon_stage:
        msg = "使用消耗品失败：玩家不在地下城场景中"
        logger.error(msg)
        return False, msg

    # 检查当前地下城是否处于进行中状态，如果不是则无法使用消耗品。
    if not dbg_game.current_combat_room.combat.is_ongoing:
        msg = "使用消耗品失败：战斗未在进行中"
        logger.error(msg)
        return False, msg

    # 获取当前地下城的最新回合，如果没有进行中的回合，则无法使用消耗品。
    latest_round = dbg_game.current_combat_room.combat.latest_round
    if latest_round is None:
        msg = "使用消耗品失败：当前没有进行中的回合"
        logger.error(msg)
        return False, msg

    # 检查当前回合的抽牌阶段是否已完成，如果尚未完成，则无法使用消耗品。
    if not latest_round.draw_completed:
        msg = "使用消耗品失败：抽牌阶段尚未完成"
        logger.error(msg)
        return False, msg

    # 检查当前回合的行动者是否存在，如果不存在则无法使用消耗品。
    current_turn_actor_name = latest_round.current_actor
    if current_turn_actor_name is None:
        msg = "使用消耗品失败：当前没有行动角色"
        logger.error(msg)
        return False, msg

    # 获取玩家实体，并确保其具有必要的组件（PartyMemberComponent 和 InventoryComponent），以便使用消耗品。
    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "activate_use_consumable: player_entity is None"
    assert player_entity.has(PartyMemberComponent), "玩家实体缺少 PartyMemberComponent"
    assert player_entity.has(InventoryComponent), "玩家实体缺少 InventoryComponent"

    # 只有背包持有者本人是当前行动者时，才允许发起消耗品使用。
    current_turn_entity = dbg_game.get_actor_entity(current_turn_actor_name)
    if current_turn_entity is None or current_turn_actor_name != player_entity.name:
        msg = f"使用消耗品失败：当前行动角色 {current_turn_actor_name} 不是背包持有者 {player_entity.name}"
        logger.error(msg)
        return False, msg

    # 从玩家实体中获取背包组件，并尝试在背包中找到指定的消耗品，如果找不到则返回错误。
    inventory_comp = player_entity.get(InventoryComponent)
    selected_item = next((i for i in inventory_comp.items if i.name == item_name), None)
    if selected_item is None:
        msg = (
            f"玩家背包中找不到消耗品 '{item_name}'，"
            f"当前背包: {[i.name for i in inventory_comp.items]}"
        )
        logger.error(msg)
        return False, msg

    # 检查选中的物品是否为消耗品，如果不是则无法使用。
    if not isinstance(selected_item, ConsumableItem):
        msg = f"物品 '{item_name}' 不是消耗品（类型: {type(selected_item).__name__}）"
        logger.error(msg)
        return False, msg

    # 解析消耗品的目标，根据消耗品的目标类型、数量和玩家实体，结合传入的目标列表，确定最终的目标实体列表。如果解析失败，则返回错误。
    resolved_targets, resolve_err = resolve_targets(
        selected_item.target_type, 1, player_entity, targets, dbg_game
    )
    if resolve_err:
        logger.error(f"activate_use_consumable: {resolve_err}")
        return False, resolve_err

    logger.debug(
        f"为玩家 {player_entity.name} 激活消耗品使用，物品: {selected_item.name} 目标: {resolved_targets}"
    )

    # 将使用消耗品的动作挂在玩家实体上，记录玩家、消耗品和目标实体列表，以便在游戏逻辑中处理实际的消耗品使用效果。
    player_entity.replace(
        UseConsumableItemAction,
        player_entity.name,
        selected_item,
        resolved_targets,
    )

    # 返回成功消息，表示已成功激活消耗品的使用。
    return True, f"成功激活消耗品使用（物品: {item_name}）"


###################################################################################################################################################################
def activate_use_gear(
    dbg_game: DBGGame,
    item_name: str,
    targets: List[str],
) -> Tuple[bool, str]:
    """使用队伍背包内的指定装备。装备是队伍级别的行为."""

    # 检查玩家是否在地下城场景中，如果不在则无法使用装备。
    if not dbg_game.is_player_in_dungeon_stage:
        msg = "使用装备失败：玩家不在地下城场景中"
        logger.error(msg)
        return False, msg

    # 检查当前地下城是否处于进行中状态，如果不是则无法使用装备。
    if not dbg_game.current_combat_room.combat.is_ongoing:
        msg = "使用装备失败：战斗未在进行中"
        logger.error(msg)
        return False, msg

    # 获取当前地下城的最新回合，如果没有进行中的回合，则无法使用装备。
    latest_round = dbg_game.current_combat_room.combat.latest_round
    if latest_round is None:
        msg = "使用装备失败：当前没有进行中的回合"
        logger.error(msg)
        return False, msg

    # 检查当前回合的抽牌阶段是否已完成，如果尚未完成，则无法使用装备。
    if not latest_round.draw_completed:
        msg = "使用装备失败：抽牌阶段尚未完成"
        logger.error(msg)
        return False, msg

    # 获取当前回合的行动者名称，如果没有行动者，则无法使用装备。
    current_turn_actor_name = latest_round.current_actor
    if current_turn_actor_name is None:
        msg = "使用装备失败：当前没有行动角色"
        logger.error(msg)
        return False, msg

    # 获取玩家实体，并确保其具有必要的组件（PartyMemberComponent 和 InventoryComponent），以便使用装备。
    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "activate_use_gear: player_entity is None"
    assert player_entity.has(PartyMemberComponent), "玩家实体缺少 PartyMemberComponent"
    assert player_entity.has(InventoryComponent), "玩家实体缺少 InventoryComponent"

    # 只有背包持有者本人是当前行动者时，才允许发动装备使用。
    if current_turn_actor_name != player_entity.name:
        msg = f"使用装备失败：当前行动角色 {current_turn_actor_name} 不是背包持有者 {player_entity.name}"
        logger.error(msg)
        return False, msg

    # 从玩家实体中获取背包组件，并尝试在背包中找到指定的装备，如果找不到则返回错误。
    inventory_comp = player_entity.get(InventoryComponent)
    selected_item = next((i for i in inventory_comp.items if i.name == item_name), None)
    if selected_item is None:
        msg = (
            f"玩家背包中找不到装备 '{item_name}'，"
            f"当前背包: {[i.name for i in inventory_comp.items]}"
        )
        logger.error(msg)
        return False, msg

    # 检查选中的物品是否为装备，如果不是则无法使用。
    if not isinstance(selected_item, GearItem):
        msg = f"物品 '{item_name}' 不是装备（类型: {type(selected_item).__name__}）"
        logger.error(msg)
        return False, msg

    # 检查该装备是否已经被其他实体装备，如果已被装备则无法再次使用。
    holder = find_equipped_gear_holder(dbg_game, selected_item)
    if holder is not None:
        msg = f"装备 '{item_name}' 当前已被 {holder.name} 装备中，无法再次使用"
        logger.error(msg)
        return False, msg

    # 装备固定作用于单一友方目标，确保目标数量和阵营符合装备要求。
    resolved_targets, resolve_err = resolve_targets(
        TargetType.ALLY_SINGLE, 1, player_entity, targets, dbg_game
    )
    if resolve_err:
        logger.error(f"activate_use_gear: {resolve_err}")
        return False, resolve_err

    # 检查解析后的目标数量是否符合装备的要求，如果不是单目标装备则返回错误。
    if len(resolved_targets) != 1:
        msg = f"装备使用要求单目标，解析结果为 {resolved_targets}"
        logger.error(msg)
        return False, msg

    # 获取目标实体，并检查其当前回合剩余能量，如果能量不足则无法为其装备。
    target_entity = dbg_game.get_entity_by_name(resolved_targets[0])
    assert (
        target_entity is not None
    ), f"activate_use_gear: 无法找到目标实体 {resolved_targets[0]}"

    # 检查目标实体的当前能量是否足以支付装备的消耗，如果不足则返回错误。
    current_energy = get_energy(target_entity)
    if current_energy < selected_item.cost:
        msg = f"目标 '{target_entity.name}' 当前能量不足（需要{selected_item.cost}点，当前剩余{current_energy}点），无法为其装备"
        logger.error(msg)
        return False, msg

    logger.debug(
        f"为玩家 {player_entity.name} 激活装备使用，物品: {selected_item.name} 目标: {resolved_targets}"
    )

    # 将装备使用动作挂载到玩家实体上，以便在游戏逻辑中处理该动作。
    player_entity.replace(
        UseGearItemAction,
        player_entity.name,
        selected_item,
        resolved_targets,
    )

    # 返回成功消息，表示装备使用动作已成功激活。
    return True, f"成功激活装备使用（物品: {item_name}）"


###################################################################################################################################################################
def activate_pass_turn(
    dbg_game: DBGGame,
    actor_name: str,
) -> Tuple[bool, str]:
    """让指定战斗角色跳过本次出牌机会（过牌），消耗 1 点 energy。"""

    # 检查玩家是否在地下城场景中，如果不在则无法执行过牌动作。
    if not dbg_game.is_player_in_dungeon_stage:
        msg = "过牌失败：玩家不在地下城场景中"
        logger.error(msg)
        return False, msg

    # 验证当前回合是否允许该角色进行操作，包括是否存在该角色以及是否轮到该角色出牌。
    entity, error_msg = _validate_play_turn(dbg_game, actor_name)
    if entity is None:
        logger.error(f"activate_pass_turn: {error_msg}")
        return False, error_msg

    # 激活过牌动作，将 PassTurnAction 挂载到角色实体上，以便在游戏逻辑中处理该动作。
    logger.debug(f"为角色 {actor_name} 激活过牌动作")
    entity.replace(PassTurnAction, entity.name)
    return True, f"成功为角色 {actor_name} 激活过牌动作"


###################################################################################################################################################################
def collect_combat_loot(
    dbg_game: DBGGame,
) -> Tuple[bool, str]:
    """将战斗战利品背包（CombatLootComponent）中的道具全部转入玩家随身背包（InventoryComponent）。"""

    # 检查玩家是否在地下城场景中，如果不在则无法收取战利品。
    if not dbg_game.is_player_in_dungeon_stage:
        msg = "收取战利品失败：玩家不在地下城场景中"
        logger.error(msg)
        return False, msg

    # 获取玩家实体，并确保其存在。
    player_entity = dbg_game.get_player_entity()
    assert player_entity is not None, "无法获取玩家实体"

    # 检查玩家实体是否拥有战斗战利品组件，如果没有则无法收取战利品。
    if not player_entity.has(CombatLootComponent):
        msg = (
            "收取战利品失败：玩家身上没有 CombatLootComponent（本场战斗无掉落或已收取）"
        )
        logger.warning(msg)
        return False, msg

    assert player_entity.has(InventoryComponent), "玩家实体缺少 InventoryComponent"

    # 获取战斗战利品组件中的道具列表，以便将其合并到玩家的背包中。
    loot_comp = player_entity.get(CombatLootComponent)
    loot_items = loot_comp.items

    inventory_comp = player_entity.get(InventoryComponent)
    new_inventory = list(inventory_comp.items) + loot_items

    player_entity.replace(InventoryComponent, inventory_comp.name, new_inventory)
    player_entity.remove(CombatLootComponent)

    logger.info(
        f"[collect_combat_loot] 收取战利品 {len(loot_items)} 件，"
        f"背包现有 {len(new_inventory)} 件道具"
    )
    return True, f"成功收取 {len(loot_items)} 件战利品到背包"
