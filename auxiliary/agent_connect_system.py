from loguru import logger
import os
from typing import Dict
from auxiliary.actor_agent import ActorAgent

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
    def request(self, name: str, prompt: str) -> None:
        if name in self.memorydict:
            #self.memorydict[name].request(prompt)
            logger.debug(f"request: {name} is requested.{prompt}")
        else:
            logger.error(f"request: {name} is not registered.")


        


