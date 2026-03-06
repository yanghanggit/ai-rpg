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
    SkillBookComponent,
    ExpeditionMemberComponent,
    EnemyComponent,
    CombatStatsComponent,
    DeathComponent,
    Card,
    CharacterStats,
    InventoryComponent,
    Round,
)
from ..entitas import Entity, Matcher
from langchain_core.messages import AIMessage


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
def get_alive_expedition_members_on_stage(
    anchor_entity: Entity, tcg_game: TCGGame
) -> List[Entity]:
    """获取锹点实体所在场景中所有存活的远征队成员

    以 anchor_entity 定位其所在场景，然后在该场景中筛选所有带
    ExpeditionMemberComponent 的存活实体。玩家实体是常用的锹点，
    但任意处于场景中的实体均可作为 anchor。

    Args:
        anchor_entity: 用于定位场景的锹点实体
        tcg_game: TCG游戏实例

    Returns:
        存活的远征队成员实体列表
    """
    actor_entities = tcg_game.get_alive_actors_on_stage(anchor_entity)
    return [
        entity for entity in actor_entities if entity.has(ExpeditionMemberComponent)
    ]


###################################################################################################################################################################
def get_alive_enemies_on_stage(
    anchor_entity: Entity, tcg_game: TCGGame
) -> List[Entity]:
    """获取锹点实体所在场景中所有存活的敌方

    以 anchor_entity 定位其所在场景，然后在该场景中筛选所有带
    EnemyComponent 的存活实体。

    Args:
        anchor_entity: 用于定位场景的锹点实体
        tcg_game: TCG游戏实例

    Returns:
        存活的敌方实体列表
    """
    actor_entities = tcg_game.get_alive_actors_on_stage(anchor_entity)
    return [entity for entity in actor_entities if entity.has(EnemyComponent)]


###################################################################################################################################################################
def filter_valid_targets(
    anchor_entity: Entity, tcg_game: TCGGame, target_names: List[str]
) -> List[Entity]:
    """从候选目标名称中筛选出当前场景里存活的角色实体

    以 anchor_entity 定位场景，返回名称在 target_names 中且仍然存活的实体列表。
    已死亡或不在场的目标会被自动过滤掉。

    Args:
        anchor_entity: 用于定位场景的锚点实体
        tcg_game: TCG游戏实例
        target_names: 候选目标名称列表

    Returns:
        存活且合法的目标实体列表
    """
    target_name_set = set(target_names)
    alive_actor_entities = tcg_game.get_alive_actors_on_stage(anchor_entity)
    return [entity for entity in alive_actor_entities if entity.name in target_name_set]


###################################################################################################################################################################
def activate_random_expedition_member_card_draws(
    expedition_member_entities: List[Entity],
    enemy_entities: List[Entity],
) -> Tuple[bool, str]:
    """
    为指定的远征队成员列表激活抽牌动作（随机选择技能和状态效果）

    Args:
        expedition_member_entities: 需要激活抽牌的远征队成员实体列表
        enemy_entities: 场上存活的敌方实体列表，用于随机选择目标

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """

    assert (
        len(expedition_member_entities) > 0
    ), "activate_random_expedition_member_card_draws: expedition_member_entities is empty"
    if len(expedition_member_entities) == 0:
        error_msg = "激活远征队成员抽牌失败: 没有存活的远征队成员"
        logger.error(error_msg)
        return False, error_msg

    assert (
        len(enemy_entities) > 0
    ), "activate_random_expedition_member_card_draws: enemy_entities is empty"
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
            CombatStatsComponent
        ), f"Entity {entity.name} must have CombatStatsComponent"
        combat_stats = entity.get(CombatStatsComponent)
        status_effects = combat_stats.status_effects.copy()

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
    expedition_member_entity: Entity,
    target_entities: List[Entity],
    skill_name: str,
    status_effect_names: List[str],
) -> Tuple[bool, str]:
    """
    为指定的远征队成员激活抽牌动作（使用指定的技能、目标和状态效果）

    调用方需在调用前完成：entity 查找与存活验证、target_entities 合法性验证（可用
    filter_valid_targets 辅助）。本函数只做组件读写，无 game 依赖。

    Args:
        expedition_member_entity: 出牌者实体（须为远征队成员且存活）
        target_entities: 指定的目标实体列表（调用方保证合法）
        skill_name: 指定的技能名称
        status_effect_names: 指定的状态效果名称列表

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """

    # 检查是否已经有抽牌动作（将被覆盖）
    assert expedition_member_entity.has(
        ExpeditionMemberComponent
    ), f"Entity {expedition_member_entity.name} must have ExpeditionMemberComponent"

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

    # 查找，如果没有就返回错误
    selected_skill = skill_book_comp.find_skill(skill_name)
    if selected_skill is None:
        error_msg = f"激活指定抽牌失败: 角色 {expedition_member_entity.name} 没有技能 '{skill_name}'，可用技能: {[s.name for s in skill_book_comp.skills]}"
        logger.error(error_msg)
        return False, error_msg

    # 2. 验证状态效果名称是否都在实体的当前状态效果中
    assert expedition_member_entity.has(
        CombatStatsComponent
    ), f"Entity {expedition_member_entity.name} must have CombatStatsComponent"
    combat_stats = expedition_member_entity.get(CombatStatsComponent)
    for effect_name in status_effect_names:
        if combat_stats.find_status_effect(effect_name) is None:
            error_msg = f"激活指定抽牌失败: 角色 {expedition_member_entity.name} 没有状态效果 '{effect_name}'，当前状态效果: {[e.name for e in combat_stats.status_effects]}"
            logger.error(error_msg)
            return False, error_msg

    # 3. 创建 DrawCardsAction 组件
    expedition_member_entity.replace(
        DrawCardsAction,
        expedition_member_entity.name,
        selected_skill,  # skill
        [e.name for e in target_entities],  # targets
        status_effect_names,  # 指定的状态效果列表
    )

    return True, f"成功为角色 {expedition_member_entity.name} 激活抽牌动作"


###################################################################################################################################################################
def activate_random_enemy_card_draws(
    enemy_entities: List[Entity],
    expedition_member_entities: List[Entity],
) -> Tuple[bool, str]:
    """
    为指定的敌方列表激活抽牌动作（随机选择技能和状态效果）

    Args:
        enemy_entities: 场上存活的敌方实体列表
        expedition_member_entities: 场上存活的远征队成员实体列表，用于随机选择目标

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """

    assert (
        len(enemy_entities) > 0
    ), "activate_random_enemy_card_draws: enemy_entities is empty"
    if len(enemy_entities) == 0:
        error_msg = "激活Enemy抽牌失败: 没有存活的Enemy角色"
        logger.error(error_msg)
        return False, error_msg

    assert (
        len(expedition_member_entities) > 0
    ), "activate_random_enemy_card_draws: expedition_member_entities is empty"
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
            CombatStatsComponent
        ), f"Entity {entity.name} must have CombatStatsComponent"
        combat_stats = entity.get(CombatStatsComponent)
        status_effects = combat_stats.status_effects.copy()

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

    _current_round = tcg_game.current_combat_sequence.latest_round
    assert _current_round is not None
    if _current_round.is_round_completed:
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
    assert latest_round is not None
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
def mark_expedition_retreat(tcg_game: TCGGame) -> Tuple[bool, str]:
    """
    标记所有远征队成员撤退：为每人添加死亡标记并写入撤退叙事消息。

    本函数只做状态标记与消息写入，不依赖战斗状态。
    调用方在此之后需推进 combat_execution_pipeline，
    由 CombatOutcomeSystem 检测死亡并触发后续失败流程。

    Args:
        tcg_game: TCG游戏实例

    Returns:
        tuple[bool, str]: (True, 结果消息)
    """
    dungeon = tcg_game.world.dungeon
    assert dungeon is not None, "mark_expedition_retreat: dungeon is None"

    expedition_member_entities = tcg_game.get_group(
        Matcher(all_of=[ExpeditionMemberComponent])
    ).entities
    assert (
        len(expedition_member_entities) > 0
    ), "mark_expedition_retreat: no expedition members found"

    for expedition_member_entity in expedition_member_entities:

        assert expedition_member_entity.has(
            ExpeditionMemberComponent
        ), f"Entity {expedition_member_entity.name} must have ExpeditionMemberComponent"

        # 标记为死亡，后续 CombatOutcomeSystem 会检测并触发战斗失败流程
        expedition_member_entity.replace(DeathComponent, expedition_member_entity.name)
        logger.info(f"撤退: 角色 {expedition_member_entity.name} 标记为死亡")

        # 解析所在场景，生成撤退叙事消息并写入上下文
        stage_entity = tcg_game.resolve_stage_entity(expedition_member_entity)
        assert (
            stage_entity is not None
        ), f"无法找到角色 {expedition_member_entity.name} 所在的场景实体"

        retreat_message = _generate_retreat_message(dungeon.name, stage_entity.name)
        tcg_game.add_human_message(
            expedition_member_entity,
            retreat_message,
            dungeon_lifecycle_retreat=f"{dungeon.name}:{stage_entity.name}",
        )

        logger.info(
            f"战斗撤退成功: 地下城={dungeon.name}, 关卡={stage_entity.name}, "
            f"撤退角色数={len(expedition_member_entities)}"
        )

    return (
        True,
        f"已标记 {len(expedition_member_entities)} 个远征队成员撤退，地下城={dungeon.name}",
    )


###################################################################################################################################################################
def ensure_all_actors_have_fallback_cards(
    tcg_game: TCGGame, current_round_number: int, combat_round: Round
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
        tcg_game: TCG游戏实例
        current_round_number: 当前回合编号（用于手牌组件与消息标记）
        combat_round: 当前回合对象（由调用方保证未完成）

    Returns:
        tuple[bool, str]: (是否成功, 结果消息)
    """

    assert current_round_number >= 0, "current_round_number must be non-negative"
    assert not combat_round.is_round_completed, "当前回合已完成，无需兜底手牌"

    if len(combat_round.action_order) == 0:
        logger.warning("当前回合行动队列为空，无需添加兜底卡牌")
        return True, "当前回合行动队列为空，无需添加兜底卡牌"

    fallback_count = 0
    for combat_actor_entity_name in combat_round.action_order:

        combat_actor_entity = tcg_game.get_entity_by_name(combat_actor_entity_name)
        assert (
            combat_actor_entity is not None
        ), f"无法找到角色实体: {combat_actor_entity_name}"
        if combat_actor_entity is None:
            logger.error(
                f"无法找到角色实体: {combat_actor_entity_name}, 跳过兜底卡牌添加"
            )
            continue

        # 跳过已有手牌或已死亡的角色
        if combat_actor_entity.has(HandComponent):
            logger.debug(f"角色 {combat_actor_entity_name} 已有手牌，跳过兜底卡牌添加")
            continue

        if combat_actor_entity.has(DeathComponent):
            logger.debug(f"角色 {combat_actor_entity_name} 已死亡，跳过兜底卡牌添加")
            continue

        # 兜底卡牌的目标固定为自己
        fallback_action = "暂时采取保守策略观察战局"
        fallback_mechanism = "本回合不进行任何攻击或防御加成"

        # 创建兜底卡牌
        fallback_card = Card(
            name="应急应对",
            action=fallback_action,
            stats=CharacterStats(hp=0, max_hp=0, attack=0, defense=0),
            targets=[combat_actor_entity.name],
            status_effects=[],
            affixes=[f"战术：{fallback_mechanism}"],
        )

        # 从InventoryComponent继承物品词条到卡牌词条
        inventory_comp = combat_actor_entity.get(InventoryComponent)
        assert (
            inventory_comp is not None
        ), f"Entity {combat_actor_entity.name} must have InventoryComponent"
        for item in inventory_comp.items:
            fallback_card.affixes.extend(item.affixes)  # 追加装备词条

        # 添加手牌组件
        combat_actor_entity.replace(
            HandComponent,
            combat_actor_entity.name,
            [fallback_card],
            current_round_number,
        )

        # 添加压缩提示词到上下文
        compressed_prompt = f"""# 指令！第 {current_round_number} 回合：生成战斗卡牌(JSON)

**卡牌**封装行动信息，由战斗系统结算。"""
        tcg_game.add_human_message(
            entity=combat_actor_entity,
            message_content=compressed_prompt,
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
