"""战斗流程处理模块。

提供战斗相关的完整流程函数，包括零血量实体处理、死亡通知、DeathComponent 挂载，
以及回合行动顺序计算（get_current_turn_actor / advance_turn）。
作为模块级函数供 systems 层直接调用。
"""

import random
from typing import List, Optional, Set
from loguru import logger
from ..entitas import Entity, Matcher
from ..models import (
    CharacterStatsComponent,
    DeathComponent,
    HumanMessage,
    Round,
    PartyMemberComponent,
    MonsterComponent,
)
from .dbg_game import DBGGame
from .dbg_entity_ops import compute_character_stats


#################################################################################################################################################
def _format_zero_health_message() -> str:
    """生成 HP 归零时发送给角色的通知消息"""
    return "# 你的HP已归零，失去战斗能力！"


#################################################################################################################################################
def process_zero_health_entities(game: DBGGame) -> None:
    """为 HP 归零且尚未标记死亡的实体添加 DeathComponent。

    Args:
        game: DBG 游戏实例
    """
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
    """从最新回合快照中找出第一个尚未 pass turn 的角色名。

    行动权的推进完全由 `round.completed_actors`（已明确 pass turn 的角色）决定，
    与 energy 是否耗尽无关：即使角色 energy 已耗尽，也必须显式 pass turn 才会
    交出行动权（Slay the Spire 式“手动结束回合”）。
    途中死亡但尚未 pass turn 的角色会被跳过，避免其永久卡住行动顺序。

    Args:
        game: DBG 游戏实例
        round: 当前战斗回合

    Returns:
        当前应行动的角色名；若快照中所有角色均已 pass turn（或已死亡）则返回 None
    """
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
    """消耗 energy 后重新计算当前 turn 行动者，并写回 round.current_turn_actor_name。

    在每次出牌或过牌消耗 energy 之后调用，保持 Round 模型中 current_turn_actor_name 的最新状态。

    Args:
        game: DBG 游戏实例
        round: 当前战斗回合
    """
    round.current_actor = get_current_turn_actor(game, round)
    logger.debug(
        f"advance_turn: current_turn_actor_name updated to {round.current_actor}"
    )


#################################################################################################################################################
def get_alive_actors_in_stage(game: DBGGame, entity: Entity) -> Set[Entity]:
    """获取指定场景上存活的 Actor 实体。

    过滤掉带有 DeathComponent 的 Actor，只返回活着的 Actor。

    Args:
        game: DBG 游戏实例
        entity: Stage 实体或 Actor 实体

    Returns:
        Set[Entity]: 该场景上存活的 Actor 实体集合（不包括已死亡的）
    """
    ret = game.get_actors_in_stage(entity)
    return {actor for actor in ret if not actor.has(DeathComponent)}


#################################################################################################################################################
def pick_spread_targets(enemies: List[Entity], hit_count: int) -> List[Entity]:
    """按 hit_count 与候选敌人数量的关系，选取"散射"命中列表（ENEMY_SPREAD 专用）。

    - hit_count > 敌人数量：保证每个敌人至少命中一次，多出的次数随机补齐，最终整体打乱顺序。
    - hit_count <= 敌人数量（含相等）：直接随机抽取（不保证覆盖，允许重复或遗漏）。

    Args:
        enemies: 候选敌人实体列表（通常为场上全部存活敌方）
        hit_count: 命中次数

    Returns:
        List[Entity]: 长度为 hit_count 的命中目标列表（enemies 为空时返回空列表）
    """
    if not enemies:
        return []

    if hit_count > len(enemies):
        assigned = list(enemies) + random.choices(enemies, k=hit_count - len(enemies))
        random.shuffle(assigned)
        return assigned

    return random.choices(enemies, k=hit_count)


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
