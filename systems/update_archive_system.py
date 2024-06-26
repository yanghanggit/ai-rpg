from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import (ActorComponent)
from systems.update_archive_helper import UpdareArchiveHelper
from auxiliary.cn_builtin_prompt import update_actor_archive_prompt, update_stage_archive_prompt
from auxiliary.file_system_helper import add_actor_archive_files, update_actor_archive_file, add_stage_archive_files
from typing import Set, override

class UpdateArchiveSystem(ExecuteProcessor):
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    @override
    def execute(self) -> None:
        self.update_archive()
############################################################################################################
    def update_archive(self) -> None:
        # 建立数据
        context = self.context
        known_info_helper = UpdareArchiveHelper(self.context)
        known_info_helper.prepare()
        # 对Actor进行处理
        actor_entities: Set[Entity] = context.get_group(Matcher(all_of=[ActorComponent])).entities
        for _en in actor_entities:
            #更新Actor的Actor档案，可能更新了谁认识谁，还有如果在场景中，外观是什么
            self.update_actor_archive(_en, known_info_helper)
            #更新Actor的场景档案，
            self.update_stage_archive(_en, known_info_helper)
############################################################################################################
    def update_actor_archive(self, actor_entity: Entity, helper: UpdareArchiveHelper) -> None:
        #
        actor_comp: ActorComponent = actor_entity.get(ActorComponent)
        who_do_you_know: Set[str] = helper.who_do_you_know(actor_comp.name)
        if len(who_do_you_know) == 0:
            logger.warning(f"{actor_comp.name} 什么人都不认识，这个合理么？")
            return
        
        # 补充文件，有可能是新的人，也有可能全是旧的人
        add_actor_archive_files(self.context.file_system, actor_comp.name, who_do_you_know)        

        # 更新文件，只更新场景内我能看见的人
        appearance_data = self.context.appearance_in_stage(actor_entity)
        for name in who_do_you_know:
            appearance = appearance_data.get(name, "")
            if appearance != "":
                update_actor_archive_file(self.context.file_system, actor_comp.name, name, appearance)

        # 更新chat history
        who_do_you_know_promt = ",".join(who_do_you_know)
        message = update_actor_archive_prompt(actor_comp.name, who_do_you_know_promt)

        exclude_chat_history: Set[str] = set()
        exclude_chat_history.add(message)
        self.context.agent_connect_system.exclude_chat_history(actor_comp.name, exclude_chat_history)
        self.context.safe_add_human_message_to_entity(actor_entity, message)
############################################################################################################
    def update_stage_archive(self, actor_entity: Entity, helper: UpdareArchiveHelper) -> None:
        actor_comp: ActorComponent = actor_entity.get(ActorComponent)
        _stages_you_know: Set[str] = helper.stages_you_know(actor_comp.name)
        if len(_stages_you_know) == 0:
            logger.warning(f"{actor_comp.name} 什么地点都不知道，这个合理么？")
            return
        
        # 写文件
        add_stage_archive_files(self.context.file_system, actor_comp.name, _stages_you_know)

        # 更新chat history
        _stages_you_know_prompt = ",".join(_stages_you_know)
        message = update_stage_archive_prompt(actor_comp.name, _stages_you_know_prompt)

        exclude_chat_history: Set[str] = set()
        exclude_chat_history.add(message)
        self.context.agent_connect_system.exclude_chat_history(actor_comp.name, exclude_chat_history)
        self.context.safe_add_human_message_to_entity(actor_entity, message)
############################################################################################################
    