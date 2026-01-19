"""
地下城战斗动作模块

提供战斗回合中的动作激活函数，包括抽牌和打牌等核心战斗行为。
这些函数通过添加动作组件来驱动战斗流程，由 combat_pipeline 负责执行。
"""

import random
from typing import List, Set, Tuple
from loguru import logger
from ..game.tcg_game import TCGGame
from ..models import (
    DrawCardsAction,
    HandComponent,
    PlayCardsAction,
    Skill,
    SkillBookComponent,
    AllyComponent,
    EnemyComponent,
)
from ..entitas import Entity


###################################################################################################################################################################
def _get_available_skills(entity: Entity) -> List[Skill]:
    """获取实体可用的技能列表

    Args:
        entity: 目标实体

    Returns:
        实体的所有可用技能列表
    """
    skill_book_comp = entity.get(SkillBookComponent)
    assert skill_book_comp is not None, "Entity must have SkillBookComponent"

    if len(skill_book_comp.skills) == 0:
        logger.warning(f"entity {entity.name} has no skills in SkillBookComponent")
        assert False, "Entity has no skills in SkillBookComponent"

    return skill_book_comp.skills.copy()


###################################################################################################################################################################
def get_enemy_targets_for_ally(entity: Entity, tcg_game: TCGGame) -> List[str]:
    """获取ally阵营角色的敌方目标列表

    站在ally视角，返回场景内所有带EnemyComponent的实体名称列表。
    用于为ally角色的DrawCardsAction填充targets字段。

    Args:
        entity: ally阵营的角色实体
        tcg_game: TCG游戏实例

    Returns:
        敌方实体名称列表
    """
    assert entity.has(AllyComponent), f"Entity {entity.name} must have AllyComponent"

    # 获取entity所在场景的所有存活角色
    actor_entities = tcg_game.get_alive_actors_on_stage(entity)

    # 筛选所有enemy阵营的实体
    enemy_targets = [
        actor.name for actor in actor_entities if actor.has(EnemyComponent)
    ]

    return enemy_targets


###################################################################################################################################################################
def get_ally_targets_for_enemy(entity: Entity, tcg_game: TCGGame) -> List[str]:
    """获取enemy阵营角色的敌方目标列表

    站在enemy视角，返回场景内所有带AllyComponent的实体名称列表。
    用于为enemy角色的DrawCardsAction填充targets字段。

    Args:
        entity: enemy阵营的角色实体
        tcg_game: TCG游戏实例

    Returns:
        敌方实体名称列表
    """
    assert entity.has(EnemyComponent), f"Entity {entity.name} must have EnemyComponent"

    # 获取entity所在场景的所有存活角色
    actor_entities = tcg_game.get_alive_actors_on_stage(entity)

    # 筛选所有ally阵营的实体
    ally_targets = [actor.name for actor in actor_entities if actor.has(AllyComponent)]

    return ally_targets


###################################################################################################################################################################
def activate_actor_card_draws(tcg_game: TCGGame) -> None:
    """
    为场上所有存活角色激活抽牌动作

    Args:
        tcg_game: TCG游戏实例
    """

    player_entity = tcg_game.get_player_entity()
    assert player_entity is not None, "activate_actor_card_draws: player_entity is None"

    # 获取场上所有存活的角色
    actor_entities = tcg_game.get_alive_actors_on_stage(player_entity)

    # 为每个角色添加抽牌动作组件
    for entity in actor_entities:
        # 获取可用技能列表（最多2个），这里加一条吧，在编辑过程中，就不允许出现无技能的人物。
        available_skills = _get_available_skills(entity)
        assert (
            len(available_skills) > 0
        ), f"Entity {entity.name} has no available skills"

        # 随机选择一个技能作为初始技能
        selected_skill = (
            random.choice(available_skills)
            if available_skills
            else Skill(name="", description="")
        )

        # 根据阵营获取目标列表
        if entity.has(AllyComponent):
            targets = get_enemy_targets_for_ally(entity, tcg_game)
        elif entity.has(EnemyComponent):
            targets = get_ally_targets_for_enemy(entity, tcg_game)
        else:
            logger.warning(
                f"Entity {entity.name} has neither AllyComponent nor EnemyComponent"
            )
            targets = []

        # 加一些日志用于调试!
        logger.debug(
            f"为角色 {entity.name} 激活抽牌动作，使用技能 【{selected_skill.name}】，目标列表: {targets}"
        )

        entity.replace(
            DrawCardsAction,
            entity.name,
            selected_skill,  # skill
            targets,  # targets
            [],  # status_effects
        )


###################################################################################################################################################################
def activate_random_play_cards(tcg_game: TCGGame) -> Tuple[bool, str]:
    """
    为所有存活角色随机选择并激活打牌动作

    为每个存活角色随机选择一张手牌并添加打牌动作组件。

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
