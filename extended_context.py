
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
    

    def get_stagecomponent_by_uncertain_entity(self, entity: Entity) -> StageComponent:
        if entity.has(StageComponent):
            return entity.get(StageComponent)

        elif entity.has(NPCComponent):
            current_stage_name = entity.get(NPCComponent).current_stage
            for stage in self.get_group(Matcher(StageComponent)).entities:
                if stage.get(StageComponent).name == current_stage_name:
                    return stage.get(StageComponent)
        return None
        
    def show_stages_log(self) -> str:

        stagesentities = self.get_group(Matcher(StageComponent)).entities
        npcsentities = self.get_group(Matcher(NPCComponent)).entities
        map: dict[str, list[str]] = {}

        for entity in stagesentities:
            stagecomp = entity.get(StageComponent)
            ls = map.get(stagecomp.name, [])
            map[stagecomp.name] = ls

            for entity in npcsentities:
                npccomp = entity.get(NPCComponent)
                if npccomp.current_stage == stagecomp.name:
                    ls.append(npccomp.name)
        return map




        
    