
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
    
    def get_npcs_in_stage(self, stage_name: str) -> list[Entity]:   
        npcs = []
        for entity in self.get_group(Matcher(NPCComponent)).entities:
            comp = entity.get(NPCComponent)
            if comp.current_stage == stage_name:
                npcs.append(entity)
        return npcs
    

    def getplayer(self) -> Entity:
        for entity in self.get_group(Matcher(PlayerComponent)).entities:
            return entity
        return None
    

    def get_stage_by_entity(self, entity: Entity) -> StageComponent:
        if entity.has(StageComponent):
            return entity.get(StageComponent)

        elif entity.has(NPCComponent):
            current_stage_name = entity.get(NPCComponent).current_stage
            for stage in self.get_group(Matcher(StageComponent)).entities:
                if stage.get(StageComponent).name == current_stage_name:
                    return stage.get(StageComponent)
        return None
    
    def add_stage_events(self, name: str, content: str) -> None:
        entity = self.getstage(name)
        if entity is not None:
            comp = entity.get(StageComponent)
            comp.events.append(content)
            return
        
    def get_stage_events(self, name: str) -> list[str]:
        entity = self.getstage(name)
        if entity is not None:
            comp = entity.get(StageComponent)
            return comp.events
        return []
    
    def showstages(self) -> str:

        stagesentities = self.get_group(Matcher(StageComponent)).entities
        npcsentities = self.get_group(Matcher(NPCComponent)).entities
        map: dict[str, list[str]] = {}

        for entity in stagesentities:
            comp = entity.get(StageComponent)
            ls = map.get(comp.name, [])
            map[comp.name] = ls

            for entity in npcsentities:
                comp = entity.get(NPCComponent)
                if comp.current_stage == comp.name:
                    ls.append(comp.name)
        return map




        
    