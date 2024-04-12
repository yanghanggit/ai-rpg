
from entitas import InitializeProcessor, ExecuteProcessor, Matcher #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import (NPCComponent, StageComponent)
from typing import Set, List
from langchain_core.messages import HumanMessage, AIMessage
from auxiliary.file_system import KnownNPCFile, KnownStageFile


class KnownInformationSystem(InitializeProcessor, ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def initialize(self) -> None:
        logger.debug("<<<<<<<<<<<<<  KnownInformationSystem init   >>>>>>>>>>>>>>>>>")
        #建立NPC的关系图谱
        self.init_known_npc()
        #建立知道的Stage的关系图谱
        self.init_known_stage()
############################################################################################################
    def init_known_stage(self) -> None:
        memory_system = self.context.memory_system
        agent_connect_system = self.context.agent_connect_system
        # ## 所有的npc名字
        allstagenames = self.all_stage_names()
        # # 开始提取关系
        npcentities = self.context.get_group(Matcher(NPCComponent)).entities
        for npc in npcentities:
            npccomp: NPCComponent = npc.get(NPCComponent)
            # 从初始化记忆中提取所有的关系
            npcsmem = memory_system.getmemory(npccomp.name)
            whereyouknow1 = self.where_you_know_in_memory(npcsmem, allstagenames)
            # 从chat history中提取所有的关系
            chathistory = agent_connect_system.get_chat_history(npccomp.name)
            whereyouknow2 = self.where_you_know_in_chat_history(chathistory, allstagenames)
            # 最后关系网的网，更新进去
            merge = whereyouknow1 | whereyouknow2
            self.add_known_stage_file(npccomp.name, merge)
############################################################################################################
    def init_known_npc(self) -> None:
        memory_system = self.context.memory_system
        agent_connect_system = self.context.agent_connect_system
        ## 所有的npc名字
        allnpcsname = self.all_npc_names()
        # 开始提取关系
        npcentities = self.context.get_group(Matcher(NPCComponent)).entities
        for npc in npcentities:
            npccomp: NPCComponent = npc.get(NPCComponent)
            # 从初始化记忆中提取所有的关系
            npcsmem = memory_system.getmemory(npccomp.name)
            whoyouknow1 = self.who_you_know_in_memory(npcsmem, allnpcsname)
            # 从chat history中提取所有的关系
            chathistory = agent_connect_system.get_chat_history(npccomp.name)
            whoyouknow2 = self.who_you_know_in_chat_history(chathistory, allnpcsname)
            # 最后关系网的网，更新进去
            merge = whoyouknow1 | whoyouknow2
            self.add_known_npc_file(npccomp.name, merge)    
############################################################################################################
    def all_npc_names(self) -> Set[str]:
        npcentities = self.context.get_group(Matcher(NPCComponent)).entities
        allnpcsname: Set[str] = set()
        for npc in npcentities:
            npccomp1: NPCComponent = npc.get(NPCComponent)
            allnpcsname.add(npccomp1.name)
        return allnpcsname
############################################################################################################
    def all_stage_names(self) -> Set[str]:
        stageentities = self.context.get_group(Matcher(StageComponent)).entities
        allstagesname: Set[str] = set()
        for stage in stageentities:
            stagecomp: StageComponent = stage.get(StageComponent)
            allstagesname.add(stagecomp.name)
        return allstagesname
############################################################################################################
    def add_known_npc_file(self, who: str, allnames: Set[str]) -> None:
        file_system = self.context.file_system
        for npcname in allnames:
            file = KnownNPCFile(npcname, who, npcname)
            file_system.add_known_npc_file(file)
############################################################################################################
    def add_known_stage_file(self, who: str, allnames: Set[str]) -> None:
        file_system = self.context.file_system
        for npcname in allnames:
            file = KnownStageFile(npcname, who, npcname)
            file_system.add_known_stage_file(file)
############################################################################################################
    def who_you_know_in_memory(self, yourmemory: str, allnames: Set[str]) -> Set[str]:
        return self.frommemory(yourmemory, allnames)
############################################################################################################
    def where_you_know_in_memory(self, yourmemory: str, allnames: Set[str]) -> Set[str]:
        return self.frommemory(yourmemory, allnames)
############################################################################################################
    def frommemory(self, yourmemory: str, allnames: Set[str]) -> Set[str]:
        result: Set[str] = set()
        for name in allnames:
            if name in yourmemory:
                result.add(name)
        return result
############################################################################################################
    def who_you_know_in_chat_history(self, chathistory: List[HumanMessage | AIMessage], allnames: Set[str]) -> Set[str]:
        return self.from_chat_history(chathistory, allnames)
############################################################################################################
    def where_you_know_in_chat_history(self, chathistory: List[HumanMessage | AIMessage], allnames: Set[str]) -> Set[str]:
        return self.from_chat_history(chathistory, allnames)
############################################################################################################ 
    def from_chat_history(self, chathistory: List[HumanMessage | AIMessage], allnames: Set[str]) -> Set[str]:
        all_content_from_messages: str = ""
        for chat in chathistory:
            if isinstance(chat, HumanMessage):
                all_content_from_messages += str(chat.content)
            elif isinstance(chat, AIMessage):
                all_content_from_messages += str(chat.content)

        result: Set[str] = set()
        for name in allnames:
            if name in all_content_from_messages:
                result.add(name)
        return result
############################################################################################################
    def execute(self) -> None:
        logger.debug("<<<<<<<<<<<<<  RelationshipSystem execute >>>>>>>>>>>>>>>>>")
############################################################################################################
    