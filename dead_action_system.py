
from entitas import Matcher,ExecuteProcessor
from components import DeadActionComponent, LeaveActionComponent, TagActionComponent, DestroyComponent
from extended_context import ExtendedContext


class DeadActionSystem(ExecuteProcessor):
    
    def __init__(self, context: ExtendedContext) -> None:
        self.context = context

    def execute(self) -> None:
        print("<<<<<<<<<<<<<  DeadActionSystem  >>>>>>>>>>>>>>>>>")
        entities = self.context.get_group(Matcher(DeadActionComponent)).entities
        for entity in entities:
            if entity.has(LeaveActionComponent):
                entity.remove(LeaveActionComponent)
             
            if entity.has(TagActionComponent):
                entity.remove(TagActionComponent)
            
            if not entity.has(DestroyComponent):
                entity.add(DestroyComponent)

        
             
            
        


    