
from entitas import Matcher,ExecuteProcessor,Group,Context,Entity
from components import DestroyComponent
   
class DestroySystem(ExecuteProcessor):
    entities_to_remove = list[Entity]
    
    def __init__(self, context) -> None:
        self.context:Context = context
        self.entities_to_remove: list[Entity] = []

    def execute(self) -> None:
        print("<<<<<<<<<<<<<  DestroySystem  >>>>>>>>>>>>>>>>>")
        entityGroup: Group = self.context.get_group(Matcher(DestroyComponent))
        entities:set[Entity] = entityGroup.entities

        for entity in entities:
             self.context.destroy_entity(entity)
             self.entities_to_remove.append(entity)

        for item in self.entities_to_remove:
            item.destroy()



    