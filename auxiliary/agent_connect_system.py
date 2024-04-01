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
    def pop_chat_history(self, name: str) -> None:
        if name in self.memorydict:
            self.memorydict[name].chat_history.pop()
            logger.debug(f"pop_chat_history: {name} is poped chat history.")
        else:
            logger.error(f"pop_chat_history: {name} is not registered.")

        


