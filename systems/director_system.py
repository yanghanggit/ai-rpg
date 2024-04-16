from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.components import StageComponent, NPCComponent
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.director_component import DirectorComponent

class DirectorSystem(ExecuteProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        self.context = context
###################################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  DirectorSystem  >>>>>>>>>>>>>>>>>")
        self.handle()
        self.directorclear()
###################################################################################################################
    def handle(self) -> None:
        entities = self.context.get_group(Matcher(all_of=[StageComponent, DirectorComponent])).entities
        for entity in entities:
            self.handlestage(entity)
            self.handle_npcs_in_this_stage(entity)
###################################################################################################################   
    def directorclear(self) -> None:
        entities = self.context.get_group(Matcher(all_of=[StageComponent, DirectorComponent])).entities
        for entity in entities:
            directorcomp: DirectorComponent = entity.get(DirectorComponent)
            directorcomp.clear()
###################################################################################################################
    def handlestage(self, entitystage: Entity) -> None:
        assert entitystage.has(StageComponent)
        stagecomp: StageComponent = entitystage.get(StageComponent)
        directorcomp: DirectorComponent = entitystage.get(DirectorComponent)
        events2stage = directorcomp.tostage(stagecomp.name, self.context)         
        newmsg = "\n".join(events2stage)
        if len(newmsg) > 0:
            self.context.safe_add_human_message_to_entity(entitystage, newmsg)
###################################################################################################################
    def handle_npcs_in_this_stage(self, entitystage: Entity) -> None:
        assert entitystage.has(StageComponent)
        stagecomp: StageComponent = entitystage.get(StageComponent)
        allnpcsinthestage = self.context.npcs_in_this_stage(stagecomp.name)
        directorcomp: DirectorComponent = entitystage.get(DirectorComponent)
        for npcentity in allnpcsinthestage:
            npccomp: NPCComponent = npcentity.get(NPCComponent)
            events2npc = directorcomp.tonpc(npccomp.name, self.context)            
            newmsg = "\n".join(events2npc)
            if len(newmsg) > 0:
                self.context.safe_add_human_message_to_entity(npcentity, newmsg)
###################################################################################################################
    