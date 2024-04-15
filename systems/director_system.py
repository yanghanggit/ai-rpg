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
        self.must_clear_director_data()
###################################################################################################################
    def handle(self) -> None:
        entities = self.context.get_group(Matcher(all_of=[StageComponent, DirectorComponent])).entities
        for entity in entities:
            self.handlestage(entity)
            self.handle_npcs_in_this_stage(entity)
###################################################################################################################   
    def must_clear_director_data(self) -> None:
        entities = self.context.get_group(Matcher(all_of=[StageComponent, DirectorComponent])).entities
        for entity in entities:
            directorcomp: DirectorComponent = entity.get(DirectorComponent)
            directorcomp.clear()
###################################################################################################################
    ### 重构用的。用新的Director类来处理, 转化成场景事件，加入到场景的消息列表中
    def handlestage(self, entitystage: Entity) -> None:
        stagecomp: StageComponent = entitystage.get(StageComponent)
        directorcomp: DirectorComponent = entitystage.get(DirectorComponent)
        convertedevents2stage = directorcomp.tostage(stagecomp.name, self.context)         
        stagememlist = "\n".join(convertedevents2stage)
        if len(stagememlist) > 0:
            self.context.safe_add_human_message_to_entity(entitystage, stagememlist)
###################################################################################################################
    ### 重构用的。用新的Director类来处理，转化成NPC事件，加入到NPC的消息列表中
    def handle_npcs_in_this_stage(self, entitystage: Entity) -> None:
        stagecomp: StageComponent = entitystage.get(StageComponent)
        allnpcsinthestage = self.context.npcs_in_this_stage(stagecomp.name)
        directorcomp: DirectorComponent = entitystage.get(DirectorComponent)
        for npcentity in allnpcsinthestage:
            npccomp: NPCComponent = npcentity.get(NPCComponent)
            convertedevents2npc = directorcomp.tonpc(npccomp.name, self.context)            
            npcmemlist = "\n".join(convertedevents2npc)
            if len(npcmemlist) > 0:
                self.context.safe_add_human_message_to_entity(npcentity, npcmemlist)
###################################################################################################################
    