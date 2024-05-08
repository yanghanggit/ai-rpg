from auxiliary.file_def import KnownNPCFile, KnownStageFile
from entitas import Entity, Matcher, InitializeProcessor # type: ignore
from auxiliary.components import WorldComponent, StageComponent, NPCComponent
from auxiliary.cn_builtin_prompt import (read_archives_when_system_init_prompt,
                                    read_all_neccesary_info_when_system_init_prompt,
                                    remember_begin_before_game_start_prompt,
                                    check_status_before_game_start_prompt,
                                    remember_npc_archives_before_game_start_prompt,
                                    confirm_current_stage_before_game_start_prompt,
                                    confirm_stages_before_game_start_prompt,
                                    remember_end_before_game_start_prompt,
                                    notify_game_start_prompt)
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from systems.known_information_helper import KnownInformationHelper
from typing import cast


###############################################################################################################################################
class InitMemorySystem(InitializeProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
###############################################################################################################################################
    def initialize(self) -> None:
        logger.debug("<<<<<<<<<<<<<  InitMemorySystem  >>>>>>>>>>>>>>>>>")
        self.initmemory()
###############################################################################################################################################
    def initmemory(self) -> None:
        #
        context = self.context
        helper = KnownInformationHelper(context)
        helper.build()
        #分段处理
        self.handleworld(helper)
        self.handlestages(helper)
        self.handlenpcs(helper)
        ##最后并发执行
        context.agent_connect_system.run_async_requet_tasks()
###############################################################################################################################################
    def handleworld(self, helper: KnownInformationHelper) -> None:
        context = self.context
        memory_system = context.memory_system
        agent_connect_system = context.agent_connect_system
        worlds: set[Entity] = context.get_group(Matcher(WorldComponent)).entities
        for world in worlds:
            worldcomp: WorldComponent = world.get(WorldComponent)
            worldmemory = memory_system.getmemory(worldcomp.name)
            if worldmemory == "":
                logger.error(f"worldmemory is empty: {worldcomp.name}")
                continue
            readarchprompt = read_archives_when_system_init_prompt(worldmemory, world, context)
            agent_connect_system.add_async_requet_task(worldcomp.name, readarchprompt)
###############################################################################################################################################
    def handlestages(self, helper: KnownInformationHelper) -> None:
        context = self.context
        memory_system = context.memory_system
        agent_connect_system = context.agent_connect_system
        stages: set[Entity] = context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            stagecomp: StageComponent = stage.get(StageComponent)
            stagememory = memory_system.getmemory(stagecomp.name)
            if stagememory == "":
                logger.error(f"stagememory is empty: {stagecomp.name}")
                continue
            readarchprompt = read_archives_when_system_init_prompt(stagememory, stage, context)
            agent_connect_system.add_async_requet_task(stagecomp.name, readarchprompt)
###############################################################################################################################################
    def handlenpcs(self, helper: KnownInformationHelper) -> None:
        #
        context = self.context
        memory_system = context.memory_system
        agent_connect_system = context.agent_connect_system

        #测试用
        batch_by_step_then_request = True

        # 初始化npc的
        npcs: set[Entity] = context.get_group(Matcher(all_of=[NPCComponent])).entities
        for npcentity in npcs:
            npccomp: NPCComponent = npcentity.get(NPCComponent)
            npcname: str = npccomp.name
           
            # 知道的npc
            info_who_you_know = helper.who_do_you_know(npccomp.name)
            self.add_known_npc_file(npccomp.name, info_who_you_know)

            # 知道的舞台
            info_where_you_know = helper.where_do_you_know(npccomp.name)
            self.add_known_stage_file(npccomp.name, info_where_you_know)

            # 可以去的舞台
            info_where_you_can_go = info_where_you_know.copy()
            info_where_you_can_go.discard(npccomp.current_stage)

            #切成字符串，给read_all_neccesary_info_when_system_init_prompt            
            str_props_info = ""
            propslist = helper.get_npcs_with_props_info(npccomp.name)
            if len(propslist) > 0:
                str_props_info = "\n".join(propslist)
            
            str_where_you_can_go = ""
            if len(info_where_you_can_go) > 0:
                str_where_you_can_go = ",".join(info_where_you_can_go)

            str_who_you_know = ""
            if len(info_who_you_know) > 0:
                str_who_you_know = ",".join(info_who_you_know)

            #
            str_init_memory = memory_system.getmemory(npcname)

            ## 测试的分值，可以逐条压入history，然后最后request
            if batch_by_step_then_request:
                self.batch_message_remember_begin(npcentity, npcname, str_init_memory)
                self.batch_message_check_status(npcentity, npcname, str_props_info)
                self.batch_message_stages(npcentity, npcname, cast(str, npccomp.current_stage), str_where_you_can_go)
                self.batch_message_npc_archive(npcentity, npcname, str_who_you_know)
                self.batch_message_remember_end(npcentity, npcname)
                request_prompt = notify_game_start_prompt(npcname, context)
                #
                agent_connect_system.add_async_requet_task(npcname, request_prompt)
            else:
                # 旧的执行方式
                readarchprompt = read_all_neccesary_info_when_system_init_prompt(str_init_memory, 
                                                                                str_props_info, 
                                                                                cast(str, npccomp.current_stage),
                                                                                str_where_you_can_go, 
                                                                                str_who_you_know)
                #
                agent_connect_system.add_async_requet_task(npcname, readarchprompt)
###############################################################################################################################################
    def batch_message_remember_begin(self, entity: Entity, npcname: str, memorycontent: str) -> None:
        prompt = remember_begin_before_game_start_prompt(npcname, memorycontent, self.context)
        self.context.safe_add_human_message_to_entity(entity, prompt)
###############################################################################################################################################
    def batch_message_check_status(self, entity: Entity, npcname: str, propsinfo: str) -> None:
        prompt = check_status_before_game_start_prompt(npcname, propsinfo, self.context)
        self.context.safe_add_human_message_to_entity(entity, prompt)
###############################################################################################################################################
    def batch_message_npc_archive(self, entity: Entity, npcname: str, who_you_know: str) -> None:
        prompt = remember_npc_archives_before_game_start_prompt(npcname, who_you_know, self.context)
        self.context.safe_add_human_message_to_entity(entity, prompt)
###############################################################################################################################################
    def batch_message_stages(self, entity: Entity, npcname: str, current_stage_name: str, stages_names: str) -> None:
        #当前场景
        current_stage_prompt = confirm_current_stage_before_game_start_prompt(npcname, current_stage_name, self.context)
        self.context.safe_add_human_message_to_entity(entity, current_stage_prompt)
        #其他场景
        stages_prompt = confirm_stages_before_game_start_prompt(npcname, stages_names, self.context)
        self.context.safe_add_human_message_to_entity(entity, stages_prompt)
###############################################################################################################################################
    def batch_message_remember_end(self, entity: Entity, npcname: str) -> None:
        prompt = remember_end_before_game_start_prompt(npcname, self.context)
        self.context.safe_add_human_message_to_entity(entity, prompt)
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