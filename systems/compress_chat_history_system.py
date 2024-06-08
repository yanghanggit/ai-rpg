from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import (ActorComponent, StageComponent)
from typing import Set, override, Dict
from auxiliary.cn_builtin_prompt import ACTOR_PLAN_PROMPT_TAG, STAGE_PLAN_PROMPT_TAG, COMPRESS_ACTOR_PLAN_PROMPT, COMPRESS_STAGE_PLAN_PROMPT

class CompressChatHistorySystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    @override
    def execute(self) -> None:
        # 这个很有危险
        #self.handle_exclude_chat_history()
        self.handle_compress_chat_history()
############################################################################################################
    def handle_exclude_chat_history(self) -> None:
        context = self.context
        agent_connect_system = context.agent_connect_system
        tags: Set[str] = {ACTOR_PLAN_PROMPT_TAG, STAGE_PLAN_PROMPT_TAG}
        entities: set[Entity] = context.get_group(Matcher(any_of=[ActorComponent, StageComponent])).entities
        for entity in entities:
            safename = context.safe_get_entity_name(entity)
            if safename == "":
                continue
            agent_connect_system.exclude_chat_history(safename, tags)
############################################################################################################
    def handle_compress_chat_history(self) -> None:
        context = self.context
        agent_connect_system = context.agent_connect_system
        replace_data: Dict[str, str] = { ACTOR_PLAN_PROMPT_TAG : COMPRESS_ACTOR_PLAN_PROMPT, STAGE_PLAN_PROMPT_TAG : COMPRESS_STAGE_PLAN_PROMPT}
        entities: set[Entity] = context.get_group(Matcher(any_of=[ActorComponent, StageComponent])).entities
        for entity in entities:
            safename = context.safe_get_entity_name(entity)
            if safename == "":
                continue
            agent_connect_system.replace_chat_history(safename, replace_data)
############################################################################################################