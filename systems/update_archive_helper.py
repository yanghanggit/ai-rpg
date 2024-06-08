from entitas import Entity, Matcher # type: ignore
from auxiliary.components import StageComponent, ActorComponent
from auxiliary.extended_context import ExtendedContext
from langchain_core.messages import (HumanMessage, 
                                    AIMessage)
from loguru import logger
from typing import List, Dict, Set


#### 一次处理过程的封装
###############################################################################################################################################
class UpdareArchiveHelper:
    def __init__(self, context: ExtendedContext) -> None:
        ##我的参数
        self.context = context
        self._stagenames: Set[str] = set()
        self._npcnames: Set[str] = set()
        self._npc_chat_history: Dict[str, str] = {}
        self._npcs_with_props_info: Dict[str, List[str]] = {}
###############################################################################################################################################
    def prepare(self) -> None:
        ##step1: 所有拥有初始化记忆的场景拿出来
        self.prepare_stage_names()
        ##step2: 所有拥有初始化记忆的NPC拿出来
        self.prepare_npc_names()
        ##step3: 打包NPC的对话历史，方便后续查找
        self.prepare_npc_chat_history()
        ##step4: 所有拥有初始化记忆的NPC的道具信息拿出来
        self.prepare_npc_with_props_info()
###############################################################################################################################################
    def prepare_stage_names(self) -> None:
        self._stagenames.clear()
        #
        context = self.context
        memory_system = context.kick_off_memory_system
        stages: set[Entity] = context.get_group(Matcher(StageComponent)).entities
        for stage in stages:
            stagecomp: StageComponent = stage.get(StageComponent)
            stagememory = memory_system.get_kick_off_memory(stagecomp.name)
            if stagememory != "":
                self._stagenames.add(stagecomp.name)
            else:
                logger.error(f"stage {stagecomp.name} has no init memory?")
###############################################################################################################################################
    def prepare_npc_names(self) -> None:
        self._npcnames.clear()
        #
        context = self.context
        memory_system = context.kick_off_memory_system
        npcs: set[Entity] = context.get_group(Matcher(ActorComponent)).entities
        for npc in npcs:
            npccomp: ActorComponent = npc.get(ActorComponent)
            npcmemory = memory_system.get_kick_off_memory(npccomp.name)
            if npcmemory != "":
                self._npcnames.add(npccomp.name)
            else:
                logger.error(f"npc {npccomp.name} has no init memory?")
###############################################################################################################################################           
    def prepare_npc_chat_history(self) -> None:
        self._npc_chat_history.clear()
        context = self.context
        agent_connect_system = context.agent_connect_system
        npcs: set[Entity] = context.get_group(Matcher(ActorComponent)).entities
        for npc in npcs:
            npccomp: ActorComponent = npc.get(ActorComponent)
            chathistory: List[str] = agent_connect_system.create_chat_history_dump(npccomp.name)
            pack_all = "\n".join(chathistory)
            self._npc_chat_history[npccomp.name] = pack_all
###############################################################################################################################################
    def prepare_npc_with_props_info(self) ->  None:
        self._npcs_with_props_info.clear()
        #
        context = self.context
        file_system = context.file_system
        npcs: set[Entity] = context.get_group(Matcher(ActorComponent)).entities
        for npc in npcs:
            npccomp: ActorComponent = npc.get(ActorComponent)
            propfiles = file_system.get_prop_files(npccomp.name)
            prop_and_desc: list[str] = []
            for file in propfiles:
                prop_and_desc.append(f"{file.name}:{file.prop._description}")
            self._npcs_with_props_info[npccomp.name] = prop_and_desc
###############################################################################################################################################
    @property
    def stagenames(self) -> Set[str]:
        return self._stagenames
###############################################################################################################################################
    @property
    def npcnames(self) -> Set[str]:
        return self._npcnames
###############################################################################################################################################
    def get_npcs_with_props_info(self, npcname: str) -> List[str]:
        return self._npcs_with_props_info.get(npcname, [])
###############################################################################################################################################
    def stages_you_know(self, npcname: str) -> Set[str]:
        #需要检查的场景名
        need_check_names = self.stagenames
        #人身上道具提到的
        mentioned_in_prop_description = self.name_mentioned_in_prop_description(need_check_names, npcname)
        #记忆中出现的
        mentioned_in_memory = self.name_mentioned_in_memory(need_check_names, npcname)
        #对话历史与上下文中出现的
        mentioned_in_chat_history = self.name_mentioned_in_chat_history(need_check_names, npcname)
        #取并集
        finalres = mentioned_in_prop_description | mentioned_in_memory | mentioned_in_chat_history 
        return finalres
###############################################################################################################################################
    def who_do_you_know(self, npcname: str) -> Set[str]:
        #需要检查的场景名
        need_check_names = self.npcnames
        #人身上道具提到的
        mentioned_in_prop_description = self.name_mentioned_in_prop_description(need_check_names, npcname)
        #记忆中出现的
        mentioned_in_memory = self.name_mentioned_in_memory(need_check_names, npcname)
        #对话历史与上下文中出现的
        mentioned_in_chat_history = self.name_mentioned_in_chat_history(need_check_names, npcname)
        #取并集
        finalres = mentioned_in_prop_description | mentioned_in_memory | mentioned_in_chat_history
        finalres.discard(npcname) ##去掉自己，没必要认识自己
        return finalres
###############################################################################################################################################
    def name_mentioned_in_prop_description(self, checknames: Set[str], npcname: str) -> Set[str]:
        res: Set[str] = set()
        propinfolist = self._npcs_with_props_info.get(npcname, [])
        for propinfo in propinfolist:
            for name in checknames:
                if propinfo.find(name) != -1:
                    res.add(name)
        return res
###############################################################################################################################################
    def name_mentioned_in_memory(self, checknames: Set[str], npcname: str) -> Set[str]:
        memory_system = self.context.kick_off_memory_system
        result: set[str] = set()
        npcmemory = memory_system.get_kick_off_memory(npcname)
        for name in checknames:
            if name in npcmemory:
                result.add(name)
        return result
###############################################################################################################################################
    def name_mentioned_in_chat_history(self, checknames: Set[str], npcname: str) -> Set[str]:
        result: set[str] = set()
        pack_chat_history = self._npc_chat_history.get(npcname, "")
        for name in checknames:
            if pack_chat_history.find(name) != -1:
                result.add(name)
        return result
###############################################################################################################################################