from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from ecs_systems.components import (ActorComponent, StageComponent)
from typing import Set, override, Dict
from builtin_prompt.cn_constant_prompt import _CNConstantPrompt_

class CompressChatHistorySystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self._context: ExtendedContext = context
############################################################################################################
    @override
    def execute(self) -> None:
        # 这个很有危险
        #self.handle_exclude_chat_history()
        self.handle_compress_chat_history()
############################################################################################################
    def handle_exclude_chat_history(self) -> None:
        context = self._context
        tags: Set[str] = {_CNConstantPrompt_.ACTOR_PLAN_PROMPT_TAG, _CNConstantPrompt_.STAGE_PLAN_PROMPT_TAG}
        entities: Set[Entity] = context.get_group(Matcher(any_of=[ActorComponent, StageComponent])).entities
        for entity in entities:
            safename = context.safe_get_entity_name(entity)
            if safename == "":
                continue
            context._langserve_agent_system.exclude_content_then_rebuild_chat_history(safename, tags)
############################################################################################################
    def handle_compress_chat_history(self) -> None:
        context = self._context
        replace_data: Dict[str, str] = { _CNConstantPrompt_.ACTOR_PLAN_PROMPT_TAG : _CNConstantPrompt_.COMPRESS_ACTOR_PLAN_PROMPT, 
                                        _CNConstantPrompt_.STAGE_PLAN_PROMPT_TAG : _CNConstantPrompt_.COMPRESS_STAGE_PLAN_PROMPT}
        entities: Set[Entity] = context.get_group(Matcher(any_of=[ActorComponent, StageComponent])).entities
        for entity in entities:
            safename = context.safe_get_entity_name(entity)
            if safename == "":
                continue
            context._langserve_agent_system.replace_chat_history(safename, replace_data)
############################################################################################################