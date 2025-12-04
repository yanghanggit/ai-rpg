"""
地下城战斗动作模块

本模块提供地下城战斗中的各种动作激活函数，用于在战斗回合中为角色添加和管理动作。
这些动作包括抽牌、出牌等核心战斗行为，是战斗系统的关键组成部分。

主要功能:
    - 抽牌动作激活: 为场上所有存活角色添加抽牌动作
    - 打牌动作激活: 为角色随机选择并激活打牌动作

核心概念:
    - Action Component: 动作组件，通过ECS系统附加到实体上
    - Combat Pipeline: 战斗处理流程，负责执行这些动作
    - Round System: 回合系统，管理战斗的顺序和状态

使用场景:
    这些函数通常在地下城战斗的特定阶段被调用，用于驱动战斗流程。
    它们会修改实体的组件状态，然后由 combat_pipeline 处理实际的执行逻辑。
"""

import random
from typing import Set, Tuple
from loguru import logger
from ..game.tcg_game import TCGGame
from ..models import (
    DrawCardsAction,
    HandComponent,
    PlayCardsAction,
)
from ..entitas import Entity


###################################################################################################################################################################
def activate_actor_card_draws(tcg_game: TCGGame) -> None:
    """
    为场上所有存活角色激活抽牌动作

    为玩家所在场景的所有存活角色添加抽牌动作组件，由 combat_pipeline 后续处理执行。

    Args:
        tcg_game: TCG游戏实例
    """

    player_entity = tcg_game.get_player_entity()
    assert player_entity is not None, "activate_actor_card_draws: player_entity is None"

    # 获取场上所有存活的角色
    actor_entities = tcg_game.get_alive_actors_on_stage(player_entity)

    # 为每个角色添加抽牌动作组件
    for entity in actor_entities:
        entity.replace(
            DrawCardsAction,
            entity.name,
        )


###################################################################################################################################################################
def activate_random_play_cards(tcg_game: TCGGame) -> Tuple[bool, str]:
    """
    为所有存活角色随机选择并激活打牌动作

    为当前回合中的每个存活角色随机选择一张手牌，并设置为待执行的打牌动作。
    用于测试或AI自动推进战斗。

    Args:
        tcg_game: TCG游戏实例

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """

    # 1. 验证战斗回合状态
    if len(tcg_game.current_combat_sequence.current_rounds) == 0:
        error_msg = "激活打牌动作失败: 没有当前回合"
        logger.error(error_msg)
        return False, error_msg

    if not tcg_game.current_combat_sequence.is_ongoing:
        error_msg = "激活打牌动作失败: 回合未在进行中"
        logger.error(error_msg)
        return False, error_msg

    if tcg_game.current_combat_sequence.latest_round.is_completed:
        error_msg = "激活打牌动作失败: 回合已完成"
        logger.error(error_msg)
        return False, error_msg

    # 必须有玩家实体在的场景中
    player_entity = tcg_game.get_player_entity()
    assert player_entity is not None, "activate_actor_card_draws: player_entity is None"

    # 2. 获取所有存活且拥有手牌的角色
    actor_entities: Set[Entity] = tcg_game.get_alive_actors_on_stage(player_entity)
    if len(actor_entities) == 0:
        error_msg = "激活打牌动作失败: 没有存活的持有手牌的角色"
        logger.error(error_msg)
        return False, error_msg

    # 3. 预验证所有角色状态（避免部分成功）
    latest_round = tcg_game.current_combat_sequence.latest_round
    for actor_entity in actor_entities:
        # 验证角色在行动队列中
        if actor_entity.name not in latest_round.action_order:
            error_msg = (
                f"激活打牌动作失败: 角色 {actor_entity.name} 不在本回合行动队列中"
            )
            logger.error(error_msg)
            return False, error_msg

        # 验证角色尚未有打牌动作
        if actor_entity.has(PlayCardsAction):
            error_msg = f"激活打牌动作失败: 角色 {actor_entity.name} 已有打牌动作"
            logger.error(error_msg)
            return False, error_msg

        # 验证角色有手牌组件且有可用手牌
        if not actor_entity.has(HandComponent):
            error_msg = f"激活打牌动作失败: 角色 {actor_entity.name} 没有手牌组件"
            logger.error(error_msg)
            return False, error_msg

        hand_comp = actor_entity.get(HandComponent)
        assert (
            len(hand_comp.cards) > 0
        ), f"激活打牌动作失败: 角色 {actor_entity.name} 手牌组件异常"
        if len(hand_comp.cards) == 0:
            error_msg = f"激活打牌动作失败: 角色 {actor_entity.name} 没有可用手牌"
            logger.error(error_msg)
            return False, error_msg

    # 4. 为所有角色添加随机打牌动作
    for actor_entity in actor_entities:
        hand_comp = actor_entity.get(HandComponent)
        selected_card = random.choice(hand_comp.cards)

        logger.debug(f"为角色 {actor_entity.name} 随机选择卡牌: {selected_card.name}")

        # 添加打牌动作组件
        actor_entity.replace(
            PlayCardsAction,
            actor_entity.name,
            selected_card,
            selected_card.targets,  # 后续这里可以换掉 让客户端决定,作为出牌。
        )

    return True, "成功激活打牌动作"


###################################################################################################################################################################
