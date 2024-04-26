from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import WorldComponent, NPCComponent, StageComponent, NPC_DIALOGUE_ACTIONS_REGISTER, STAGE_DIALOGUE_ACTIONS_REGISTER
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from typing import Dict, List, Set, Any

####################################################################################################
class PostConversationalActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
####################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        unionactions = self.union_stage_and_npc_dialogue_action_register()
        trigger: Dict[Matcher, GroupEvent] = {}
        for action in unionactions:
            trigger[Matcher(action)] = GroupEvent.ADDED
        return trigger
####################################################################################################
    def filter(self, entity: Entity) -> bool:
        # 能做对话的交互的只有这几个人
        return entity.has(WorldComponent) or entity.has(NPCComponent) or entity.has(StageComponent)
####################################################################################################
    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  PostConversationalActionSystem  >>>>>>>>>>>>>>>>>")
        for entity in entities:
            self.log_conversational_action(entity)
####################################################################################################
    def union_stage_and_npc_dialogue_action_register(self) -> List[Any]:
         unionactions = List(Set(NPC_DIALOGUE_ACTIONS_REGISTER) | Set(STAGE_DIALOGUE_ACTIONS_REGISTER))
         return unionactions    
####################################################################################################
    # 只关注对话行为，并打印出来
    def log_conversational_action(self, entity: Entity) -> None:
        name = self.context.safe_get_entity_name(entity)
        logger.debug(f"log_conversational_action: {name}, {'=' * 50}")
        actions = self.union_stage_and_npc_dialogue_action_register()
        for action in actions:
            if entity.has(action):
                logger.debug(f"{action}")
        logger.debug(f"{'=' * 100}")
        pass
####################################################################################################       