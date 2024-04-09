from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.components import StageComponent, NPCComponent
from auxiliary.extended_context import ExtendedContext
from auxiliary.prompt_maker import confirm_everything_after_director_add_new_memories_prompt
from loguru import logger
from auxiliary.director_component import DirectorComponent

class DirectorSystem(ExecuteProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        self.context = context

    def execute(self) -> None:

        logger.debug("<<<<<<<<<<<<<  DirectorSystem  >>>>>>>>>>>>>>>>>")
        self.handle()
        self.must_clear_director_data()

    def handle(self) -> None:
 
        entities = self.context.get_group(Matcher(all_of=[StageComponent, DirectorComponent])).entities
        for entity in entities:
            self.handlestage(entity)
            self.director_handle_stage(entity)
           
    def must_clear_director_data(self) -> None:
        
        entities = self.context.get_group(Matcher(all_of=[StageComponent, DirectorComponent])).entities
        for entity in entities:
            ### 原始的！！！
            comp = entity.get(StageComponent)
            comp.directorscripts.clear()
            ### 重构的！！！
            directorcomp: DirectorComponent = entity.get(DirectorComponent)
            #director: Director = directorcomp.director
            directorcomp.clear()

    def handlestage(self, entitystage: Entity) -> None:

        stagecomp: StageComponent = entitystage.get(StageComponent)
        logger.debug(f"[{stagecomp.name}] 开始导演+++++++++++++++++++++++++++++++++++++++++++++++++++++")

        directorscripts: list[str] = stagecomp.directorscripts
        if len(directorscripts) == 0:
            return

        npcs_in_stage = self.context.npcs_in_this_stage(stagecomp.name)
        npcs_names = " ".join([npc.get(NPCComponent).name for npc in npcs_in_stage])

        confirm_prompt = confirm_everything_after_director_add_new_memories_prompt(directorscripts, npcs_names, stagecomp.name, self.context)
        logger.debug(f"记忆添加内容:\n{confirm_prompt}\n")

        self.context.add_human_message_to_entity(entitystage, confirm_prompt)
        for npcen in npcs_in_stage:
            self.context.add_human_message_to_entity(npcen, confirm_prompt)
        logger.debug(f"[{stagecomp.name}] 结束导演+++++++++++++++++++++++++++++++++++++++++++++++++++++")


    ### 重构用的。用新的Director类来处理
    def director_handle_stage(self, entitystage: Entity) -> None:

        stagecomp: StageComponent = entitystage.get(StageComponent)
        allnpcsinthestage = self.context.npcs_in_this_stage(stagecomp.name)

        directorcomp: DirectorComponent = entitystage.get(DirectorComponent)
        #director: Director = directorcomp.director

        for npcen in allnpcsinthestage:
            npccomp: NPCComponent = npcen.get(NPCComponent)
            convertedevents2npc = directorcomp.convert(npccomp.name, self.context)            
            npcmemlist = "\n".join(convertedevents2npc)
            logger.debug(f"refactor npcmemlist: {npcmemlist}")
            

    