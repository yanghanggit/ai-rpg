
from entitas import Entity, Matcher, ExecuteProcessor #type: ignore
from auxiliary.components import StageComponent, NPCComponent, DirectorComponent
from typing import List
from auxiliary.extended_context import ExtendedContext
from auxiliary.prompt_maker import confirm_everything_after_director_add_new_memories_prompt
from loguru import logger
from director import Director

class DirectorSystem(ExecuteProcessor):

    def __init__(self, context: ExtendedContext) -> None:

        self.context = context

    def execute(self) -> None:
 
        logger.debug("<<<<<<<<<<<<<  DirectorSystem  >>>>>>>>>>>>>>>>>")
        self.handle()
        self.clear()

    def handle(self) -> None:
 
        entities = self.context.get_group(Matcher(StageComponent)).entities
        for entity in entities:
            self.handlestage(entity)
           
    
    def clear(self) -> None:

        entities = self.context.get_group(Matcher(StageComponent)).entities
        for entity in entities:
            comp = entity.get(StageComponent)
            comp.directorscripts.clear()
            ### 重构的！！！
            directorcomp = entity.get(DirectorComponent)
            directorcomp.director.clear()


    def handlestage(self, entitystage: Entity) -> None:

        stage_comp: StageComponent = entitystage.get(StageComponent)
        logger.debug(f"[{stage_comp.name}] 开始导演+++++++++++++++++++++++++++++++++++++++++++++++++++++")

        directorscripts: list[str] = stage_comp.directorscripts
        if len(directorscripts) == 0:
            return

        npcs_in_stage = self.context.get_npcs_in_stage(stage_comp.name)
        npcs_names = " ".join([npc.get(NPCComponent).name for npc in npcs_in_stage])

        confirm_prompt = confirm_everything_after_director_add_new_memories_prompt(directorscripts, npcs_names, stage_comp.name, self.context)
        logger.debug(f"记忆添加内容:\n{confirm_prompt}\n")

        self.context.add_agent_memory(entitystage, confirm_prompt)
        for npcen in npcs_in_stage:
            self.context.add_agent_memory(npcen, confirm_prompt)

        logger.debug(f"[{stage_comp.name}] 结束导演+++++++++++++++++++++++++++++++++++++++++++++++++++++")