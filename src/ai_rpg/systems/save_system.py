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

        # 保存时，打印当前场景中的所有角色
        actor_distribution: Dict[Entity, List[Entity]] = (
            self._game.get_actors_by_stage()
        )

        #
        actor_distribution_info: Dict[str, List[str]] = {}
        for stage, actors in actor_distribution.items():
            actor_distribution_info[stage.name] = []
            for actor in actors:
                actor_distribution_info[stage.name].append(
                    # f"{actor.name}{'(Dead)' if actor.has(DeathComponent) or actor.has(NightKillFlagComponent) else ''}"
                    self._format_entity_name_with_status(actor)
                )

        logger.warning(
            f"mapping = {json.dumps(actor_distribution_info, indent=2, ensure_ascii=False)}"
        )

        # 核心调用
        self._game.save_game()

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
