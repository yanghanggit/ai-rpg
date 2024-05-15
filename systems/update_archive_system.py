from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import (NPCComponent)
from systems.update_archive_helper import UpdareArchiveHelper
from auxiliary.cn_builtin_prompt import updated_information_on_WhoDoYouKnow_prompt, updated_information_about_StagesYouKnow_prompt
from auxiliary.file_system_helper import add_npc_archive_files, update_npc_archive_file, add_stage_archive_files

class UpdateArchiveSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def execute(self) -> None:
        self.update_archive()
############################################################################################################
    def update_archive(self) -> None:
        # 建立数据
        context = self.context
        known_info_helper = UpdareArchiveHelper(self.context)
        known_info_helper.prepare()
        # 对NPC进行处理
        npcs: set[Entity] = context.get_group(Matcher(all_of=[NPCComponent])).entities
        for npc in npcs:
            #更新NPC的NPC档案，可能更新了谁认识谁，还有如果在场景中，外观是什么
            self.update_npc_archive(npc, known_info_helper)
            #更新NPC的场景档案，
            self.update_stage_archive(npc, known_info_helper)
############################################################################################################
    def update_npc_archive(self, npcentity: Entity, helper: UpdareArchiveHelper) -> None:
        #
        npccomp: NPCComponent = npcentity.get(NPCComponent)
        who_do_you_know: set[str] = helper.who_do_you_know(npccomp.name)
        if len(who_do_you_know) == 0:
            logger.warning(f"{npccomp.name} 什么人都不认识，这个合理么？")
            return
        
        # 补充文件，有可能是新的人，也有可能全是旧的人
        add_npc_archive_files(self.context.file_system, npccomp.name, who_do_you_know)        

        # 更新文件，只更新场景内我能看见的人
        appearance_data = self.context.npc_appearance_in_the_stage(npcentity)
        for name in who_do_you_know:
            appearance = appearance_data.get(name, "")
            if appearance != "":
                update_npc_archive_file(self.context.file_system, npccomp.name, name, appearance)

        # 更新chat history
        who_do_you_know_promt = ",".join(who_do_you_know)
        message = updated_information_on_WhoDoYouKnow_prompt(npccomp.name, who_do_you_know_promt)
        self.context.agent_connect_system.exclude_chat_history(npccomp.name, set(message))
        self.context.safe_add_human_message_to_entity(npcentity, message)
############################################################################################################
    def update_stage_archive(self, npcentity: Entity, helper: UpdareArchiveHelper) -> None:
        npccomp: NPCComponent = npcentity.get(NPCComponent)
        _stages_you_know: set[str] = helper.stages_you_know(npccomp.name)
        if len(_stages_you_know) == 0:
            logger.warning(f"{npccomp.name} 什么地点都不知道，这个合理么？")
            return
        
        # 写文件
        add_stage_archive_files(self.context.file_system, npccomp.name, _stages_you_know)

        # 更新chat history
        _stages_you_know_prompt = ",".join(_stages_you_know)
        message = updated_information_about_StagesYouKnow_prompt(npccomp.name, _stages_you_know_prompt)
        self.context.agent_connect_system.exclude_chat_history(npccomp.name, set(message))
        self.context.safe_add_human_message_to_entity(npcentity, message)
############################################################################################################
    