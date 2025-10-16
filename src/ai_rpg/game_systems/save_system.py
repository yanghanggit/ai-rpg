import asyncio
import json
from typing import Dict, List, final, override
from loguru import logger
from ..models.components import (
    DeathComponent,
    NightKillComponent,
    DayDiscussionComponent,
    NightPlanComponent,
    DayVoteComponent,
)
from ..entitas import ExecuteProcessor, Entity
from ..game.tcg_game import TCGGame


@final
class SaveSystem(ExecuteProcessor):

    ############################################################################################################
    def __init__(self, game_context: TCGGame) -> None:
        self._game: TCGGame = game_context

    ############################################################################################################
    @override
    async def execute(self) -> None:

        # 保存时，打印当前场景中的所有角色
        actor_distribution: Dict[Entity, List[Entity]] = (
            self._game.get_stage_actor_distribution()
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
        # self._game.save()
        logger.debug("开始保存游戏...")
        await asyncio.to_thread(self._game.save)

    ############################################################################################################
    def _format_entity_name_with_status(self, entity: Entity) -> str:
        tags = []

        if entity.has(DeathComponent):
            tags.append("dead")

        if entity.has(NightPlanComponent):
            tags.append("night-planned")

        if entity.has(NightKillComponent):
            tags.append("night-killed")

        if entity.has(DayDiscussionComponent):
            tags.append("day-discussed")

        if entity.has(DayVoteComponent):
            tags.append("day-voted")

        if len(tags) == 0:
            return entity.name
        else:
            return f"{entity.name}({' & '.join(tags)})"

    ############################################################################################################
