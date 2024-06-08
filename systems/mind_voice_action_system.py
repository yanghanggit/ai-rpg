from typing import override
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import MindVoiceActionComponent
from auxiliary.actor_plan_and_action import ActorAction
from auxiliary.extended_context import ExtendedContext
#from auxiliary.print_in_color import Color
from loguru import logger

####################################################################################################
class MindVoiceActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
####################################################################################################
    @override
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(MindVoiceActionComponent): GroupEvent.ADDED}
####################################################################################################
    @override
    def filter(self, entity: Entity) -> bool:
        return entity.has(MindVoiceActionComponent)
####################################################################################################
    @override
    def react(self, entities: list[Entity]) -> None:
        # 核心处理
        for entity in entities:
            self.mindvoice(entity)      
####################################################################################################
    def mindvoice(self, entity: Entity) -> None:
        pass
        # mindvoicecomp: MindVoiceActionComponent = entity.get(MindVoiceActionComponent)
        # action: ActorAction = mindvoicecomp.action
        # combine = action.single_value()
        #logger.debug(f"debug!! [mindvoice]:{action.name} = {combine}")
 ####################################################################################################       
                