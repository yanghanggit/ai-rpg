from typing import override
from entitas import ExecuteProcessor, Matcher #type: ignore
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from systems.components import STAGE_AVAILABLE_ACTIONS_REGISTER, ACTOR_AVAILABLE_ACTIONS_REGISTER, StageComponent, ActorComponent
   
class PostActionSystem(ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    @override
    def execute(self) -> None:
        # 在这里清除所有的行动
        self.remove_actor_actions()
        self.remove_stage_actions()
        self.test()
############################################################################################################
    def remove_stage_actions(self) -> None:
        entities = self.context.get_group(Matcher(all_of = [StageComponent], any_of = STAGE_AVAILABLE_ACTIONS_REGISTER)).entities.copy()
        for entity in entities:
            #logger.debug(f"remove_stage_actions: {entity}")
            for actionsclass in STAGE_AVAILABLE_ACTIONS_REGISTER:
                if entity.has(actionsclass):
                    entity.remove(actionsclass)
############################################################################################################
    def remove_actor_actions(self) -> None:
        entities = self.context.get_group(Matcher(all_of = [ActorComponent], any_of = ACTOR_AVAILABLE_ACTIONS_REGISTER)).entities.copy()
        for entity in entities:
            for actionsclass in ACTOR_AVAILABLE_ACTIONS_REGISTER:
                if entity.has(actionsclass):
                    entity.remove(actionsclass)
############################################################################################################
    def test(self) -> None:
        stageentities = self.context.get_group(Matcher(any_of = STAGE_AVAILABLE_ACTIONS_REGISTER)).entities
        assert len(stageentities) == 0, f"Stage entities with actions: {stageentities}"
        actor_entities = self.context.get_group(Matcher(any_of = ACTOR_AVAILABLE_ACTIONS_REGISTER)).entities
        assert len(actor_entities) == 0, f"Actor entities with actions: {actor_entities}"
############################################################################################################

            

