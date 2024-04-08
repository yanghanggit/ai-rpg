from typing import List, Optional, Union, cast
from langchain_core.messages import HumanMessage, AIMessage
from langserve import RemoteRunnable  # type: ignore
from loguru import logger

class ActorAgent:

    def __init__(self, name: str = "", url: str = "") -> None:
        self.name: str = name 
        self.url: str = url
        self.agent: RemoteRunnable = None
        self.chat_history: List[Union[HumanMessage, AIMessage]] = []
################################################################################################################################################################################
    def connect(self) -> bool:
        if self.url == "":
            logger.error(f"connect: {self.name} have no url. 请确认是默认玩家，否则检查game_settings.json中配置。")
            return False
        try:
            self.agent = RemoteRunnable(self.url)
            assert self.agent is not None
            self.chat_history = []
            return True
        except Exception as e:
            logger.error(e)
            return False        
        return False
################################################################################################################################################################################
    def request(self, prompt: str) -> Optional[str]:

        if self.agent is None:
            logger.error(f"request: {self.name} have no agent.请确认是默认玩家，否则检查game_settings.json中配置。")
            return None
    
        try:

            response = self.agent.invoke({"input": prompt, "chat_history": self.chat_history})
            responsecontent = cast(str, response.get('output', ''))
            self.chat_history.extend([HumanMessage(content = prompt), AIMessage(content = responsecontent)])
            logger.debug(f"\n{'=' * 50}\n{self.name} request result:\n{responsecontent}\n{'=' * 50}")
            return responsecontent
           
        except Exception as e:
            logger.error(f"{self.name}: request error: {e}")
            return None      

        return None
################################################################################################################################################################################
    def add_human_message_to_chat_history(self, new_chat: str) -> None:
        self.chat_history.extend([HumanMessage(content = new_chat)])
################################################################################################################################################################################
    def add_ai_message_to_chat_history(self, new_chat: str) -> None:
        self.chat_history.extend([AIMessage(content = new_chat)])
################################################################################################################################################################################
    def __str__(self) -> str:
        return f"ActorAgent({self.name}, {self.url})"
################################################################################################################################################################################
