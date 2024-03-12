
from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent
from components import TagActionComponent
from actor_action import ActorAction
from extended_context import ExtendedContext

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################   
class TagActionSystem(ReactiveProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self):
        return {Matcher(TagActionComponent): GroupEvent.ADDED}

    def filter(self, entity: list[Entity]):
        return entity.has(TagActionComponent)

    def react(self, entities: list[Entity]):
        print("<<<<<<<<<<<<<  TagActionSystem  >>>>>>>>>>>>>>>>>")
        self.handle(entities)
        #必须移除！！！！！
        for entity in entities:
            entity.remove(TagActionComponent)    

    ###############################################################################################################################################
    def handle(self, entities: list[Entity]) -> None:
        for entity in entities:
            tagcomp = entity.get(TagActionComponent)
            #print("tag_action ===== >", tagcomp.action)
    ###############################################################################################################################################