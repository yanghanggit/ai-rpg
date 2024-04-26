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
        # 发生对话类行为的人
        for entity in entities:
            logger.debug(f"react: {entity}")
####################################################################################################
    def union_stage_and_npc_dialogue_action_register(self) -> List[Any]:
         unionactions = List(Set(NPC_DIALOGUE_ACTIONS_REGISTER) | Set(STAGE_DIALOGUE_ACTIONS_REGISTER))
         return unionactions
####################################################################################################       