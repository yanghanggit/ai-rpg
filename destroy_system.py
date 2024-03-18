
from entitas import Matcher, ExecuteProcessor, Group, Entity
from components import DestroyComponent
from extended_context import ExtendedContext
   
class DestroySystem(ExecuteProcessor):
    
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context

    def execute(self) -> None:
        print("<<<<<<<<<<<<<  DestroySystem  >>>>>>>>>>>>>>>>>")
        entityGroup: Group = self.context.get_group(Matcher(DestroyComponent))
        entities: set[Entity] = entityGroup.entities
        #不能够一边遍历一边删除，所以先复制一份
        entities_copy = entities.copy()
        while len(entities_copy) > 0:
             destory_entity = entities_copy.pop() 
             self.context.destroy_entity(destory_entity)