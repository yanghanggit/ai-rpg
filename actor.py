from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable

#
class Actor:
    def __init__(self, name: str):
        self.name = name     
        #测试的
        self.max_hp = 100
        self.hp = 100
        self.damage = 10

    def connect(self, url: str)-> None:
        self.agent = RemoteRunnable(url)
        self.chat_history = []

    def call_agent(self, prompt: str) -> str:
        response = self.agent.invoke({"input": prompt, "chat_history": self.chat_history})
        self.chat_history.extend([HumanMessage(content=prompt), AIMessage(content=response['output'])])
        return response['output']






