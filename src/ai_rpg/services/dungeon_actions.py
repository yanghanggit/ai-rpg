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
    CombatStatsComponent,
    DeathComponent,
)
from ..entitas import Entity


###################################################################################################################################################################
def _generate_retreat_message(dungeon_name: str, stage_name: str) -> str:
    """生成撤退提示消息

    Args:
        dungeon_name: 地下城名称
        stage_name: 当前关卡名称

    Returns:
        str: 格式化的撤退提示消息
    """
    return f"""# 提示！战斗撤退：从地下城 {dungeon_name} 的关卡 {stage_name} 撤退

你选择了战斗中撤退。所有同伴视为战斗失败。战斗结束后将返回家园。"""


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
def activate_random_ally_card_draws(tcg_game: TCGGame) -> Tuple[bool, str]:
    """
    为场上所有存活的Ally阵营角色激活抽牌动作（随机选择技能和状态效果）

    Args:
        tcg_game: TCG游戏实例

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """

    player_entity = tcg_game.get_player_entity()
    if player_entity is None:
        error_msg = "激活Ally抽牌失败: 玩家实体不存在"
        logger.error(error_msg)
        return False, error_msg

    # 获取场上所有存活的角色
    actor_entities = tcg_game.get_alive_actors_on_stage(player_entity)

    # 筛选Ally阵营的角色
    ally_entities = [entity for entity in actor_entities if entity.has(AllyComponent)]

    if len(ally_entities) == 0:
        error_msg = "激活Ally抽牌失败: 没有存活的Ally角色"
        logger.error(error_msg)
        return False, error_msg

    activated_count = 0

    # 为每个Ally角色添加抽牌动作组件
    for entity in ally_entities:

        # 跳过已经有抽牌动作的角色
        if entity.has(DrawCardsAction):
            logger.warning(
                f"Entity {entity.name} already has DrawCardsAction, skipping activation"
            )
            continue

        # 获取可用技能列表
        available_skills = _get_available_skills(entity)
        if len(available_skills) == 0:
            error_msg = f"激活Ally抽牌失败: 角色 {entity.name} 没有可用技能"
            logger.error(error_msg)
            return False, error_msg

        # 随机选择一个技能作为初始技能
        selected_skill = random.choice(available_skills)

        # 获取敌方目标列表
        targets = get_enemy_targets_for_ally(entity, tcg_game)

        # 随机一个target,然后组成[]
        if len(targets) > 0:
            targets = [random.choice(targets)]

        # 获取角色当前所有的状态效果
        combat_stats = entity.get(CombatStatsComponent)
        status_effects = combat_stats.status_effects.copy() if combat_stats else []

        # 随机从全部中选择一个，然后组成[]
        if len(status_effects) > 0:
            status_effects = [random.choice(status_effects)]

        # 目前传随机状态效果列表
        entity.replace(
            DrawCardsAction,
            entity.name,
            selected_skill,  # skill
            targets,  # targets
            status_effects,  # 随机状态效果列表
        )
        activated_count += 1

    return True, f"成功为{activated_count}个Ally角色激活抽牌动作"


###################################################################################################################################################################
def activate_specified_ally_card_draws(
    entity_name: str,
    tcg_game: TCGGame,
    skill_name: str,
    target_names: List[str],
    status_effect_names: List[str],
) -> Tuple[bool, str]:
    """
    为指定的Ally阵营角色激活抽牌动作（使用指定的技能、目标和状态效果）

    Args:
        entity_name: 出牌者实体名称
        tcg_game: TCG游戏实例
        skill_name: 指定的技能名称
        target_names: 指定的目标名称列表
        status_effect_names: 指定的状态效果名称列表

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """

    player_entity = tcg_game.get_player_entity()
    if player_entity is None:
        error_msg = "激活指定Ally抽牌失败: 玩家实体不存在"
        logger.error(error_msg)
        return False, error_msg

    # 获取场上所有存活的角色
    actor_entities = tcg_game.get_alive_actors_on_stage(player_entity)

    # 查找指定名称的实体
    entity = None
    for actor in actor_entities:
        if actor.name == entity_name:
            entity = actor
            break

    # 验证实体存在
    if entity is None:
        error_msg = f"激活指定Ally抽牌失败: 角色 '{entity_name}' 不在存活角色中: {[actor.name for actor in actor_entities]}"
        logger.error(error_msg)
        return False, error_msg

    # 验证实体是Ally阵营
    if not entity.has(AllyComponent):
        error_msg = f"激活指定Ally抽牌失败: 角色 '{entity_name}' 不是Ally阵营"
        logger.error(error_msg)
        return False, error_msg

    # 检查是否已经有抽牌动作
    if entity.has(DrawCardsAction):
        logger.warning(
            f"Entity {entity.name} already has DrawCardsAction, skipping activation"
        )
        return True, f"角色 {entity.name} 已有抽牌动作，跳过"

    # 构建场上所有存活角色的名称集合（用于验证目标）
    alive_actor_names = {actor.name for actor in actor_entities}

    # 1. 验证并获取指定的技能
    available_skills = _get_available_skills(entity)
    selected_skill = None
    for skill in available_skills:
        if skill.name == skill_name:
            selected_skill = skill
            break

    if selected_skill is None:
        error_msg = f"激活指定Ally抽牌失败: 角色 {entity.name} 没有技能 '{skill_name}'，可用技能: {[s.name for s in available_skills]}"
        logger.error(error_msg)
        return False, error_msg

    # 2. 验证目标名称是否都在场上存活角色中
    invalid_targets = [
        target for target in target_names if target not in alive_actor_names
    ]
    if invalid_targets:
        error_msg = f"激活指定Ally抽牌失败: 无效的目标 {invalid_targets}，存活角色: {alive_actor_names}"
        logger.error(error_msg)
        return False, error_msg

    # 3. 验证状态效果名称是否都在实体的当前状态效果中
    combat_stats = entity.get(CombatStatsComponent)
    current_status_effects = combat_stats.status_effects.copy() if combat_stats else []
    current_status_effect_names = {se.name for se in current_status_effects}

    invalid_status_effects = [
        se_name
        for se_name in status_effect_names
        if se_name not in current_status_effect_names
    ]
    if invalid_status_effects:
        error_msg = f"激活指定Ally抽牌失败: 无效的状态效果 {invalid_status_effects}，当前状态效果: {current_status_effect_names}"
        logger.error(error_msg)
        return False, error_msg

    # 4. 根据状态效果名称筛选出对应的状态效果对象
    selected_status_effects = [
        se for se in current_status_effects if se.name in status_effect_names
    ]

    # 5. 创建 DrawCardsAction 组件
    entity.replace(
        DrawCardsAction,
        entity.name,
        selected_skill,  # skill
        target_names,  # targets
        selected_status_effects,  # 指定的状态效果列表
    )

    return True, f"成功为角色 {entity.name} 激活抽牌动作"


###################################################################################################################################################################
def activate_random_enemy_card_draws(tcg_game: TCGGame) -> Tuple[bool, str]:
    """
    为场上所有存活的Enemy阵营角色激活抽牌动作（随机选择技能和状态效果）

    Args:
        tcg_game: TCG游戏实例

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """

    player_entity = tcg_game.get_player_entity()
    if player_entity is None:
        error_msg = "激活Enemy抽牌失败: 玩家实体不存在"
        logger.error(error_msg)
        return False, error_msg

    # 获取场上所有存活的角色
    actor_entities = tcg_game.get_alive_actors_on_stage(player_entity)

    # 筛选Enemy阵营的角色
    enemy_entities = [entity for entity in actor_entities if entity.has(EnemyComponent)]

    if len(enemy_entities) == 0:
        error_msg = "激活Enemy抽牌失败: 没有存活的Enemy角色"
        logger.error(error_msg)
        return False, error_msg

    activated_count = 0

    # 为每个Enemy角色添加抽牌动作组件
    for entity in enemy_entities:

        # 跳过已经有抽牌动作的角色
        if entity.has(DrawCardsAction):
            logger.warning(
                f"Entity {entity.name} already has DrawCardsAction, skipping activation"
            )
            continue

        # 获取可用技能列表
        available_skills = _get_available_skills(entity)
        if len(available_skills) == 0:
            error_msg = f"激活Enemy抽牌失败: 角色 {entity.name} 没有可用技能"
            logger.error(error_msg)
            return False, error_msg

        # 随机选择一个技能作为初始技能
        selected_skill = random.choice(available_skills)

        # 获取敌方目标列表
        targets = get_ally_targets_for_enemy(entity, tcg_game)

        # 随机一个target,然后组成[]
        if len(targets) > 0:
            targets = [random.choice(targets)]

        # 获取角色当前所有的状态效果
        combat_stats = entity.get(CombatStatsComponent)
        status_effects = combat_stats.status_effects.copy() if combat_stats else []

        # 随机从全部中选择一个，然后组成[]
        if len(status_effects) > 0:
            status_effects = [random.choice(status_effects)]

        # 目前传随机状态效果列表
        entity.replace(
            DrawCardsAction,
            entity.name,
            selected_skill,  # skill
            targets,  # targets
            status_effects,  # 随机状态效果列表
        )
        activated_count += 1

    return True, f"成功为{activated_count}个Enemy角色激活抽牌动作"


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

        # logger.debug(f"为角色 {actor_entity.name} 随机选择卡牌: {selected_card.name}")

        # 添加打牌动作组件
        actor_entity.replace(
            PlayCardsAction,
            actor_entity.name,
            selected_card,
            selected_card.targets,  # 后续这里可以换掉 让客户端决定,作为出牌。
        )

    return True, "成功激活打牌动作"


###################################################################################################################################################################
def retreat_from_dungeon_combat(tcg_game: TCGGame) -> Tuple[bool, str]:
    """
    战斗中撤退

    允许玩家在战斗进行中主动撤退，所有ally阵营角色视为死亡，
    触发地下城失败流程并返回家园。

    Args:
        tcg_game: TCG游戏实例

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """
    # 1. 验证战斗状态
    if not tcg_game.current_combat_sequence.is_ongoing:
        error_msg = "撤退失败: 当前没有进行中的战斗"
        logger.error(error_msg)
        return False, error_msg

    # 2. 验证地下城状态
    dungeon = tcg_game.world.dungeon
    if dungeon is None or dungeon.current_stage_index < 0:
        error_msg = "撤退失败: 当前不在地下城中"
        logger.error(error_msg)
        return False, error_msg

    # 3. 获取当前地下城场景
    current_stage = dungeon.get_current_stage()
    if current_stage is None:
        error_msg = "撤退失败: 无法获取当前地下城场景"
        logger.error(error_msg)
        return False, error_msg

    # 4. 获取玩家实体
    player_entity = tcg_game.get_player_entity()
    if player_entity is None:
        error_msg = "撤退失败: 无法找到玩家实体"
        logger.error(error_msg)
        return False, error_msg

    # 5. 获取场景内所有ally阵营角色
    actor_entities = tcg_game.get_alive_actors_on_stage(player_entity)
    ally_entities = [entity for entity in actor_entities if entity.has(AllyComponent)]

    if len(ally_entities) == 0:
        error_msg = "撤退失败: 场景内没有ally阵营角色"
        logger.error(error_msg)
        return False, error_msg

    # 6. 为所有ally角色添加DeathComponent（标记为死亡）
    for ally_entity in ally_entities:
        ally_entity.replace(DeathComponent, ally_entity.name)
        logger.info(f"撤退: 角色 {ally_entity.name} 标记为死亡")

    # 7. 为所有ally角色添加撤退消息到上下文
    retreat_message = _generate_retreat_message(dungeon.name, current_stage.name)

    for ally_entity in ally_entities:
        tcg_game.add_human_message(
            ally_entity,
            retreat_message,
            dungeon_lifecycle_retreat=f"{dungeon.name}:{current_stage.name}",
        )

    logger.info(
        f"战斗撤退成功: 地下城={dungeon.name}, 关卡={current_stage.name}, "
        f"撤退角色数={len(ally_entities)}"
    )

    return True, f"成功从 {dungeon.name} 的 {current_stage.name} 撤退"


###################################################################################################################################################################
