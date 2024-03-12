
from typing import List, Union, cast
from langchain_core.messages import HumanMessage, AIMessage
from langserve import RemoteRunnable  # type: ignore


###############################################################################################################################################
class ActorAgent:

    def __init__(self):
        self.name: str = ""   
        self.url: str = ""
        self.memory: str = ""
        self.agent: RemoteRunnable = None
        self.chat_history: List[Union[HumanMessage, AIMessage]] = []

    def init(self, name: str, url: str, memory: str) -> None:
        self.name = name
        self.url = url
        self.memory = memory

    def connect(self)-> None:
        self.agent = RemoteRunnable(self.url)
        self.chat_history = []

    def request(self, prompt: str) -> str:
        if self.agent is None:
            print(f"request: {self.name} have no agent.")
            return ""
        if self.chat_history is None:
            print(f"request: {self.name} have no chat history.")
            return ""
        response = self.agent.invoke({"input": prompt, "chat_history": self.chat_history})
        response_output = cast(str, response.get('output', ''))
        self.chat_history.extend([HumanMessage(content=prompt), AIMessage(content=response_output)])

        print(f"{self.name } request = ", response_output)
        return response_output
    
    def add_chat_history(self, new_chat: str) -> None:
        if self.agent is None:
            print(f"add_chat_history: {self.name} have no agent.")
            return ""
        print(f"{self.name } add_chat_history = ", new_chat)
        self.chat_history.extend([HumanMessage(content = new_chat)])
    
    def __str__(self) -> str:
        return f"ActorAgent({self.name}, {self.url})"
