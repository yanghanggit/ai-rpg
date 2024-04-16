from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent # type: ignore
from auxiliary.components import MindVoiceActionComponent
from auxiliary.actor_action import ActorAction
from auxiliary.extended_context import ExtendedContext
from auxiliary.print_in_color import Color
from loguru import logger

####################################################################################################
class MindVoiceActionSystem(ReactiveProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context
####################################################################################################
    def get_trigger(self) -> dict[Matcher, GroupEvent]:
        return {Matcher(MindVoiceActionComponent): GroupEvent.ADDED}
####################################################################################################
    def filter(self, entity: Entity) -> bool:
        return entity.has(MindVoiceActionComponent)
####################################################################################################
    def react(self, entities: list[Entity]) -> None:
        logger.debug("<<<<<<<<<<<<<  MindVoiceActionSystem  >>>>>>>>>>>>>>>>>")
        # 核心处理
        for entity in entities:
            self.mindvoice(entity)      
####################################################################################################
    def mindvoice(self, entity: Entity) -> None:
        mindvoicecomp: MindVoiceActionComponent = entity.get(MindVoiceActionComponent)
        action: ActorAction = mindvoicecomp.action
        for value in action.values:
            what_to_said = f"debug!! [mindvoice]:{action.name} = {value}"
            logger.debug(f"{Color.BLUE}{what_to_said}{Color.ENDC}") #目前还是测试
 ####################################################################################################       
                