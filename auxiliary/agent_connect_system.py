import os
from loguru import logger
from typing import Dict,  List, Union, Optional
from auxiliary.actor_agent import ActorAgent
from langchain_core.messages import HumanMessage, AIMessage
import json

## 单独封装一个系统，用于连接actor agent
class AgentConnectSystem:

    ##
    def __init__(self, name: str) -> None:
        self.name: str = name
        self.memorydict: Dict[str, ActorAgent] = {}
        self.rootpath = ""
############################################################################################################
    ### 必须设置根部的执行路行
    def set_root_path(self, rootpath: str) -> None:
        if self.rootpath != "":
            raise Exception(f"[filesystem]已经设置了根路径，不能重复设置。")
        self.rootpath = rootpath
        logger.debug(f"[filesystem]设置了根路径为{rootpath}")
############################################################################################################
    def register_actor_agent(self, name: str, url: str) -> None:
        self.memorydict[name] = ActorAgent(name, url)
        logger.debug(f"register_actor_agent: {name} is registered. url = {url}")
############################################################################################################
    def debug_show_all_agents(self) -> None:
        logger.debug(f"AgentConnectSystem: {self.name} has {len(self.memorydict)} actor agents.")
        for name, agent in self.memorydict.items():
            logger.debug(f"AgentConnectSystem: {name} = {agent}")
############################################################################################################
    def connect_actor_agent(self, name: str) -> bool:
        if name in self.memorydict:
            return self.memorydict[name].connect()
        logger.error(f"connect_actor_agent: {name} is not registered.")
        return False
############################################################################################################
    def request(self, name: str, prompt: str) -> Optional[str]:
        if name in self.memorydict:
            return self.memorydict[name].request(prompt)
        logger.error(f"request: {name} is not registered.")
        return None
############################################################################################################
    def add_human_message_to_chat_history(self, name: str, chat: str) -> None:
        if name in self.memorydict:
            self.memorydict[name].add_human_message_to_chat_history(chat)
        else:
            logger.error(f"add_chat_history: {name} is not registered.")
############################################################################################################
    def add_ai_message_to_chat_history(self, name: str, chat: str) -> None:
        if name in self.memorydict:
            self.memorydict[name].add_ai_message_to_chat_history(chat)
            #logger.debug(f"add_chat_history: {name} is added chat history.")
        else:
            logger.error(f"add_chat_history: {name} is not registered.")
############################################################################################################
    def get_chat_history(self, name: str) -> List[Union[HumanMessage, AIMessage]]:
        if name in self.memorydict:
            return self.memorydict[name].chat_history
        logger.error(f"get_chat_history: {name} is not registered.")
        return []   
############################################################################################################
    def remove_last_conversation_between_human_and_ai(self, name: str) -> None:
        if not name in self.memorydict:
            return
        
        chat_history = self.memorydict[name].chat_history
        if len(chat_history) == 0:
            return

        if isinstance(chat_history[-1], AIMessage):
            ## 是AI的回答，需要删除AI的回答和人的问题
            chat_history.pop()
        else:
            ## 最后一次不是AI的回答，就跳出，因为可能是有问题的。ai还没有回答，只有人的问题
            return

        ## 删除人的问题，直到又碰见AI的回答，就跳出        
        for i in range(len(chat_history)-1, -1, -1):
            if isinstance(chat_history[i], HumanMessage):
                chat_history.pop(i)
            elif isinstance(chat_history[i], AIMessage):
                break
############################################################################################################
    ### 目标文件
    def chat_history_dump(self, who: str) -> str:
        return f"{self.rootpath}{who}/chat_history/dump.json"
############################################################################################################  
    ### 所有的chathistory
    def all_agents_chat_history_dump(self) -> None:
        for who in self.memorydict.keys():
            chatlist = self.output_chat_history_dump(who)
            if len(chatlist) == 0:
                continue
            chat_json = json.dumps(chatlist, ensure_ascii = False)
            chat_string = str(chat_json)
            self.write_chat_history_dump(who, chat_string)
############################################################################################################  
    ### 准备dump
    def output_chat_history_dump(self, who: str) ->  List[str]:
        chathistory = self.get_chat_history(who)
        chatlist: List[str] = []
        for chat in chathistory:
            if isinstance(chat, HumanMessage):
                chatlist.append(f"[HumanMessage]: {chat.content}")
            elif isinstance(chat, AIMessage):
                chatlist.append(f"[{who}]: {chat.content}")
        return chatlist
############################################################################################################
    ##强制写入
    def write_chat_history_dump(self, who: str, content: str) -> None:
        mempath = self.chat_history_dump(who)
        try:
            if not os.path.exists(mempath):
                os.makedirs(os.path.dirname(mempath), exist_ok=True)
            with open(mempath, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.error(f"[{who}]写入chat history dump失败。")
            return
############################################################################################################