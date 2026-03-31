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
    Card,
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
def activate_play_cards_specified(
    tcg_game: TCGGame,
    actor_name: str,
    card_name: str,
    targets: List[str],
) -> Tuple[bool, str]:
    """
    让指定角色打出指定名称的手牌。

    Args:
        tcg_game: TCG游戏实例
        actor_name: 出牌角色的全名（如 角色.猎人.石坚）
        card_name: 要打出的卡牌名称（须存在于该角色手牌中）
        targets: 目标名称列表，可为 []

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """
    # 首位规则：必须在本回合 action_order 内，且当前轮到自己出牌
    latest_round = tcg_game.current_dungeon.latest_round
    if latest_round is None:
        error_msg = "activate_play_cards_specified: 当前没有进行中的回合"
        logger.error(error_msg)
        return False, error_msg

    if actor_name not in latest_round.action_order:
        error_msg = (
            f"角色 {actor_name} 不在本回合行动顺序中: {latest_round.action_order}"
        )
        logger.error(error_msg)
        return False, error_msg

    next_actor = next(
        (
            a
            for a in latest_round.action_order
            if a not in latest_round.completed_actors
        ),
        None,
    )
    if next_actor != actor_name:
        error_msg = f"现在不是 {actor_name} 的回合，当前应由 {next_actor} 出牌"
        logger.error(error_msg)
        return False, error_msg

    entity = tcg_game.get_actor_entity(actor_name)
    if entity is None:
        error_msg = f"activate_play_cards_specified: 找不到角色 {actor_name}"
        logger.error(error_msg)
        return False, error_msg

    if not (entity.has(ExpeditionMemberComponent) or entity.has(EnemyComponent)):
        error_msg = f"角色 {actor_name} 不是战斗角色（非 ExpeditionMember 或 Enemy）"
        logger.error(error_msg)
        return False, error_msg

    if entity.has(DeathComponent):
        error_msg = f"角色 {actor_name} 已死亡，无法出牌"
        logger.error(error_msg)
        return False, error_msg

    if not entity.has(HandComponent):
        error_msg = f"角色 {actor_name} 没有 HandComponent"
        logger.error(error_msg)
        return False, error_msg

    if entity.has(ExpeditionMemberComponent):

        hand_comp = entity.get(HandComponent)
        selected_card = next((c for c in hand_comp.cards if c.name == card_name), None)
        if selected_card is None:
            error_msg = f"角色 {actor_name} 手牌中找不到卡牌 '{card_name}'，当前手牌: {[c.name for c in hand_comp.cards]}"
            logger.error(error_msg)
            return False, error_msg

        logger.debug(
            f"为角色 {actor_name} 激活出牌动作，卡牌: {selected_card.name} 目标: {targets}"
        )
        entity.replace(PlayCardsAction, entity.name, selected_card, targets)

    else:

        # 敌人就故意给一个空的
        assert entity.has(
            EnemyComponent
        ), f"角色 {actor_name} 既不是远征队成员也不是敌人，无法出牌"

        logger.debug(
            f"为敌人 {actor_name} 激活出牌动作，（敌人默认空卡），会由系统自动选择卡牌和目标"
        )
        entity.replace(PlayCardsAction, entity.name, Card(name="", action=""), [])

    return True, f"成功为角色 {actor_name} 激活出牌动作（卡牌: {card_name}）"


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
