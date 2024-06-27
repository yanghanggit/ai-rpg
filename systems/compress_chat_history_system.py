from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import (ActorComponent, StageComponent)
from typing import Set, override, Dict
from builtin_prompt.cn_builtin_prompt import __ConstantPromptValue__

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
        tags: Set[str] = {__ConstantPromptValue__.ACTOR_PLAN_PROMPT_TAG, __ConstantPromptValue__.STAGE_PLAN_PROMPT_TAG}
        entities: Set[Entity] = context.get_group(Matcher(any_of=[ActorComponent, StageComponent])).entities
        for entity in entities:
            safename = context.safe_get_entity_name(entity)
            if safename == "":
                continue
            agent_connect_system.exclude_chat_history(safename, tags)
############################################################################################################
    def handle_compress_chat_history(self) -> None:
        context = self.context
        agent_connect_system = context.agent_connect_system
        replace_data: Dict[str, str] = { __ConstantPromptValue__.ACTOR_PLAN_PROMPT_TAG : __ConstantPromptValue__.COMPRESS_ACTOR_PLAN_PROMPT, 
                                        __ConstantPromptValue__.STAGE_PLAN_PROMPT_TAG : __ConstantPromptValue__.COMPRESS_STAGE_PLAN_PROMPT}
        entities: Set[Entity] = context.get_group(Matcher(any_of=[ActorComponent, StageComponent])).entities
        for entity in entities:
            safename = context.safe_get_entity_name(entity)
            if safename == "":
                continue
            agent_connect_system.replace_chat_history(safename, replace_data)
############################################################################################################