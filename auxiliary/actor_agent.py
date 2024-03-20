
from typing import List, Optional, Union, cast
from langchain_core.messages import HumanMessage, AIMessage
from langserve import RemoteRunnable  # type: ignore
from loguru import logger  # type: ignore

class ActorAgent:

    def __init__(self, name: str = "", url: str = "", memory: str = "") -> None:
        self.name: str = name 
        self.url: str = url
        self.memory: str = memory
        self.agent: RemoteRunnable = None
        self.chat_history: List[Union[HumanMessage, AIMessage]] = []

    def connect(self)-> None:
        if self.url == "":
            logger.info(f"connect: {self.name} have no url. 因为是默认玩家。")
            self.agent = None
        else:
            self.agent = RemoteRunnable(self.url)
        self.chat_history = []

        if self.memory == "":
            self.memory = "/savedData/basic_archive.md"
            logger.warning(f"{self.name}未找到专属存档，载入默认存档")

    def request(self, prompt: str) -> Optional[str]:
        if self.agent is None:
            logger.warning(f"request: {self.name} have no agent.")
            return None
        if self.chat_history is None:
            logger.warning(f"request: {self.name} have no chat history.")
            return ""
        response = self.agent.invoke({"input": prompt, "chat_history": self.chat_history})
        response_output = cast(str, response.get('output', ''))
        self.chat_history.extend([HumanMessage(content=prompt), AIMessage(content=response_output)])

        logger.debug(f"\n{'=' * 50}\n{self.name} request result:\n{response_output}\n{'=' * 50}")
        return response_output
    
    def add_chat_history(self, new_chat: str) -> None:
        if self.agent is None:
            logger.warning(f"add_chat_history: {self.name} have no agent.")
            return
        self.chat_history.extend([HumanMessage(content = new_chat)])
    
    def __str__(self) -> str:
        return f"ActorAgent({self.name}, {self.url})"
