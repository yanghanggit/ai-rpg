from math import log
from typing import final, override
from ..entitas import Entity, GroupEvent, Matcher
from ..game_systems.base_action_reactive_system import BaseActionReactiveSystem
from ..models import (
    QueryAction,
    QueryEvent,
)
from ..chroma import get_chroma_db
from ..rag import rag_semantic_search
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
        logger.success("🕵️‍♂️ 处理 QueryAction")
