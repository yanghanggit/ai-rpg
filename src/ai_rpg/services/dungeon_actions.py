"""
地下城战斗动作模块

提供战斗回合中的动作激活函数，包括抽牌和打牌等核心战斗行为。
这些函数通过添加动作组件来驱动战斗流程，由 combat_pipeline 负责执行。
"""

import random
from typing import List, Tuple
from loguru import logger
from ..game.tcg_game import TCGGame
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
    Card,
    TargetType,
    HandComponent,
    InventoryComponent,
    UseConsumableItemAction,
)
from ..entitas import Entity, Matcher


###################################################################################################################################################################
def _get_alive_party_members_in_stage(
    anchor_entity: Entity, tcg_game: TCGGame
) -> List[Entity]:
    """获取锚点实体所在场景中所有存活的远征队成员

    以 anchor_entity 定位其所在场景，然后在该场景中筛选所有带
    PartyMemberComponent 的存活实体。玩家实体是常用的锚点，
    但任意处于场景中的实体均可作为 anchor。

    Args:
        anchor_entity: 用于定位场景的锚点实体
        tcg_game: TCG游戏实例

    Returns:
        存活的远征队成员实体列表
    """
    actor_entities = tcg_game.get_alive_actors_in_stage(anchor_entity)
    return [entity for entity in actor_entities if entity.has(PartyMemberComponent)]


###################################################################################################################################################################
def _get_alive_monsters_in_stage(
    anchor_entity: Entity, tcg_game: TCGGame
) -> List[Entity]:
    """获取锚点实体所在场景中所有存活的怪物

    以 anchor_entity 定位其所在场景，然后在该场景中筛选所有带
    MonsterComponent 的存活实体。

    Args:
        anchor_entity: 用于定位场景的锚点实体
        tcg_game: TCG游戏实例

    Returns:
        存活的怪物实体列表
    """
    actor_entities = tcg_game.get_alive_actors_in_stage(anchor_entity)
    return [entity for entity in actor_entities if entity.has(MonsterComponent)]


###################################################################################################################################################################
def activate_all_card_draws(
    tcg_game: TCGGame,
) -> Tuple[bool, str]:
    """
    为当前场景中所有存活的战斗角色（远征队成员 + 敌方）激活抽牌动作。

    Args:
        tcg_game: TCG游戏实例

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """

    if not tcg_game.current_dungeon.is_ongoing:
        return False, "只能在战斗中使用is_ongoing"

    player_entity = tcg_game.get_player_entity()
    assert player_entity is not None, "activate_all_card_draws: player_entity is None"

    all_entities = _get_alive_party_members_in_stage(
        player_entity, tcg_game
    ) + _get_alive_monsters_in_stage(player_entity, tcg_game)

    if len(all_entities) == 0:
        error_msg = "激活全员抽牌失败: 场景中没有存活的战斗角色"
        logger.error(error_msg)
        return False, error_msg

    for entity in all_entities:
        assert not entity.has(
            DrawCardsAction
        ), f"Entity {entity.name} already has DrawCardsAction, so will be overwritten by new DrawCardsAction"

        # 添加。
        entity.replace(DrawCardsAction, entity.name)

    return True, f"成功为 {len(all_entities)} 个战斗角色激活抽牌动作"


###################################################################################################################################################################
def _resolve_targets(
    target_type: TargetType,
    hit_count: int,
    actor_entity: Entity,
    passed_targets: List[str],
    tcg_game: TCGGame,
) -> Tuple[List[str], str]:
    """根据 target_type 解析并验证目标。

    actor_entity 是 PartyMemberComponent 时，"敌方"为 MonsterComponent，"我方"为 PartyMemberComponent。
    actor_entity 是 MonsterComponent 时，"敌方"为 PartyMemberComponent，"我方"为 MonsterComponent。

    Returns:
        (resolved_targets, error_msg): error_msg 为空字符串表示成功。
    """
    is_actor_ally = actor_entity.has(PartyMemberComponent)

    def _get_enemies() -> List[Entity]:
        return (
            _get_alive_monsters_in_stage(actor_entity, tcg_game)
            if is_actor_ally
            else _get_alive_party_members_in_stage(actor_entity, tcg_game)
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

        case TargetType.ENEMY_RANDOM_MULTI:
            enemies = _get_enemies()
            if not enemies:
                return [], "ENEMY_RANDOM_MULTI：场上无存活敌方"
            return [e.name for e in random.choices(enemies, k=hit_count)], ""

        case TargetType.SELF_ONLY:
            return [actor_entity.name], ""

        case _:  # ALLY_SINGLE / ALLY_ALL — 不限制目标
            return list(passed_targets), ""


###################################################################################################################################################################
def _validate_play_turn(
    tcg_game: TCGGame,
    actor_name: str,
) -> Tuple["Entity | None", str]:
    """校验当前是否轮到指定角色出牌，并返回其实体。

    Returns:
        (entity, "") 校验通过；(None, error_msg) 校验失败。
    """
    latest_round = tcg_game.current_dungeon.latest_round
    if latest_round is None:
        return None, "当前没有进行中的回合"

    current_snapshot = (
        latest_round.actor_order_snapshots[-1]
        if latest_round.actor_order_snapshots
        else []
    )
    if actor_name not in current_snapshot:
        return (
            None,
            f"角色 {actor_name} 不在本回合行动快照中: {current_snapshot}",
        )

    next_actor = latest_round.current_turn_actor_name
    if next_actor != actor_name:
        return None, f"现在不是 {actor_name} 的回合，当前应由 {next_actor} 出牌"

    entity = tcg_game.get_actor_entity(actor_name)
    if entity is None:
        return None, f"找不到角色 {actor_name}"

    if not (entity.has(PartyMemberComponent) or entity.has(MonsterComponent)):
        return None, f"角色 {actor_name} 不是战斗角色（非 PartyMember 或 Monster）"

    if entity.has(DeathComponent):
        return None, f"角色 {actor_name} 已死亡，无法出牌"

    if not entity.has(HandComponent):
        return None, f"角色 {actor_name} 没有 HandComponent"

    return entity, ""


###################################################################################################################################################################
def _validate_actor_turn(
    tcg_game: TCGGame,
    actor_name: str,
) -> Tuple["Entity | None", str]:
    """校验当前是否轮到指定角色行动，并返回其实体。

    与 _validate_play_turn 相同，但不要求角色持有 HandComponent。
    适用于消耗品等不依赖手牌的行动。

    Returns:
        (entity, "") 校验通过；(None, error_msg) 校验失败。
    """
    latest_round = tcg_game.current_dungeon.latest_round
    if latest_round is None:
        return None, "当前没有进行中的回合"

    current_snapshot = (
        latest_round.actor_order_snapshots[-1]
        if latest_round.actor_order_snapshots
        else []
    )
    if actor_name not in current_snapshot:
        return (
            None,
            f"角色 {actor_name} 不在本回合行动快照中: {current_snapshot}",
        )

    next_actor = latest_round.current_turn_actor_name
    if next_actor != actor_name:
        return None, f"现在不是 {actor_name} 的回合，当前应由 {next_actor} 出牌"

    entity = tcg_game.get_actor_entity(actor_name)
    if entity is None:
        return None, f"找不到角色 {actor_name}"

    if not (entity.has(PartyMemberComponent) or entity.has(MonsterComponent)):
        return None, f"角色 {actor_name} 不是战斗角色（非 PartyMember 或 Monster）"

    if entity.has(DeathComponent):
        return None, f"角色 {actor_name} 已死亡，无法行动"

    return entity, ""


###################################################################################################################################################################
async def activate_play_cards_specified(
    tcg_game: TCGGame,
    actor_name: str,
    card_name: str,
    targets: List[str],
    action: str = "",
) -> Tuple[bool, str]:
    """
    让指定远征队员打出指定名称的手牌。仅适用于 PartyMemberComponent 角色。
    敌人出牌请使用 activate_monster_play_trigger。

    Args:
        tcg_game: TCG游戏实例
        actor_name: 出牌角色的全名（如 角色.旅行者.无名氏）
        card_name: 要打出的卡牌名称（须存在于该角色手牌中）
        targets: 目标名称列表，可为 []
        action: 出牌时的第一人称叙事；默认为空字符串，仲裁 agent 将自行演绎

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """
    entity, error_msg = _validate_play_turn(tcg_game, actor_name)
    if entity is None:
        logger.error(f"activate_play_cards_specified: {error_msg}")
        return False, error_msg

    if not entity.has(PartyMemberComponent):
        msg = f"角色 {actor_name} 不是远征队员，怪物出牌请使用 activate_monster_play_trigger"
        logger.error(msg)
        return False, msg

    hand_comp = entity.get(HandComponent)
    selected_card = next((c for c in hand_comp.cards if c.name == card_name), None)
    if selected_card is None:
        msg = f"角色 {actor_name} 手牌中找不到卡牌 '{card_name}'，当前手牌: {[c.name for c in hand_comp.cards]}"
        logger.error(msg)
        return False, msg

    if not selected_card.playable:
        return False, "该卡牌不可出牌"

    resolved_targets, resolve_err = _resolve_targets(
        selected_card.target_type, selected_card.hit_count, entity, targets, tcg_game
    )
    if resolve_err:
        logger.error(f"activate_play_cards_specified: {resolve_err}")
        return False, resolve_err

    logger.debug(
        f"为角色 {actor_name} 激活出牌动作，卡牌: {selected_card.name} 目标: {resolved_targets}"
    )
    entity.replace(
        PlayCardsAction,
        entity.name,
        selected_card,
        resolved_targets,
        action,
    )
    return True, f"成功为角色 {actor_name} 激活出牌动作（卡牌: {card_name}）"


###################################################################################################################################################################
def activate_monster_play_trigger(
    tcg_game: TCGGame,
    actor_name: str,
) -> Tuple[bool, str]:
    """
    触发指定怪物的出牌决策流程。仅适用于 MonsterComponent 角色。
    玩家出牌请使用 activate_play_cards_specified。

    同时设置两个组件：
    - PlayCardsAction：空卡占位，MonsterPrePlaySystem 在 pipeline 中自动选牌并替换为真实卡牌与目标。
    - MonsterTurnAction：明确标记这是怪物回合，MonsterPrePlaySystem 同时监听两者以触发决策。

    Args:
        tcg_game: TCG游戏实例
        actor_name: 怪物角色的全名

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """
    entity, error_msg = _validate_play_turn(tcg_game, actor_name)
    if entity is None:
        logger.error(f"activate_monster_play_trigger: {error_msg}")
        return False, error_msg

    if not entity.has(MonsterComponent):
        msg = f"角色 {actor_name} 不是怪物，远征队员出牌请使用 activate_play_cards_specified"
        logger.error(msg)
        return False, msg

    logger.debug(f"为怪物 {actor_name} 触发出牌决策，由 MonsterPrePlaySystem 自动选牌")

    # 使用空卡占位，真正的卡牌和目标由 MonsterPrePlaySystem 在 pipeline 中自动替换
    entity.replace(PlayCardsAction, entity.name, Card(name="", description=""), [], "")

    # 核心标记：添加 MonsterTurnAction 组件，触发 MonsterPrePlaySystem 的决策流程
    entity.replace(MonsterTurnAction, entity.name)

    return True, f"成功为怪物 {actor_name} 触发出牌决策"


###################################################################################################################################################################
def activate_retreat(
    tcg_game: TCGGame,
) -> Tuple[bool, str]:
    """
    为所有远征队成员激活撤退动作。

    为每个远征队成员添加 RetreatAction 组件，由 RetreatActionSystem 响应处理。
    要求当前处于战斗进行中（is_ongoing）状态。

    这是符合 ECS 响应式架构的新实现方式，替代直接操作的 mark_retreat。
    撤退处理流程：
    1. 本函数添加 RetreatAction 组件
    2. RetreatActionSystem 响应并标记死亡、添加叙事消息
    3. CombatOutcomeSystem 检测死亡并触发战斗失败流程

    Args:
        tcg_game: TCG游戏实例

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """

    if not tcg_game.current_dungeon.is_ongoing:
        error_msg = "激活撤退动作失败: 只能在战斗进行中使用"
        logger.error(error_msg)
        return False, error_msg

    party_member_entities = tcg_game.get_group(
        Matcher(all_of=[PartyMemberComponent])
    ).entities

    if len(party_member_entities) == 0:
        error_msg = "激活撤退动作失败: 没有找到远征队成员"
        logger.error(error_msg)
        return False, error_msg

    # 为每个远征队成员添加撤退动作组件
    for party_member_entity in party_member_entities:
        assert party_member_entity.has(
            PartyMemberComponent
        ), f"Entity {party_member_entity.name} must have PartyMemberComponent"

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
    tcg_game: TCGGame,
    actor_name: str,
    item_name: str,
    targets: List[str],
) -> Tuple[bool, str]:
    """让指定远征队员使用背包内的指定消耗品。仅适用于 PartyMemberComponent 角色。

    使用消耗品不消耗 energy，可在玩家行动阶段内任意次数使用。

    Args:
        tcg_game: TCG游戏实例
        actor_name: 使用消耗品的角色全名
        item_name: 要使用的消耗品名称（须存在于该角色 InventoryComponent 中）
        targets: 目标名称列表，可为 []；target_type 为 SELF_ONLY / ENEMY_ALL 时系统自动覆盖

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """
    entity, error_msg = _validate_actor_turn(tcg_game, actor_name)
    if entity is None:
        logger.error(f"activate_use_consumable: {error_msg}")
        return False, error_msg

    if not entity.has(PartyMemberComponent):
        msg = f"角色 {actor_name} 不是远征队员，怪物无法使用消耗品"
        logger.error(msg)
        return False, msg

    if not entity.has(InventoryComponent):
        msg = f"角色 {actor_name} 没有 InventoryComponent"
        logger.error(msg)
        return False, msg

    inventory_comp = entity.get(InventoryComponent)
    selected_item = next((i for i in inventory_comp.items if i.name == item_name), None)
    if selected_item is None:
        msg = (
            f"角色 {actor_name} 背包中找不到消耗品 '{item_name}'，"
            f"当前背包: {[i.name for i in inventory_comp.items]}"
        )
        logger.error(msg)
        return False, msg

    from ..models import ConsumableItem as _ConsumableItem

    if not isinstance(selected_item, _ConsumableItem):
        msg = f"物品 '{item_name}' 不是消耗品（类型: {type(selected_item).__name__}）"
        logger.error(msg)
        return False, msg

    resolved_targets, resolve_err = _resolve_targets(
        selected_item.target_type, 1, entity, targets, tcg_game
    )
    if resolve_err:
        logger.error(f"activate_use_consumable: {resolve_err}")
        return False, resolve_err

    logger.debug(
        f"为角色 {actor_name} 激活消耗品使用，物品: {selected_item.name} 目标: {resolved_targets}"
    )
    entity.replace(
        UseConsumableItemAction,
        entity.name,
        selected_item,
        resolved_targets,
    )
    return True, f"成功为角色 {actor_name} 激活消耗品使用（物品: {item_name}）"


###################################################################################################################################################################
def activate_pass_turn(
    tcg_game: TCGGame,
    actor_name: str,
) -> Tuple[bool, str]:
    """让指定战斗角色跳过本次出牌机会（过牌），消耗 1 点 energy。

    Args:
        tcg_game: TCG游戏实例
        actor_name: 过牌角色的全名

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """
    entity, error_msg = _validate_play_turn(tcg_game, actor_name)
    if entity is None:
        logger.error(f"activate_pass_turn: {error_msg}")
        return False, error_msg

    logger.debug(f"为角色 {actor_name} 激活过牌动作")
    entity.replace(PassTurnAction, entity.name)
    return True, f"成功为角色 {actor_name} 激活过牌动作"
