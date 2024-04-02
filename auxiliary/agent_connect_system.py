from loguru import logger
from typing import Dict
from auxiliary.actor_agent import ActorAgent
from typing import List, Union
from langchain_core.messages import HumanMessage, AIMessage
from loguru import logger
from typing import Optional

## 所有的初始记忆在这里管理
class AgentConnectSystem:

    ##
    def __init__(self, name: str) -> None:
        self.name: str = name
        self.memorydict: Dict[str, ActorAgent] = {}

    ##
    def register_actor_agent(self, name: str, url: str) -> None:
        self.memorydict[name] = ActorAgent(name, url)
        logger.debug(f"register_actor_agent: {name} is registered. url = {url}")

    ##
    def connect_actor_agent(self, name: str) -> None:
        if name in self.memorydict:
            #self.memorydict[name].connect()
            logger.debug(f"connect_actor_agent: {name} is connected.")
        else:
            logger.error(f"connect_actor_agent: {name} is not registered.")
    ##
    def debug_show_all_agents(self) -> None:
        logger.debug(f"AgentConnectSystem: {self.name} has {len(self.memorydict)} actor agents.")
        for name, agent in self.memorydict.items():
            logger.debug(f"AgentConnectSystem: {name} = {agent}")

    ##
    def request2(self, name: str, prompt: str) -> Optional[str]:
        if name in self.memorydict:
            logger.debug(f"request: {name} is requested.{prompt}")
            #return self.memorydict[name].request(prompt)
            return None
        logger.error(f"request: {name} is not registered.")
        return None

    #
    def add_chat_history(self, name: str, chat: str) -> None:
        if name in self.memorydict:
            self.memorydict[name].add_chat_history(chat)
            logger.debug(f"add_chat_history: {name} is added chat history.")
        else:
            logger.error(f"add_chat_history: {name} is not registered.")

    #
    def get_chat_history(self, name: str) -> List[Union[HumanMessage, AIMessage]]:
        if name in self.memorydict:
            return self.memorydict[name].chat_history
        logger.error(f"get_chat_history: {name} is not registered.")
        return []
    
    #
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
            return

        ## 删除人的问题，直到又碰见AI的回答，就跳出        
        for i in range(len(chat_history)-1, -1, -1):
            if isinstance(chat_history[i], HumanMessage):
                chat_history.pop(i)
            elif isinstance(chat_history[i], AIMessage):
                break

