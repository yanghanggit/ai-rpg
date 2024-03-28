
from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.components import StageComponent, NPCComponent, DirectorComponent
from typing import List
from auxiliary.extended_context import ExtendedContext
from auxiliary.prompt_maker import confirm_everything_after_director_add_new_memories_prompt
from loguru import logger
from director import Director



# matcher = Matcher(all_of=[CompA, CompB, CompC],
#                   any_of=[CompD, CompE],
#                   none_of=[CompF])



class DirectorSystem(ExecuteProcessor):

    def __init__(self, context: ExtendedContext) -> None:
        self.context = context

    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  DirectorSystem  >>>>>>>>>>>>>>>>>")
        self.handle()
        self.clear()

    def handle(self) -> None:
 
        entities = self.context.get_group(Matcher(all_of=[StageComponent, DirectorComponent])).entities
        for entity in entities:
            self.handlestage(entity)
           
    
    def clear(self) -> None:
        entities = self.context.get_group(Matcher(all_of=[StageComponent, DirectorComponent])).entities
        for entity in entities:
            ### 原始的！！！
            comp = entity.get(StageComponent)
            comp.directorscripts.clear()
            ### 重构的！！！
            directorcomp = entity.get(DirectorComponent)
            director: Director = directorcomp.director
            director.clear()


    def handlestage(self, entitystage: Entity) -> None:

        stagecomp: StageComponent = entitystage.get(StageComponent)
        logger.debug(f"[{stagecomp.name}] 开始导演+++++++++++++++++++++++++++++++++++++++++++++++++++++")

        directorscripts: list[str] = stagecomp.directorscripts
        if len(directorscripts) == 0:
            return

        npcs_in_stage = self.context.get_npcs_in_stage(stagecomp.name)
        npcs_names = " ".join([npc.get(NPCComponent).name for npc in npcs_in_stage])

        confirm_prompt = confirm_everything_after_director_add_new_memories_prompt(directorscripts, npcs_names, stagecomp.name, self.context)
        logger.debug(f"记忆添加内容:\n{confirm_prompt}\n")

        self.context.add_agent_memory(entitystage, confirm_prompt)
        for npcen in npcs_in_stage:
            self.context.add_agent_memory(npcen, confirm_prompt)

        logger.debug(f"[{stagecomp.name}] 结束导演+++++++++++++++++++++++++++++++++++++++++++++++++++++")


        ### 重构的测试????????
        directorcomp: DirectorComponent = entitystage.get(DirectorComponent)
        director: Director = directorcomp.director
        for npcen in npcs_in_stage:
            npcmem = director.convert(npcen.get(NPCComponent).name, self.context)
            logger.debug(f"npcmem:{npcmem}")
    