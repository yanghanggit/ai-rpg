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

    def connect(self)-> None:
        if self.url != "":
            self.agent = RemoteRunnable(self.url)
        else:
            logger.warning(f"connect: {self.name} have no url. 请确认是默认玩家，否则检查game_settings.json中配置。")
 
        self.chat_history = []

    def request(self, prompt: str) -> Optional[str]:
        if self.agent is None:
            logger.warning(f"request: {self.name} have no agent.请确认是默认玩家，否则检查game_settings.json中配置。")
            return None
        response = self.agent.invoke({"input": prompt, "chat_history": self.chat_history})
        response_output = cast(str, response.get('output', ''))
        self.chat_history.extend([HumanMessage(content=prompt), AIMessage(content=response_output)])
        logger.debug(f"\n{'=' * 50}\n{self.name} request result:\n{response_output}\n{'=' * 50}")
        return response_output
    
    def add_chat_history(self, new_chat: str) -> None:
        self.chat_history.extend([HumanMessage(content = new_chat)])
    
    def __str__(self) -> str:
        return f"ActorAgent({self.name}, {self.url})"
