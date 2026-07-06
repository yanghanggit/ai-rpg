"""战斗流程处理模块。

提供战斗相关的完整流程函数，包括零血量实体处理、死亡通知、DeathComponent 挂载，
以及回合行动顺序计算（get_current_turn_actor / advance_turn）。
作为模块级函数供 systems 层直接调用。
"""

from typing import Optional, Set
from loguru import logger
from ..entitas import Entity, Matcher
from ..models import (
    CharacterStatsComponent,
    DeathComponent,
    HumanMessage,
    Round,
)
from .dbg_game import DBGGame
from .dbg_entity_ops import compute_character_stats, get_energy


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
    """从最新回合快照中找出第一个仍有行动力（energy > 0）的角色名。

    Args:
        game: DBG 游戏实例
        round: 当前战斗回合

    Returns:
        当前应行动的角色名；若所有角色能量耗尽则返回 None
    """
    if not round.actor_order_snapshots:
        return None

    snapshot = round.actor_order_snapshots[-1]
    for actor_name in snapshot:
        actor_entity = game.get_actor_entity(actor_name)
        assert actor_entity is not None, f"无法找到角色实体: {actor_name}"
        if get_energy(actor_entity) > 0:
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
    round.current_turn_actor_name = get_current_turn_actor(game, round)
    logger.debug(
        f"advance_turn: current_turn_actor_name updated to {round.current_turn_actor_name}"
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
