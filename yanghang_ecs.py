###
### 测试与LLM无关的代码，和一些尝试
###
# import json
# from builder import WorldBuilder, StageBuilder, NPCBuilder



from collections import namedtuple
from entitas import Entity, Matcher, Context, Processors, ExecuteProcessor, ReactiveProcessor, GroupEvent, InitializeProcessor, Group
import time

Position = namedtuple('Position', 'x y')
Health = namedtuple('Health', 'value')
Movable = namedtuple('Movable', '')




###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
ActorComponent = namedtuple('ActorComponent', 'name')
WorldComponent = namedtuple('WorldComponent', 'name')
StageComponent = namedtuple('StageComponent', 'name')
NPCComponent = namedtuple('NPCComponent', 'name')
LoadEventComponent = namedtuple('LoadEventComponent', 'load_script')
AutoPlanComponent = namedtuple('AutoPlanComponent', 'plan_prompt')
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class MyInitializeProcessor(InitializeProcessor):

    def __init__(self, context: Context) -> None:
        self.context: Context = context
      
    def initialize(self) -> None:

        worlds: set = self.context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            print(world.get(WorldComponent).name)
            world.add(LoadEventComponent, "load world")

        stages: Group = self.context.get_group(Matcher(StageComponent))
        for stage in stages.entities:
            print(stage.get(StageComponent).name)
            stage.add(LoadEventComponent, "load stage")
            stage.add(AutoPlanComponent, "auto plan")

        npcs: Group = self.context.get_group(Matcher(NPCComponent))
        for npc in npcs.entities:
            print(npc.get(NPCComponent).name)
            npc.add(LoadEventComponent, "load npc")
            npc.add(AutoPlanComponent, "auto plan")

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
############################################################################################################################################### 
class MyReactiveProcessor(ReactiveProcessor):

    def __init__(self, context) -> None:
        super().__init__(context)
        self.context = context

    def get_trigger(self):
        return {Matcher(LoadEventComponent): GroupEvent.ADDED}

    def filter(self, entity):
        return entity.has(LoadEventComponent)

    def react(self, entities):
        print("<<<<<<<<<<<<<  LoadEventComponent >>>>>>>>>>>>>>>>>")
        for entity in entities:
            print(entity.get(LoadEventComponent).load_script)

###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################       
class MyExecuteProcessor(ExecuteProcessor):
    
    def __init__(self, context) -> None:
        self.context = context

    def execute(self) -> None:
        print("<<<<<<<<<<<<<  MyExecuteProcessor >>>>>>>>>>>>>>>>>")
        entities = self.context.get_group(Matcher(ActorComponent, AutoPlanComponent)).entities
        for entity in entities:
            print(entity.get(AutoPlanComponent).plan_prompt)
            print(entity.get(ActorComponent).name)


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################           
def main() -> None:
    context = Context()
    processors = Processors()

    entity = context.create_entity()
    entity.add(Position, 3, 7)
    entity.add(Movable)

    world_entity = context.create_entity() 
    world_entity.add(ActorComponent, "<world>")
    world_entity.add(WorldComponent, "<world>")

    stage_entity = context.create_entity()
    stage_entity.add(ActorComponent, "<stage>")
    stage_entity.add(StageComponent, "<stage>")

    npc_entity = context.create_entity()
    npc_entity.add(ActorComponent, "<npc>")      
    npc_entity.add(NPCComponent, "<npc>")  

        



    print("beginning...")
    processors.add(MyInitializeProcessor(context))
    processors.add(MyReactiveProcessor(context))
    processors.add(MyExecuteProcessor(context))
    processors.activate_reactive_processors()
    processors.initialize()
    processors.execute()
    processors.cleanup()
    processors.clear_reactive_processors()
    processors.tear_down()
    print("end.")
    
if __name__ == "__main__":
    main()