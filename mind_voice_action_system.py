
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent
from components import MindVoiceActionComponent
from actor_action import ActorAction
from extended_context import ExtendedContext
from agents.tools.print_in_color import Color

class MindVoiceActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self):
        return {Matcher(MindVoiceActionComponent): GroupEvent.ADDED}

    def filter(self, entity: list[Entity]):
        return entity.has(MindVoiceActionComponent)

    def react(self, entities: list[Entity]):

        print("<<<<<<<<<<<<<  MindVoiceActionComponent  >>>>>>>>>>>>>>>>>")

        # 核心处理
        for entity in entities:
            self.handle(entity)
            
        # 必须移除！！！
        for entity in entities:
            entity.remove(MindVoiceActionComponent)         

    def handle(self, entity: Entity) -> None:
        mindvoicecomp = entity.get(MindVoiceActionComponent)
        stagecomp = self.context.get_stagecomponent_by_uncertain_entity(entity)
        if stagecomp is None or mindvoicecomp is None:
            return
        action: ActorAction = mindvoicecomp.action
        for value in action.values:
            what_to_said = f"{action.name},心里想到:{value}"
            print(f"{Color.BLUE}{what_to_said}{Color.ENDC}")
            #stagecomp.directorscripts.append(what_to_said) # 先不往场景时间里面添加，因为这个是内心的想法，不是说出来的话
            
        
                