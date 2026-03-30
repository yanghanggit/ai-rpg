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
    SkillBookComponent,
    ExpeditionMemberComponent,
    EnemyComponent,
    CombatStatusEffectsComponent,
    DeathComponent,
    Card2,
    RetreatAction,
)
from ..entitas import Entity, Matcher
from langchain_core.messages import AIMessage


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
def activate_random_expedition_member_card_draws(
    tcg_game: TCGGame,
) -> Tuple[bool, str]:
    """
    为当前场景中所有存活的远征队成员激活抽牌动作（随机选择技能和状态效果）

    Args:
        tcg_game: TCG游戏实例，内部自行获取玩家实体及场景内的队员与敌方列表

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """

    if not tcg_game.current_dungeon.is_ongoing:
        return False, "只能在战斗中使用is_ongoing"

    player_entity = tcg_game.get_player_entity()
    assert (
        player_entity is not None
    ), "activate_random_expedition_member_card_draws: player_entity is None"

    expedition_member_entities = _get_alive_expedition_members_in_stage(
        player_entity, tcg_game
    )
    enemy_entities = _get_alive_enemies_in_stage(player_entity, tcg_game)

    if len(expedition_member_entities) == 0:
        error_msg = "激活远征队成员抽牌失败: 没有存活的远征队成员"
        logger.error(error_msg)
        return False, error_msg

    if len(enemy_entities) == 0:
        error_msg = "激活远征队成员抽牌失败: 没有存活的敌方角色"
        logger.error(error_msg)
        return False, error_msg

    # 预先构建敌方目标名称列表（循环内不变）
    enemy_target_names = [entity.name for entity in enemy_entities]

    # 为每个远征队成员添加抽牌动作组件
    for entity in expedition_member_entities:

        # 跳过已经有抽牌动作的角色
        if entity.has(DrawCardsAction):
            logger.warning(
                f"Entity {entity.name} already has DrawCardsAction, so will be overwritten by new DrawCardsAction"
            )

        # 获取可用技能列表
        assert entity.has(
            SkillBookComponent
        ), f"Entity {entity.name} must have SkillBookComponent"
        skill_book_comp = entity.get(SkillBookComponent)
        assert (
            len(skill_book_comp.skills) > 0
        ), f"Entity {entity.name} has no skills in SkillBookComponent"
        available_skills = skill_book_comp.skills.copy()

        # 随机选择一个技能作为初始技能
        selected_skill = random.choice(available_skills)

        # 随机选择一个敌方目标
        targets = [random.choice(enemy_target_names)] if enemy_target_names else []

        # 获取角色当前所有的状态效果
        assert entity.has(
            CombatStatusEffectsComponent
        ), f"Entity {entity.name} must have CombatStatusEffectsComponent"
        combat_status_effects = entity.get(CombatStatusEffectsComponent)
        status_effects = combat_status_effects.status_effects.copy()

        # 随机从全部中选择一个，然后组成[]
        if len(status_effects) > 0:
            status_effects = [random.choice(status_effects)]

        # 以上 DrawCardsAction 所需的数据全部准备完成，添加组件。
        entity.replace(
            DrawCardsAction,
            entity.name,
            selected_skill,  # skill
            targets,  # targets
            status_effects,  # 随机状态效果列表
        )

    return True, f"成功为 {len(expedition_member_entities)} 个远征队成员激活抽牌动作"


###################################################################################################################################################################
def activate_specified_expedition_member_card_draws(
    tcg_game: TCGGame,
    expedition_member_name: str,
    target_names: List[str],
    skill_name: str,
    status_effect_names: List[str],
) -> Tuple[bool, str]:
    """
    为指定的远征队成员激活抽牌动作（使用指定的技能、目标和状态效果）

    Args:
        tcg_game: TCG游戏实例，内部自行查找实体及过滤合法目标
        expedition_member_name: 出牌者名称（须为远征队成员且存活）
        target_names: 指定的目标名称列表（内部会过滤出场且存活的实体）
        skill_name: 指定的技能名称
        status_effect_names: 指定的状态效果名称列表

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """

    if not tcg_game.current_dungeon.is_ongoing:
        logger.error(f"玩家 {expedition_member_name} 抽卡失败: 战斗未在进行中")
        return False, "只能在战斗中使用is_ongoing"

    # 查找实体
    expedition_member_entity = tcg_game.get_entity_by_name(expedition_member_name)
    if expedition_member_entity is None:
        error_msg = f"激活指定抽牌失败: 无法找到角色 '{expedition_member_name}'"
        logger.error(error_msg)
        return False, error_msg

    assert not expedition_member_entity.has(
        DeathComponent
    ), f"Entity {expedition_member_entity.name} is dead and cannot draw cards"

    assert expedition_member_entity.has(
        ExpeditionMemberComponent
    ), f"Entity {expedition_member_entity.name} must have ExpeditionMemberComponent"

    # 必须是玩家所在场景中的角色才能被激活抽牌动作，避免跨场景操作导致的逻辑混乱
    player_entity = tcg_game.get_player_entity()
    assert (
        player_entity is not None
    ), "activate_specified_expedition_member_card_draws: player_entity is None"

    if tcg_game.resolve_stage_entity(
        expedition_member_entity
    ) != tcg_game.resolve_stage_entity(player_entity):
        error_msg = (
            f"激活指定抽牌失败: 角色 '{expedition_member_name}' 不在玩家所在的场景中"
        )
        logger.error(error_msg)
        return False, error_msg

    # 过滤合法目标（场上存活）
    valid_target_entities = [
        entity
        for entity in tcg_game.get_alive_actors_in_stage(expedition_member_entity)
        if entity.name in set(target_names)
    ]
    if len(valid_target_entities) == 0:
        error_msg = f"激活指定抽牌失败: 角色 {expedition_member_name} 没有合法的目标"
        logger.error(error_msg)
        return False, error_msg

    # 这里不直接assert，允许覆盖（比如玩家选择了新的技能和目标），但会有日志警告
    if expedition_member_entity.has(DrawCardsAction):
        logger.warning(
            f"Entity {expedition_member_entity.name} already has DrawCardsAction, so will be overwritten by new DrawCardsAction"
        )

    # 1. 获取指定的技能
    assert expedition_member_entity.has(
        SkillBookComponent
    ), f"Entity {expedition_member_entity.name} must have SkillBookComponent"
    skill_book_comp = expedition_member_entity.get(SkillBookComponent)

    selected_skill = skill_book_comp.find_skill(skill_name)
    if selected_skill is None:
        error_msg = f"激活指定抽牌失败: 角色 {expedition_member_entity.name} 没有技能 '{skill_name}'，可用技能: {[s.name for s in skill_book_comp.skills]}"
        logger.error(error_msg)
        return False, error_msg

    # 2. 验证状态效果名称是否都在实体的当前状态效果中
    assert expedition_member_entity.has(
        CombatStatusEffectsComponent
    ), f"Entity {expedition_member_entity.name} must have CombatStatusEffectsComponent"
    combat_status_effects = expedition_member_entity.get(CombatStatusEffectsComponent)
    for effect_name in status_effect_names:
        if combat_status_effects.find_status_effect(effect_name) is None:
            error_msg = f"激活指定抒牌失败: 角色 {expedition_member_entity.name} 没有状态效果 '{effect_name}'，当前状态效果: {[e.name for e in combat_status_effects.status_effects]}"
            logger.error(error_msg)
            return False, error_msg

    # 3. 创建 DrawCardsAction 组件
    selected_status_effects = [
        combat_status_effects.find_status_effect(name)
        for name in status_effect_names
        if combat_status_effects.find_status_effect(name) is not None
    ]
    expedition_member_entity.replace(
        DrawCardsAction,
        expedition_member_entity.name,
        selected_skill,  # skill
        [e.name for e in valid_target_entities],  # targets
        selected_status_effects,  # 指定的状态效果对象列表
    )

    return True, f"成功为角色 {expedition_member_entity.name} 激活抽牌动作"


###################################################################################################################################################################
def activate_random_enemy_card_draws(
    tcg_game: TCGGame,
) -> Tuple[bool, str]:
    """
    为当前场景中所有存活的敌方激活抽牌动作（随机选择技能和状态效果）

    Args:
        tcg_game: TCG游戏实例，内部自行获取玩家实体及场景内的敌方与队员列表

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """

    if not tcg_game.current_dungeon.is_ongoing:
        return False, "只能在战斗中使用is_ongoing"

    player_entity = tcg_game.get_player_entity()
    assert (
        player_entity is not None
    ), "activate_random_enemy_card_draws: player_entity is None"

    enemy_entities = _get_alive_enemies_in_stage(player_entity, tcg_game)
    expedition_member_entities = _get_alive_expedition_members_in_stage(
        player_entity, tcg_game
    )

    if len(enemy_entities) == 0:
        error_msg = "激活Enemy抽牌失败: 没有存活的Enemy角色"
        logger.error(error_msg)
        return False, error_msg

    if len(expedition_member_entities) == 0:
        error_msg = "激活Enemy抽牌失败: 没有存活的远征队成员"
        logger.error(error_msg)
        return False, error_msg

    # 预先构建远征队成员目标名称列表（循环内不变）
    expedition_member_target_names = [
        entity.name for entity in expedition_member_entities
    ]

    # 为每个Enemy角色添加抽牌动作组件
    for entity in enemy_entities:

        # 跳过已经有抽牌动作的角色
        if entity.has(DrawCardsAction):
            logger.warning(
                f"Entity {entity.name} already has DrawCardsAction, so will be overwritten by new DrawCardsAction"
            )

        # 获取可用技能列表
        assert entity.has(
            SkillBookComponent
        ), f"Entity {entity.name} must have SkillBookComponent"
        skill_book_comp = entity.get(SkillBookComponent)
        assert (
            len(skill_book_comp.skills) > 0
        ), f"Entity {entity.name} has no skills in SkillBookComponent"
        available_skills = skill_book_comp.skills.copy()

        # 随机选择一个技能作为初始技能
        selected_skill = random.choice(available_skills)

        # 随机选择一个远征队成员目标
        targets = (
            [random.choice(expedition_member_target_names)]
            if expedition_member_target_names
            else []
        )

        # 获取角色当前所有的状态效果
        assert entity.has(
            CombatStatusEffectsComponent
        ), f"Entity {entity.name} must have CombatStatusEffectsComponent"
        combat_status_effects = entity.get(CombatStatusEffectsComponent)
        status_effects = combat_status_effects.status_effects.copy()

        # 随机从全部中选择一个，然后组成[]
        if len(status_effects) > 0:
            status_effects = [random.choice(status_effects)]

        # 以上 DrawCardsAction 所需的数据全部准备完成，添加组件。
        entity.replace(
            DrawCardsAction,
            entity.name,
            selected_skill,  # skill
            targets,  # targets
            status_effects,  # 随机状态效果列表
        )

    return True, f"成功为 {len(enemy_entities)} 个Enemy角色激活抽牌动作"


###################################################################################################################################################################
def activate_play_cards(
    tcg_game: TCGGame,
) -> Tuple[bool, str]:
    """
    为所有存活角色激活打牌动作（取手牌列表第一张）

    对每个存活战斗角色取 HandComponent 中的第一张手牌并添加打牌动作组件。
    如果发现有角色缺少手牌，会自动为其添加兜底卡牌，确保战斗流程连续性。

    Args:
        tcg_game: TCG游戏实例，内部自行获取存活战斗角色列表

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """

    # 打牌需要在战斗中，并且必须有未完成的回合
    if not tcg_game.current_dungeon.is_ongoing:
        error_msg = "激活打牌动作失败: 只能在战斗中使用is_ongoing"
        logger.error(error_msg)
        return False, error_msg

    # 判断当前是否有未完成的回合
    last_round = tcg_game.current_dungeon.latest_round
    if last_round is None or last_round.is_round_completed:
        error_msg = "激活打牌动作失败: 当前没有未完成的回合可供打牌"
        logger.error(error_msg)
        return False, error_msg

    # 确保所有角色都有后备牌（如果没有玩家指定的牌了，系统会自动提供一张后备牌，保证流程继续）
    success, message = _ensure_all_actors_have_fallback_cards(tcg_game)
    if not success:
        return False, f"激活打牌动作失败: {message}"

    player_entity = tcg_game.get_player_entity()
    assert player_entity is not None, "activate_play_cards: player_entity is None"

    alive_combat_actor_entities = _get_alive_expedition_members_in_stage(
        player_entity, tcg_game
    ) + _get_alive_enemies_in_stage(player_entity, tcg_game)

    # 一个个验证，提前发现问题避免部分成功的尴尬
    for actor_entity in alive_combat_actor_entities:

        # 验证角色有手牌组件且有可用手牌
        assert actor_entity.has(
            HandComponent
        ), f"Entity {actor_entity.name} must have HandComponent"
        if not actor_entity.has(HandComponent):
            error_msg = f"激活打牌动作失败: 角色 {actor_entity.name} 没有手牌组件"
            logger.error(error_msg)
            return False, error_msg

        hand_comp = actor_entity.get(HandComponent)

        # 验证手牌组件中有可用的手牌
        assert (
            len(hand_comp.cards) > 0
        ), f"激活打牌动作失败: 角色 {actor_entity.name} 手牌组件异常"
        if len(hand_comp.cards) == 0:
            error_msg = f"激活打牌动作失败: 角色 {actor_entity.name} 没有可用手牌"
            logger.error(error_msg)
            return False, error_msg

    # 为所有角色添加打牌动作（取第一张手牌）
    for actor_entity in alive_combat_actor_entities:

        hand_comp = actor_entity.get(HandComponent)
        selected_card = hand_comp.cards[0]
        actor_entity.replace(
            PlayCardsAction,
            actor_entity.name,
            selected_card,
            selected_card.targets,  # 后续这里可以换掉 让客户端决定,作为出牌。
        )

    return True, "成功激活打牌动作"


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
def _ensure_all_actors_have_fallback_cards(
    tcg_game: TCGGame,
) -> Tuple[bool, str]:
    """
    为所有缺少手牌的存活角色提供兜底卡牌。

    这是一个保障机制，通常在抽牌阶段结束时调用，确保所有参战角色都有可用手牌。
    如果某个角色缺少HandComponent（可能因为LLM响应解析失败、网络问题等原因），
    将为其生成一张"应急应对"卡牌，避免战斗流程中断。

    兜底卡牌特性：
    - 名称：应急应对
    - 行动：暂时采取保守策略观察战局
    - 战术：本回合不进行任何攻击或防御加成
    - 数值：攻击0、防御0
    - 目标：自己

    Args:
        tcg_game: TCG游戏实例，内部自行获取存活战斗角色列表和当前回合编号

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """

    # 验证战斗状态（由调用方 activate_play_cards 已验证，此处保留防御性检查）
    if not tcg_game.current_dungeon.is_ongoing:
        error_msg = "_ensure_all_actors_have_fallback_cards 只能在战斗中使用is_ongoing"
        logger.error(error_msg)
        return False, error_msg

    # 判断当前是否有未完成的回合
    last_round = tcg_game.current_dungeon.latest_round
    if last_round is None or last_round.is_round_completed:
        error_msg = "当前没有未完成的回合可供打牌"
        logger.error(error_msg)
        return False, error_msg

    player_entity = tcg_game.get_player_entity()
    assert (
        player_entity is not None
    ), "_ensure_all_actors_have_fallback_cards: player_entity is None"

    alive_combat_actor_entities = _get_alive_expedition_members_in_stage(
        player_entity, tcg_game
    ) + _get_alive_enemies_in_stage(player_entity, tcg_game)
    current_round_number = len(tcg_game.current_dungeon.current_rounds or [])

    assert current_round_number >= 0, "current_round_number must be non-negative"
    fallback_count = 0
    for combat_actor_entity in alive_combat_actor_entities:

        # 跳过已有手牌或已死亡的角色
        if combat_actor_entity.has(HandComponent):
            logger.debug(f"角色 {combat_actor_entity.name} 已有手牌，跳过兜底卡牌添加")
            continue

        assert not combat_actor_entity.has(
            DeathComponent
        ), f"角色 {combat_actor_entity.name} 已死亡，无法添加兜底卡牌"
        if combat_actor_entity.has(DeathComponent):
            logger.debug(f"角色 {combat_actor_entity.name} 已死亡，跳过兜底卡牌添加")
            continue

        # 兜底卡牌的目标固定为自己
        fallback_action = "暂时采取保守策略观察战局"
        fallback_mechanism = "本回合不进行任何攻击或防御加成"

        # 创建兜底卡牌
        fallback_card = Card2(
            name="应急应对",
            action=fallback_action,
            damage=0,
            block=0,
            targets=[combat_actor_entity.name],
        )

        # 添加手牌组件
        combat_actor_entity.replace(
            HandComponent,
            combat_actor_entity.name,
            [fallback_card],
            current_round_number,
        )

        # 添加压缩提示词到上下文
        fallback_prompt = f"""# 指令！第 {current_round_number} 回合：生成战斗卡牌(JSON)

**卡牌**封装行动信息，由战斗系统结算。"""

        # 添加上下文。
        tcg_game.add_human_message(
            entity=combat_actor_entity,
            message_content=fallback_prompt,
            draw_cards_round_number=current_round_number,
        )

        # 直接构造 JSON 字符串并添加 AI 消息
        fallback_json = f"""```json
{{
  "name": "应急应对",
  "action": "{fallback_action}",
  "mechanism": "{fallback_mechanism}",
  "cost": "",
  "final_attack": 0,
  "final_defense": 0
}}
```"""
        tcg_game.add_ai_message(
            combat_actor_entity,
            [
                AIMessage(
                    content=fallback_json, draw_cards_round_number=current_round_number
                )
            ],
        )

        fallback_count += 1
        logger.info(f"为角色 {combat_actor_entity.name} 添加兜底卡牌")

    if fallback_count == 0:
        return True, "所有角色都已有手牌，无需兜底"

    return True, f"成功为 {fallback_count} 个角色添加兜底卡牌"


###################################################################################################################################################################
