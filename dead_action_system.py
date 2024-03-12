
from entitas import Matcher,ExecuteProcessor
from components import DeadActionComponent


class DeadActionSystem(ExecuteProcessor):
    
    def __init__(self, context) -> None:
        self.context = context

    def execute(self) -> None:
        print("<<<<<<<<<<<<<  DeadActionSystem >>>>>>>>>>>>>>>>>")
        entities = self.context.get_group(Matcher(DeadActionComponent)).entities
        for entity in entities:
             comp = entity.get(DeadActionComponent)
             print(comp.cause)

    