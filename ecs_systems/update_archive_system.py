from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from my_entitas.extended_context import ExtendedContext
from loguru import logger
from ecs_systems.components import (ActorComponent, StageComponent)
from builtin_prompt.cn_builtin_prompt import update_actor_archive_prompt, update_stage_archive_prompt
from file_system.helper import add_actor_archive_files, update_actor_archive_file, add_stage_archive_files
from typing import Set, override, Dict, List
import json


#### 一次处理过程的封装
###############################################################################################################################################
class UpdateArchiveHelper:
    def __init__(self, context: ExtendedContext) -> None:
        ##我的参数
        self.context = context
        self._stagenames: Set[str] = set()
        self._actor_names: Set[str] = set()
        self._agent_chat_history: Dict[str, str] = {}
        self._actors_with_props_info: Dict[str, List[str]] = {}
###############################################################################################################################################
    def prepare(self) -> None:
        ##step1: 所有拥有初始化记忆的场景拿出来
        self.prepare_stage_names()
        ##step2: 所有拥有初始化记忆的Actor拿出来
        self.prepare_actor_names()
        ##step3: 打包Actor的对话历史，方便后续查找
        self.prepare_agent_chat_history()
        ##step4: 所有拥有初始化记忆的Actor的道具信息拿出来
        self.prepare_actors_with_props_info()
###############################################################################################################################################
    def prepare_stage_names(self) -> None:
        self._stagenames.clear()
        #
        context = self.context
        memory_system = context._kick_off_memory_system
        stages: Set[Entity] = context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            stagecomp: StageComponent = stage.get(StageComponent)
            stagememory = memory_system.get_kick_off_memory(stagecomp.name)
            if stagememory != "":
                self._stagenames.add(stagecomp.name)
            else:
                logger.error(f"stage {stagecomp.name} has no init memory?")
###############################################################################################################################################
    def prepare_actor_names(self) -> None:
        self._actor_names.clear()
        #
        context = self.context
        memory_system = context._kick_off_memory_system
        actor_entities: Set[Entity] = context.get_group(Matcher(ActorComponent)).entities
        for _en in actor_entities:
            actor_comp: ActorComponent = _en.get(ActorComponent)
            kick_off_memory = memory_system.get_kick_off_memory(actor_comp.name)
            if kick_off_memory != "":
                self._actor_names.add(actor_comp.name)
            else:
                logger.error(f"actor {actor_comp.name} has no init memory?")
###############################################################################################################################################           
    def prepare_agent_chat_history(self) -> None:
        self._agent_chat_history.clear()
        context = self.context
        agent_connect_system = context._langserve_agent_system
        actor_entities: Set[Entity] = context.get_group(Matcher(ActorComponent)).entities
        for _en in actor_entities:
            actor_comp: ActorComponent = _en.get(ActorComponent)
            chat_history_dump: List[Dict[str, str]] = agent_connect_system.create_chat_history_dump(actor_comp.name)
            _str = json.dumps(chat_history_dump, ensure_ascii=False)
            self._agent_chat_history[actor_comp.name] = _str
###############################################################################################################################################
    def prepare_actors_with_props_info(self) ->  None:
        self._actors_with_props_info.clear()
        #
        context = self.context
        file_system = context._file_system
        actor_entities: Set[Entity] = context.get_group(Matcher(ActorComponent)).entities
        for _en in actor_entities:
            actor_comp: ActorComponent = _en.get(ActorComponent)
            propfiles = file_system.get_prop_files(actor_comp.name)
            prop_and_desc: List[str] = []
            for file in propfiles:
                prop_and_desc.append(f"{file._name}:{file._prop._description}")
            self._actors_with_props_info[actor_comp.name] = prop_and_desc
###############################################################################################################################################
    @property
    def stagenames(self) -> Set[str]:
        return self._stagenames
###############################################################################################################################################
    @property
    def actor_names(self) -> Set[str]:
        return self._actor_names
###############################################################################################################################################
    def get_actors_with_props_info(self, actor_name: str) -> List[str]:
        return self._actors_with_props_info.get(actor_name, [])
###############################################################################################################################################
    def stages_you_know(self, actor_name: str) -> Set[str]:
        #需要检查的场景名
        need_check_names = self.stagenames
        #人身上道具提到的
        mentioned_in_prop_description = self.name_mentioned_in_prop_description(need_check_names, actor_name)
        #记忆中出现的
        mentioned_in_memory = self.name_mentioned_in_memory(need_check_names, actor_name)
        #对话历史与上下文中出现的
        mentioned_in_chat_history = self.name_mentioned_in_chat_history(need_check_names, actor_name)
        #取并集
        finalres = mentioned_in_prop_description | mentioned_in_memory | mentioned_in_chat_history 
        return finalres
###############################################################################################################################################
    def who_do_you_know(self, actor_name: str) -> Set[str]:
        #需要检查的场景名
        need_check_names = self.actor_names
        #人身上道具提到的
        mentioned_in_prop_description = self.name_mentioned_in_prop_description(need_check_names, actor_name)
        #记忆中出现的
        mentioned_in_memory = self.name_mentioned_in_memory(need_check_names, actor_name)
        #对话历史与上下文中出现的
        mentioned_in_chat_history = self.name_mentioned_in_chat_history(need_check_names, actor_name)
        #取并集
        finalres = mentioned_in_prop_description | mentioned_in_memory | mentioned_in_chat_history
        finalres.discard(actor_name) ##去掉自己，没必要认识自己
        return finalres
###############################################################################################################################################
    def name_mentioned_in_prop_description(self, checknames: Set[str], actor_name: str) -> Set[str]:
        res: Set[str] = set()
        propinfolist = self._actors_with_props_info.get(actor_name, [])
        for propinfo in propinfolist:
            for name in checknames:
                if propinfo.find(name) != -1:
                    res.add(name)
        return res
###############################################################################################################################################
    def name_mentioned_in_memory(self, checknames: Set[str], actor_name: str) -> Set[str]:
        memory_system = self.context._kick_off_memory_system
        result: Set[str] = set()
        kick_off_memory = memory_system.get_kick_off_memory(actor_name)
        for name in checknames:
            if name in kick_off_memory:
                result.add(name)
        return result
###############################################################################################################################################
    def name_mentioned_in_chat_history(self, checknames: Set[str], actor_name: str) -> Set[str]:
        result: Set[str] = set()
        pack_chat_history = self._agent_chat_history.get(actor_name, "")
        for name in checknames:
            if pack_chat_history.find(name) != -1:
                result.add(name)
        return result
###############################################################################################################################################

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
        known_info_helper = UpdateArchiveHelper(self.context)
        known_info_helper.prepare()
        # 对Actor进行处理
        actor_entities: Set[Entity] = context.get_group(Matcher(all_of=[ActorComponent])).entities
        for _en in actor_entities:
            #更新Actor的Actor档案，可能更新了谁认识谁，还有如果在场景中，外观是什么
            self.update_actor_archive(_en, known_info_helper)
            #更新Actor的场景档案，
            self.update_stage_archive(_en, known_info_helper)
############################################################################################################
    def update_actor_archive(self, actor_entity: Entity, helper: UpdateArchiveHelper) -> None:
        #
        actor_comp: ActorComponent = actor_entity.get(ActorComponent)
        who_do_you_know: Set[str] = helper.who_do_you_know(actor_comp.name)
        if len(who_do_you_know) == 0:
            logger.warning(f"{actor_comp.name} 什么人都不认识，这个合理么？")
            return
        
        # 补充文件，有可能是新的人，也有可能全是旧的人
        add_actor_archive_files(self.context._file_system, actor_comp.name, who_do_you_know)        

        # 更新文件，只更新场景内我能看见的人
        appearance_data = self.context.appearance_in_stage(actor_entity)
        for name in who_do_you_know:
            appearance = appearance_data.get(name, "")
            if appearance != "":
                update_actor_archive_file(self.context._file_system, actor_comp.name, name, appearance)

        # 更新chat history
        who_do_you_know_promt = ",".join(who_do_you_know)
        message = update_actor_archive_prompt(actor_comp.name, who_do_you_know_promt)

        exclude_chat_history: Set[str] = set()
        exclude_chat_history.add(message)
        self.context._langserve_agent_system.exclude_chat_history(actor_comp.name, exclude_chat_history)
        self.context.safe_add_human_message_to_entity(actor_entity, message)
############################################################################################################
    def update_stage_archive(self, actor_entity: Entity, helper: UpdateArchiveHelper) -> None:
        actor_comp: ActorComponent = actor_entity.get(ActorComponent)
        _stages_you_know: Set[str] = helper.stages_you_know(actor_comp.name)
        if len(_stages_you_know) == 0:
            logger.warning(f"{actor_comp.name} 什么地点都不知道，这个合理么？")
            return
        
        # 写文件
        add_stage_archive_files(self.context._file_system, actor_comp.name, _stages_you_know)

        # 更新chat history
        _stages_you_know_prompt = ",".join(_stages_you_know)
        message = update_stage_archive_prompt(actor_comp.name, _stages_you_know_prompt)

        exclude_chat_history: Set[str] = set()
        exclude_chat_history.add(message)
        self.context._langserve_agent_system.exclude_chat_history(actor_comp.name, exclude_chat_history)
        self.context.safe_add_human_message_to_entity(actor_entity, message)
############################################################################################################
    