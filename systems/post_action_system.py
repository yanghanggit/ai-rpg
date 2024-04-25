from entitas import ExecuteProcessor, Matcher #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import STAGE_AVAILABLE_ACTIONS_REGISTER, NPC_AVAILABLE_ACTIONS_REGISTER, WorldComponent, StageComponent, NPCComponent
   
class PostActionSystem(ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  PostActionSystem  >>>>>>>>>>>>>>>>>")
        # 在这里清除所有的行动
        self.remove_world_actions() # 因为world和npc的actions，目前是一样的
        self.remove_npc_actions()
        self.remove_stage_actions()
        self.test()
############################################################################################################
    def remove_world_actions(self) -> None:
        entities = self.context.get_group(Matcher(all_of = [WorldComponent], any_of = NPC_AVAILABLE_ACTIONS_REGISTER)).entities.copy()
        for entity in entities:
            logger.debug(f"remove_world_actions: {entity}")
            for actionsclass in NPC_AVAILABLE_ACTIONS_REGISTER:
                if entity.has(actionsclass):
                    entity.remove(actionsclass)
############################################################################################################
    def remove_stage_actions(self) -> None:
        entities = self.context.get_group(Matcher(all_of = [StageComponent], any_of = STAGE_AVAILABLE_ACTIONS_REGISTER)).entities.copy()
        for entity in entities:
            logger.debug(f"remove_stage_actions: {entity}")
            for actionsclass in STAGE_AVAILABLE_ACTIONS_REGISTER:
                if entity.has(actionsclass):
                    entity.remove(actionsclass)
############################################################################################################
    def remove_npc_actions(self) -> None:
        entities = self.context.get_group(Matcher(all_of = [NPCComponent], any_of = NPC_AVAILABLE_ACTIONS_REGISTER)).entities.copy()
        for entity in entities:
            logger.debug(f"remove_npc_actions: {entity}")
            for actionsclass in NPC_AVAILABLE_ACTIONS_REGISTER:
                if entity.has(actionsclass):
                    entity.remove(actionsclass)
############################################################################################################
    def test(self) -> None:
        stageentities = self.context.get_group(Matcher(any_of = STAGE_AVAILABLE_ACTIONS_REGISTER)).entities
        assert len(stageentities) == 0, f"Stage entities with actions: {stageentities}"
        npcentities = self.context.get_group(Matcher(any_of = NPC_AVAILABLE_ACTIONS_REGISTER)).entities
        assert len(npcentities) == 0, f"NPC entities with actions: {npcentities}"
############################################################################################################

            

