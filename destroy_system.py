
from entitas import Matcher, ExecuteProcessor, Group, Context, Entity
from components import DestroyComponent
   
class DestroySystem(ExecuteProcessor):
    
    def __init__(self, context) -> None:
        self.context:Context = context

    def execute(self) -> None:
        print("<<<<<<<<<<<<<  DestroySystem  >>>>>>>>>>>>>>>>>")
        entityGroup: Group = self.context.get_group(Matcher(DestroyComponent))
        entities:set[Entity] = entityGroup.entities
        
        entities_copy = entities.copy()
        while len(entities_copy) > 0:
             destory_entity = entities_copy.pop() 
             self.context.destroy_entity(destory_entity)



    