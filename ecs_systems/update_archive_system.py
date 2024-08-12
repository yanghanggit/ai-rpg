from entitas import ExecuteProcessor, Matcher, Entity #type: ignore
from rpg_game.rpg_entitas_context import RPGEntitasContext
from loguru import logger
from ecs_systems.components import (ActorComponent, StageComponent)
from ecs_systems.cn_builtin_prompt import update_actor_archive_prompt, update_stage_archive_prompt
from ecs_systems.cn_constant_prompt import _CNConstantPrompt_
from file_system.helper import add_actor_archive_files, update_actor_archive_file, add_stage_archive_files
from typing import Set, override, Dict, List


#### 一次处理过程的封装，目前是非常笨的方式（而且不是最终版本），后续可以优化。
###############################################################################################################################################
class UpdateArchiveHelper:
    def __init__(self, context: RPGEntitasContext) -> None:
        ##我的参数
        self._context = context
        self._stage_names: Set[str] = set()
        self._actor_names: Set[str] = set()
        self._agent_chat_history: Dict[str, str] = {}
        self._actors_props_desc: Dict[str, List[str]] = {}
###############################################################################################################################################
    def prepare(self) -> None:
        ## step1: 所有拥有初始化记忆的场景拿出来
        self._stage_names = self.get_stage_names()
        ## step2: 所有拥有初始化记忆的Actor拿出来
        self._actor_names = self.get_actor_names()
        ## step3: 打包Actor的对话历史，方便后续查找
        self._agent_chat_history = self.get_agent_chat_history()
        ## step4: 所有拥有初始化记忆的Actor的道具信息拿出来
        self._actors_props_desc = self.get_actors_props_desc()
###############################################################################################################################################
    def get_stage_names(self) -> Set[str]:
        result: Set[str] = set()
        stage_entities: Set[Entity] = self._context.get_group(Matcher(StageComponent)).entities
        for stage_entity in stage_entities:
            stage_comp = stage_entity.get(StageComponent)
            result.add(stage_comp.name)
        return result
###############################################################################################################################################
    def get_actor_names(self) -> Set[str]:
        result: Set[str] = set()
        actor_entities: Set[Entity] = self._context.get_group(Matcher(ActorComponent)).entities
        for actor_entity in actor_entities:
            actor_comp = actor_entity.get(ActorComponent)
            result.add(actor_comp.name)
        return result
###############################################################################################################################################           
    def get_agent_chat_history(self) -> Dict[str, str]:
        tags: Set[str] = {_CNConstantPrompt_.RE_EMPHASIZE_GAME_STYLE_TO_PREVENT_POLICY_PROBLEMS,
                                _CNConstantPrompt_.BATCH_CONVERSATION_ACTION_EVENTS_TAG,
                                _CNConstantPrompt_.SPEAK_ACTION_TAG,
                                _CNConstantPrompt_.WHISPER_ACTION_TAG,
                                _CNConstantPrompt_.BATCH_CONVERSATION_ACTION_EVENTS_TAG,}
        
        result: Dict[str, str] = {}
        actor_entities: Set[Entity] = self._context.get_group(Matcher(ActorComponent)).entities
        for actor_entity in actor_entities:
            actor_comp = actor_entity.get(ActorComponent)
            filter_chat_history = self._context._langserve_agent_system.create_filter_chat_history(actor_comp.name, tags)
            _str = " ".join(filter_chat_history) 
            result[actor_comp.name] = _str
        return result
###############################################################################################################################################
    def get_actors_props_desc(self) -> Dict[str, List[str]]:
        result: Dict[str, List[str]] = {}
        
        actor_entities: Set[Entity] = self._context.get_group(Matcher(ActorComponent)).entities
        for actor_entity in actor_entities:
            actor_comp = actor_entity.get(ActorComponent)
            prop_files = self._context._file_system.get_prop_files(actor_comp.name)
            desc: List[str] = []
            for file in prop_files:
                desc.append(f"{file.name}:{file.description}")
            result[actor_comp.name] = desc

        return result
###############################################################################################################################################
    @property
    def stage_names(self) -> Set[str]:
        return self._stage_names
###############################################################################################################################################
    @property
    def actor_names(self) -> Set[str]:
        return self._actor_names
###############################################################################################################################################
    def get_actor_props_desc(self, actor_name: str) -> List[str]:
        return self._actors_props_desc.get(actor_name, [])
###############################################################################################################################################
    def get_stage_archive(self, actor_name: str) -> Set[str]:
        #需要检查的场景名
        need_check_names = self.stage_names
        #人身上道具提到的
        mentioned_in_prop_description = self._name_mentioned_in_prop_description(need_check_names, actor_name)
        #记忆中出现的
        mentioned_in_kick_off_memory = self._name_mentioned_in_kick_off_memory(need_check_names, actor_name)
        #对话历史与上下文中出现的
        mentioned_in_chat_history = self._name_mentioned_in_chat_history(need_check_names, actor_name)
        #取并集
        return mentioned_in_prop_description | mentioned_in_kick_off_memory | mentioned_in_chat_history
###############################################################################################################################################
    def get_actor_archive(self, actor_name: str) -> Set[str]:
        #需要检查的场景名
        need_check_names = self.actor_names
        #人身上道具提到的
        mentioned_in_prop_description = self._name_mentioned_in_prop_description(need_check_names, actor_name)
        #记忆中出现的
        mentioned_in_kick_off_memory = self._name_mentioned_in_kick_off_memory(need_check_names, actor_name)
        #对话历史与上下文中出现的
        mentioned_in_chat_history = self._name_mentioned_in_chat_history(need_check_names, actor_name)
        #取并集
        finalres = mentioned_in_prop_description | mentioned_in_kick_off_memory | mentioned_in_chat_history
        finalres.discard(actor_name) ##去掉自己，没必要认识自己
        return finalres
###############################################################################################################################################
    def _name_mentioned_in_prop_description(self, check_names: Set[str], actor_name: str) -> Set[str]:
        res: Set[str] = set()
        propinfolist = self._actors_props_desc.get(actor_name, [])
        for propinfo in propinfolist:
            for name in check_names:
                if propinfo.find(name) != -1:
                    res.add(name)
        return res
###############################################################################################################################################
    def _name_mentioned_in_kick_off_memory(self, check_names: Set[str], actor_name: str) -> Set[str]:
        result: Set[str] = set()
        kick_off_memory = self._context._kick_off_memory_system.get_kick_off_memory(actor_name)
        for name in check_names:
            if name in kick_off_memory:
                result.add(name)
        return result
###############################################################################################################################################
    def _name_mentioned_in_chat_history(self, check_names: Set[str], actor_name: str) -> Set[str]:
        result: Set[str] = set()
        chat_history = self._agent_chat_history.get(actor_name, "")
        for name in check_names:
            if chat_history.find(name) != -1:
                result.add(name)
        return result
###############################################################################################################################################



class UpdateArchiveSystem(ExecuteProcessor):
    def __init__(self, context: RPGEntitasContext) -> None:
        self._context: RPGEntitasContext = context
###############################################################################################################################################
    @override
    def execute(self) -> None:
        self.update_archive()
###############################################################################################################################################
    def update_archive(self) -> None:
        # 建立数据
        context = self._context
        archive_helper = UpdateArchiveHelper(self._context)
        archive_helper.prepare()
        # 对Actor进行处理
        actor_entities: Set[Entity] = context.get_group(Matcher(all_of=[ActorComponent])).entities
        for _en in actor_entities:
            #更新Actor的Actor档案，可能更新了谁认识谁，还有如果在场景中，外观是什么
            self.update_actor_archive(_en, archive_helper)
            #更新Actor的场景档案，
            self.update_stage_archive(_en, archive_helper)
###############################################################################################################################################
    def update_actor_archive(self, actor_entity: Entity, helper: UpdateArchiveHelper) -> None:
        #
        actor_comp = actor_entity.get(ActorComponent)
        actor_archives: Set[str] = helper.get_actor_archive(actor_comp.name)
        if len(actor_archives) == 0:
            logger.warning(f"{actor_comp.name} 什么人都不认识，这个合理么？")
            return
        
        # 补充文件，有可能是新的人，也有可能全是旧的人
        add_actor_archive_files(self._context._file_system, actor_comp.name, actor_archives)        

        # 更新文件，只更新场景内我能看见的人
        appearance_data = self._context.appearance_in_stage(actor_entity)
        for name in actor_archives:
            appearance = appearance_data.get(name, "")
            if appearance != "":
                update_actor_archive_file(self._context._file_system, actor_comp.name, name, appearance)

        # 更新chat history
        actors_names = ",".join(actor_archives)
        message = update_actor_archive_prompt(actor_comp.name, actors_names)

        exclude_chat_history: Set[str] = set()
        exclude_chat_history.add(message)

        # 过去的都删除了
        self._context._langserve_agent_system.exclude_content_then_rebuild_chat_history(actor_comp.name, exclude_chat_history)

        # 添加新的
        self._context.safe_add_human_message_to_entity(actor_entity, message)
###############################################################################################################################################
    def update_stage_archive(self, actor_entity: Entity, helper: UpdateArchiveHelper) -> None:
        actor_comp = actor_entity.get(ActorComponent)
        stage_archives: Set[str] = helper.get_stage_archive(actor_comp.name)
        if len(stage_archives) == 0:
            logger.warning(f"{actor_comp.name} 什么地点都不知道，这个合理么？")
            return
        
        # 写文件
        add_stage_archive_files(self._context._file_system, actor_comp.name, stage_archives)

        # 更新chat history
        stages_names = ",".join(stage_archives)
        message = update_stage_archive_prompt(actor_comp.name, stages_names)

        exclude_chat_history: Set[str] = set()
        exclude_chat_history.add(message)

        # 过去的都删除了
        self._context._langserve_agent_system.exclude_content_then_rebuild_chat_history(actor_comp.name, exclude_chat_history)

        # 添加新的
        self._context.safe_add_human_message_to_entity(actor_entity, message)
###############################################################################################################################################
    