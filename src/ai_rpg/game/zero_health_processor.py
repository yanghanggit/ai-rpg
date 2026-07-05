"""零血量实体处理模块。

提供检测并标记 HP 归零实体的完整流程函数，包括死亡通知和 DeathComponent 挂载。
作为模块级函数供 systems 层直接调用。
"""

from loguru import logger
from ..entitas import Matcher
from ..models import (
    CharacterStatsComponent,
    DeathComponent,
    HumanMessage,
)
from .dbg_game import DBGGame
from .entity_ops import compute_character_stats


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
