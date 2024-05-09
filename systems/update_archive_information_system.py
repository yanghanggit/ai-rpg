from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import (NPCComponent)
from typing import Set
from auxiliary.file_def import KnownStageFile
from systems.known_information_helper import KnownInformationHelper
from auxiliary.cn_builtin_prompt import known_information_update_who_you_know_prompt, known_information_update_where_you_know_prompt
from auxiliary.file_system_helper import create_npc_archive_files

class UpdateArchiveInformationSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  KnownInformationSystem.execute >>>>>>>>>>>>>>>>>")
        self.knowninformation()
############################################################################################################
    def knowninformation(self) -> None:
        # 建立数据
        context = self.context
        known_info_helper = KnownInformationHelper(self.context)
        known_info_helper.build()
        # 对NPC进行处理
        npcs: set[Entity] = context.get_group(Matcher(all_of=[NPCComponent])).entities
        for npc in npcs:
            self.update_npc_information(npc, known_info_helper)
            self.update_stage_information(npc, known_info_helper)
############################################################################################################
    def update_npc_information(self, npcentity: Entity, helper: KnownInformationHelper) -> None:
        #context = self.context
        npccomp: NPCComponent = npcentity.get(NPCComponent)
        who_do_you_know: set[str] = helper.who_do_you_know(npccomp.name)
        if len(who_do_you_know) == 0:
            logger.warning(f"{npccomp.name} 什么人都不认识，这个合理么？")
            return
        
        # 写文件
        create_npc_archive_files(self.context.file_system, npccomp.name, who_do_you_know)        

        # 更新chat history
        who_do_you_know_promt = ",".join(who_do_you_know)
        newmsg = known_information_update_who_you_know_prompt(npccomp.name, who_do_you_know_promt)
        self.context.safe_add_human_message_to_entity(npcentity, newmsg)
############################################################################################################
    def update_stage_information(self, npcentity: Entity, helper: KnownInformationHelper) -> None:
        npccomp: NPCComponent = npcentity.get(NPCComponent)
        where_do_you_know: set[str] = helper.where_do_you_know(npccomp.name)
        if len(where_do_you_know) == 0:
            logger.warning(f"{npccomp.name} 什么地点都不知道，这个合理么？")
            return
        
        # 写文件
        self.add_known_stage_file(npccomp.name, where_do_you_know)

        # 更新chat history
        where_do_you_know_promt = ",".join(where_do_you_know)
        newmsg = known_information_update_where_you_know_prompt(npccomp.name, where_do_you_know_promt)
        self.context.safe_add_human_message_to_entity(npcentity, newmsg)
############################################################################################################
    def add_known_stage_file(self, filesowner: str, allnames: Set[str]) -> None:
        file_system = self.context.file_system
        for stagename in allnames:
            if filesowner == stagename:
                continue
            file = KnownStageFile(stagename, filesowner, stagename)
            file_system.add_known_stage_file(file)
############################################################################################################
    