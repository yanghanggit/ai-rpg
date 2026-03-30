"""
地下城战斗动作模块

提供战斗回合中的动作激活函数，包括抽牌和打牌等核心战斗行为。
这些函数通过添加动作组件来驱动战斗流程，由 combat_pipeline 负责执行。
"""

from typing import List, Tuple
from loguru import logger
from ..game.tcg_game import TCGGame
from ..models import (
    DrawCardsAction,
    HandComponent,
    PlayCardsAction,
    ExpeditionMemberComponent,
    EnemyComponent,
    DeathComponent,
    RetreatAction,
)
from ..entitas import Entity, Matcher


###################################################################################################################################################################
def _get_alive_expedition_members_in_stage(
    anchor_entity: Entity, tcg_game: TCGGame
) -> List[Entity]:
    """获取锚点实体所在场景中所有存活的远征队成员

    以 anchor_entity 定位其所在场景，然后在该场景中筛选所有带
    ExpeditionMemberComponent 的存活实体。玩家实体是常用的锚点，
    但任意处于场景中的实体均可作为 anchor。

    Args:
        anchor_entity: 用于定位场景的锚点实体
        tcg_game: TCG游戏实例

    Returns:
        存活的远征队成员实体列表
    """
    actor_entities = tcg_game.get_alive_actors_in_stage(anchor_entity)
    return [
        entity for entity in actor_entities if entity.has(ExpeditionMemberComponent)
    ]


###################################################################################################################################################################
def _get_alive_enemies_in_stage(
    anchor_entity: Entity, tcg_game: TCGGame
) -> List[Entity]:
    """获取锚点实体所在场景中所有存活的敌方

    以 anchor_entity 定位其所在场景，然后在该场景中筛选所有带
    EnemyComponent 的存活实体。

    Args:
        anchor_entity: 用于定位场景的锚点实体
        tcg_game: TCG游戏实例

    Returns:
        存活的敌方实体列表
    """
    actor_entities = tcg_game.get_alive_actors_in_stage(anchor_entity)
    return [entity for entity in actor_entities if entity.has(EnemyComponent)]


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

    all_entities = _get_alive_expedition_members_in_stage(
        player_entity, tcg_game
    ) + _get_alive_enemies_in_stage(player_entity, tcg_game)

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
def activate_play_cards(
    # tcg_game: TCGGame,
    entity: Entity,
    targets: List[str],
) -> Tuple[bool, str]:
    """
    为指定角色激活出牌动作（取手牌 cards[0]）。

    Args:
        tcg_game: TCG游戏实例
        entity: 出牌的战斗角色实体（expedition_member 或 enemy）
        targets: 目标名称列表，外部传入，可为 []

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """

    assert entity.has(ExpeditionMemberComponent) or entity.has(
        EnemyComponent
    ), f"Entity {entity.name} must be ExpeditionMemberComponent or EnemyComponent"

    assert not entity.has(
        DeathComponent
    ), f"Entity {entity.name} is dead and cannot play cards"

    assert entity.has(HandComponent), f"Entity {entity.name} must have HandComponent"

    hand_comp = entity.get(HandComponent)
    assert len(hand_comp.cards) > 0, f"Entity {entity.name} has no cards in hand"

    selected_card = hand_comp.cards[0]
    entity.replace(PlayCardsAction, entity.name, selected_card, targets)

    return True, f"成功为角色 {entity.name} 激活出牌动作"


###################################################################################################################################################################
def activate_all_play_cards(
    tcg_game: TCGGame,
) -> Tuple[bool, str]:
    """
    为当前场景中所有存活的战斗角色（远征队成员 + 敌方）激活出牌动作。

    先确保所有角色都有兜底卡牌，再对每个角色调用 activate_play_cards。

    Args:
        tcg_game: TCG游戏实例

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """

    if not tcg_game.current_dungeon.is_ongoing:
        error_msg = "激活出牌动作失败: 只能在战斗中使用is_ongoing"
        logger.error(error_msg)
        return False, error_msg

    last_round = tcg_game.current_dungeon.latest_round
    if last_round is None or last_round.is_round_completed:
        error_msg = "激活出牌动作失败: 当前没有未完成的回合可供打牌"
        logger.error(error_msg)
        return False, error_msg

    player_entity = tcg_game.get_player_entity()
    assert player_entity is not None, "activate_all_play_cards: player_entity is None"

    all_entities = _get_alive_expedition_members_in_stage(
        player_entity, tcg_game
    ) + _get_alive_enemies_in_stage(player_entity, tcg_game)

    for entity in all_entities:
        success, message = activate_play_cards(entity, [])
        if not success:
            return False, message

    return True, f"成功为 {len(all_entities)} 个战斗角色激活出牌动作"


###################################################################################################################################################################
def activate_expedition_retreat(
    tcg_game: TCGGame,
) -> Tuple[bool, str]:
    """
    为所有远征队成员激活撤退动作。

    为每个远征队成员添加 RetreatAction 组件，由 RetreatActionSystem 响应处理。
    要求当前处于战斗进行中（is_ongoing）状态。

    这是符合 ECS 响应式架构的新实现方式，替代直接操作的 mark_expedition_retreat。
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

    expedition_member_entities = tcg_game.get_group(
        Matcher(all_of=[ExpeditionMemberComponent])
    ).entities

    if len(expedition_member_entities) == 0:
        error_msg = "激活撤退动作失败: 没有找到远征队成员"
        logger.error(error_msg)
        return False, error_msg

    # 为每个远征队成员添加撤退动作组件
    for expedition_member_entity in expedition_member_entities:
        assert expedition_member_entity.has(
            ExpeditionMemberComponent
        ), f"Entity {expedition_member_entity.name} must have ExpeditionMemberComponent"

        expedition_member_entity.replace(
            RetreatAction,
            expedition_member_entity.name,
        )
        logger.debug(f"为角色 {expedition_member_entity.name} 添加撤退动作组件")

    return (
        True,
        f"成功为 {len(expedition_member_entities)} 个远征队成员激活撤退动作",
    )


###################################################################################################################################################################
