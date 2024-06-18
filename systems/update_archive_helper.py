from entitas import Entity, Matcher # type: ignore
from auxiliary.components import StageComponent, ActorComponent
from auxiliary.extended_context import ExtendedContext
from langchain_core.messages import (HumanMessage, 
                                    AIMessage)
from loguru import logger
from typing import List, Dict, Set
import json


#### 一次处理过程的封装
###############################################################################################################################################
class UpdareArchiveHelper:
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
        memory_system = context.kick_off_memory_system
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
        memory_system = context.kick_off_memory_system
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
        agent_connect_system = context.agent_connect_system
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
        file_system = context.file_system
        actor_entities: Set[Entity] = context.get_group(Matcher(ActorComponent)).entities
        for _en in actor_entities:
            actor_comp: ActorComponent = _en.get(ActorComponent)
            propfiles = file_system.get_prop_files(actor_comp.name)
            prop_and_desc: List[str] = []
            for file in propfiles:
                prop_and_desc.append(f"{file.name}:{file.prop._description}")
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
        memory_system = self.context.kick_off_memory_system
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