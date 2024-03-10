###
from typing import List, Union, cast
from langchain_core.messages import HumanMessage, AIMessage
from langserve import RemoteRunnable  # type: ignore
#
class Actor:
    def __init__(self, name: str):
        self.name: str = name   
        self.url: str = ""
        self.agent: RemoteRunnable = None
        self.chat_history: List[Union[HumanMessage, AIMessage]] = []

    def connect(self, url: str)-> None:
        self.agent = RemoteRunnable(url)
        self.chat_history = []

    def call_agent(self, prompt: str) -> str:
        if self.agent is None:
            print(f"call_agent: {self.name} have no agent.")
            return ""
        if self.chat_history is None:
            print(f"call_agent: {self.name} have no chat history.")
            return ""
        response = self.agent.invoke({"input": prompt, "chat_history": self.chat_history})
        response_output = cast(str, response.get('output', ''))
        self.chat_history.extend([HumanMessage(content=prompt), AIMessage(content=response_output)])
        return response_output

    def add_memory(self, content: str) -> bool:
        self.chat_history.append(HumanMessage(content=content))
        return True






