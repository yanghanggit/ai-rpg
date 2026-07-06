"""Actor 外观查询模块。

提供 get_actor_appearances_in_stage 全局函数，用于获取场景内 Actor 的外观映射。
"""

from typing import Dict
from ..entitas import Entity
from ..models import AppearanceComponent
from .rpg_game import RPGGame


###############################################################################################################################################
def get_actor_appearances_in_stage(game: RPGGame, entity: Entity) -> Dict[str, str]:
    """获取场景上 Actor 的外观信息映射。

    仅返回具有 AppearanceComponent 的 Actor 的外观信息。
    常用于生成场景描述或增强消息内容。

    Args:
        game: RPG 游戏实例
        entity: Stage 实体或 Actor 实体

    Returns:
        Dict[str, str]: 角色名称到外观描述的映射 {角色名: 外观描述}
    """
    ret: Dict[str, str] = {}
    for actor in game.get_actors_in_stage(entity):
        if actor.has(AppearanceComponent):
            final_appearance = actor.get(AppearanceComponent)
            ret.setdefault(final_appearance.name, final_appearance.appearance)
    return ret


###############################################################################################################################################
