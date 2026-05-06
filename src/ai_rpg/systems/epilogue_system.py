"""Pipeline 末端收尾系统，记录角色分布并同步实体状态到 world 模型。"""

import json
from typing import Dict, Final, List, final, override
from loguru import logger
from ..models.components import (
    DeathComponent,
)
from ..entitas import ExecuteProcessor, Entity
from ..game.rpg_game import RPGGame


@final
class EpilogueSystem(ExecuteProcessor):
    """Pipeline 末端收尾系统。

    记录角色分布日志并将实体状态同步回 world 模型。未来可在此扩展收尾检查。
    """

    ############################################################################################################
    def __init__(self, game: RPGGame) -> None:
        self._game: Final[RPGGame] = game

    ############################################################################################################
    @override
    async def execute(self) -> None:

        # 记录当前场景中的所有角色分布
        self._log_actor_distribution()

        # 保存游戏状态
        self._game.flush_entities()

    ############################################################################################################
    def _log_actor_distribution(self) -> None:
        """记录各场景中的角色分布情况到日志。"""
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
        """返回实体名称，若有状态标签（如 dead）则附加在括号内。

        Args:
            entity: 要格式化的实体。

        Returns:
            格式如 "name" 或 "name(dead)"。
        """
        tags = []

        if entity.has(DeathComponent):
            tags.append("dead")

        if len(tags) == 0:
            return entity.name
        else:
            return f"{entity.name}({' & '.join(tags)})"

    ############################################################################################################
