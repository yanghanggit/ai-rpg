
from entitas import Matcher,ExecuteProcessor
from components import DestroyComponent
   
class DestroySystem(ExecuteProcessor):
    
    def __init__(self, context) -> None:
        self.context = context

    def execute(self) -> None:
        print("<<<<<<<<<<<<<  DestroySystem  >>>>>>>>>>>>>>>>>")
        entities = self.context.get_group(Matcher(DestroyComponent)).entities
        for entity in entities:
             self.context.destroy_entity(entity)



    