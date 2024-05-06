from auxiliary.file_def import KnownNPCFile, KnownStageFile
from entitas import Entity, Matcher, InitializeProcessor # type: ignore
from auxiliary.components import WorldComponent, StageComponent, NPCComponent
from auxiliary.cn_builtin_prompt import (read_archives_when_system_init_prompt,
                                    read_all_neccesary_info_when_system_init_prompt)
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from systems.known_information_helper import KnownInformationHelper


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
class InitMemorySystem(InitializeProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
    def initialize(self) -> None:
        logger.debug("<<<<<<<<<<<<<  InitMemorySystem  >>>>>>>>>>>>>>>>>")
        self.initmemory()
###############################################################################################################################################
###############################################################################################################################################
    def initmemory(self) -> None:
        #
        context = self.context
        memory_system = context.memory_system
        agent_connect_system = context.agent_connect_system
        #
        known_info_helper = KnownInformationHelper(context)
        known_info_helper.build()

        # 初始化世界的
        worlds: set[Entity] = context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            worldcomp: WorldComponent = world.get(WorldComponent)
            worldmemory = memory_system.getmemory(worldcomp.name)
            if worldmemory == "":
                logger.error(f"worldmemory is empty: {worldcomp.name}")
                continue
            readarchprompt = read_archives_when_system_init_prompt(worldmemory, world, context)
            agent_connect_system.add_async_requet_task(worldcomp.name, readarchprompt)

        # 初始化舞台的
        stages: set[Entity] = context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            stagecomp: StageComponent = stage.get(StageComponent)
            stagememory = memory_system.getmemory(stagecomp.name)
            if stagememory == "":
                logger.error(f"stagememory is empty: {stagecomp.name}")
                continue
            readarchprompt = read_archives_when_system_init_prompt(stagememory, stage, context)
            agent_connect_system.add_async_requet_task(stagecomp.name, readarchprompt)
        
        # 初始化npc的
        npcs: set[Entity] = context.get_group(Matcher(all_of=[NPCComponent])).entities
        for npc in npcs:
            npccomp: NPCComponent = npc.get(NPCComponent)
           
            # 知道的npc
            who_do_you_know = known_info_helper.who_do_you_know(npccomp.name)
            self.add_known_npc_file(npccomp.name, who_do_you_know)

            # 知道的舞台
            where_do_you_know = known_info_helper.where_do_you_know(npccomp.name)
            self.add_known_stage_file(npccomp.name, where_do_you_know)

            # 可以去的舞台
            where_you_can_go = where_do_you_know.copy()
            where_you_can_go.discard(npccomp.current_stage)

            #切成字符串，给read_all_neccesary_info_when_system_init_prompt            
            props_info_prompt = ""
            listinfo = known_info_helper.get_npcs_with_props_info(npccomp.name)
            if len(listinfo) > 0:
                props_info_prompt = "\n".join(listinfo)
            
            where_you_can_go_prompt = ""
            if len(where_you_can_go) > 0:
                where_you_can_go_prompt = ",".join(where_you_can_go)

            who_do_you_know_prompt = ""
            if len(who_do_you_know) > 0:
                who_do_you_know_prompt = ",".join(who_do_you_know)

            readarchprompt = read_all_neccesary_info_when_system_init_prompt(memory_system.getmemory(npccomp.name), 
                                                                             props_info_prompt, 
                                                                             npccomp.current_stage, 
                                                                             where_you_can_go_prompt, 
                                                                             who_do_you_know_prompt)

            agent_connect_system.add_async_requet_task(npccomp.name, readarchprompt)

        ##最后统一执行
        agent_connect_system.run_async_requet_tasks()
###############################################################################################################################################
    def add_known_stage_file(self, filesowner: str, allnames: set[str]) -> None:
        file_system = self.context.file_system
        for stagename in allnames:
            if filesowner == stagename:
                continue
            file = KnownStageFile(stagename, filesowner, stagename)
            file_system.add_known_stage_file(file)
###############################################################################################################################################
    def add_known_npc_file(self, filesowner: str, allnames: set[str]) -> None:
        file_system = self.context.file_system
        for npcname in allnames:
            if filesowner == npcname:
                continue
            file = KnownNPCFile(npcname, filesowner, npcname)
            file_system.add_known_npc_file(file)
###############################################################################################################################################