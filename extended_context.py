
from entitas import Entity, Matcher, Context
from components import WorldComponent, StageComponent, NPCComponent, PlayerComponent

class ExtendedContext(Context):

    #
    def __init__(self):
        super().__init__()

    #
    def getworld(self) -> Entity:
        for entity in self.get_group(Matcher(WorldComponent)).entities:
            return entity
        return None
    
    def getstage(self, name: str) -> Entity:
        for entity in self.get_group(Matcher(StageComponent)).entities:
            comp = entity.get(StageComponent)
            if comp.name == name:
                return entity
        return None
    
    def getnpc(self, name: str) -> Entity:
        for entity in self.get_group(Matcher(NPCComponent)).entities:
            comp = entity.get(NPCComponent)
            if comp.name == name:
                return entity
        return None
    

    def getplayer(self) -> Entity:
        for entity in self.get_group(Matcher(PlayerComponent)).entities:
            return entity
        return None
    

    def getstage_by_entity(self, entity: Entity) -> StageComponent:
        if entity.has(StageComponent):
            return entity.get(StageComponent)

        elif entity.has(NPCComponent):
            current_stage_name = entity.get(NPCComponent).current_stage
            for stage in self.context.get_group(Matcher(StageComponent)).entities:
                if stage.get(StageComponent).name == current_stage_name:
                    return stage.get(StageComponent)
        return None