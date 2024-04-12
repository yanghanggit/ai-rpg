
from entitas import InitializeProcessor, ExecuteProcessor, Matcher #type: ignore
from auxiliary.extended_context import ExtendedContext
from loguru import logger
from auxiliary.components import (StageComponent, 
                        NPCComponent)

from auxiliary.agent_connect_system import AgentConnectSystem
from auxiliary.file_system import FileSystem
import json
from typing import Dict, Set, List
from langchain_core.messages import HumanMessage, AIMessage
   
class RelationshipSystem(InitializeProcessor, ExecuteProcessor):
############################################################################################################
    def __init__(self, context: ExtendedContext) -> None:
        self.context: ExtendedContext = context
############################################################################################################
    def initialize(self) -> None:
        logger.debug("<<<<<<<<<<<<<  RelationshipSystem init   >>>>>>>>>>>>>>>>>")

        memory_system = self.context.memory_system
        agent_connect_system = self.context.agent_connect_system

        ## 所有的npc名字
        npcentities = self.context.get_group(Matcher(NPCComponent)).entities
        allnpcsname: Set[str] = set()
        for npc in npcentities:
            npccomp1: NPCComponent = npc.get(NPCComponent)
            allnpcsname.add(npccomp1.name)

        # 开始提取关系
        for npc in npcentities:
            npccomp: NPCComponent = npc.get(NPCComponent)
            logger.debug(f"npc = {npccomp.name}")

            # 从初始化记忆中提取所有的关系
            npcsmem = memory_system.getmemory(npccomp.name)
            logger.debug(f"npcsmem = {npcsmem}")
            whoyouknow1 = self.analyze_who_you_know_in_memory(npcsmem, allnpcsname)

            # 从chat history中提取所有的关系
            chathistory = agent_connect_system.get_chat_history(npccomp.name)
            whoyouknow2 = self.analyze_who_you_know_in_chat_history(chathistory, allnpcsname)

            # 最后关系网的网，更新进去
            merge = whoyouknow1 | whoyouknow2
            memory_system.addrelationship(npccomp.name, merge)
            memory_system.writerelationship(npccomp.name)
       
############################################################################################################
    def analyze_who_you_know_in_memory(sefl, yourmemory: str, allnames: Set[str]) -> Set[str]:
        result: Set[str] = set()
        for name in allnames:
            if name in yourmemory:
                result.add(name)
        return result
############################################################################################################
    def analyze_who_you_know_in_chat_history(self, chathistory: List[HumanMessage | AIMessage], allnames: Set[str]) -> Set[str]:

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
    