from typing import final, override

# from ai_rpg.game_systems import query_action
from ..entitas import Entity, GroupEvent, Matcher
from ..game_systems.base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    QueryAction,
)
from loguru import logger


#####################################################################################################################################
@final
class QueryActionSystem(BaseActionReactiveSystem):

    #############################################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(QueryAction): GroupEvent.ADDED}

    #############################################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(QueryAction)

    #############################################################################################################################
    @override
    async def react(self, entities: list[Entity]) -> None:
        for entity in entities:
            self._process_action(entity)

    #############################################################################################################################
    def _process_action(self, entity: Entity) -> None:
        query_action = entity.get(QueryAction)
        assert query_action is not None

        logger.success(f"🔎 角色发起查询行动，问题: {query_action.question}")
