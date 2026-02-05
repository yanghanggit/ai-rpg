"""游戏保存系统模块。

本模块实现了游戏的保存功能，负责在游戏运行时保存游戏状态。
系统会收集当前场景中所有角色的分布信息，并记录它们的状态（如死亡状态），
然后触发游戏上下文的保存操作。
"""

import json
from typing import Dict, Final, List, final, override
from loguru import logger
from ..models.components import (
    DeathComponent,
)
from ..entitas import ExecuteProcessor, Entity
from ..game.rpg_game import RPGGame


@final
class SaveSystem(ExecuteProcessor):
    """游戏保存系统。

    该系统负责执行游戏的保存操作，在保存时会记录当前所有场景中
    角色的分布情况及其状态信息，然后调用游戏上下文的保存方法。

    Attributes:
        _game: 游戏上下文实例，包含游戏的核心状态和数据。
    """

    ############################################################################################################
    def __init__(self, game_context: RPGGame) -> None:
        self._game: Final[RPGGame] = game_context

    ############################################################################################################
    @override
    async def execute(self) -> None:
        # 记录当前场景中的所有角色分布
        self._log_actor_distribution()

        # 保存游戏状态
        self._game.save_game()

    ############################################################################################################
    def _log_actor_distribution(self) -> None:
        """记录当前各场景中的角色分布情况

        获取所有场景及其中的角色，格式化为 JSON 并记录到日志。
        """
        actor_distribution = self._game.get_actors_by_stage()

        actor_distribution_info: Dict[str, List[str]] = {}
        for stage, actors in actor_distribution.items():
            actor_distribution_info[stage.name] = [
                self._format_entity_name_with_status(actor) for actor in actors
            ]

        logger.warning(
            f"mapping = {json.dumps(actor_distribution_info, indent=2, ensure_ascii=False)}"
        )

    ############################################################################################################
    def _format_entity_name_with_status(self, entity: Entity) -> str:
        """格式化实体名称并附加状态标签。

        根据实体的组件状态生成包含状态信息的名称字符串。
        如果实体具有特殊状态（如死亡），会在名称后添加相应的标签。

        Args:
            entity: 要格式化的实体对象。

        Returns:
            格式化后的实体名称字符串。如果实体有状态标签，
            返回格式为 "实体名称(标签1 & 标签2)"，否则仅返回实体名称。
        """
        tags = []

        if entity.has(DeathComponent):
            tags.append("dead")

        if len(tags) == 0:
            return entity.name
        else:
            return f"{entity.name}({' & '.join(tags)})"

    ############################################################################################################
