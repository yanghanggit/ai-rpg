from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import (NPCComponent, StageComponent)
from typing import Set

class CompressChatHistorySystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def execute(self) -> None:
        context = self.context
        agent_connect_system = context.agent_connect_system
        tags: Set[str] = {"<%角色与场景初始化>", "<%角色计划>", "<%场景计划>"}
        entities: set[Entity] = context.get_group(Matcher(any_of=[NPCComponent, StageComponent])).entities
        for entity in entities:
            safename = context.safe_get_entity_name(entity)
            if safename == "":
                continue
            agent_connect_system.exclude_chat_history(safename, tags)
############################################################################################################