from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable

#
class Actor:
    def __init__(self, name: str):
        self.name = name     

    def connect(self, url: str)-> None:
        self.agent = RemoteRunnable(url)
        self.chat_history = []

    def call_agent(self, prompt: str) -> str:
        response = self.agent.invoke({"input": prompt, "chat_history": self.chat_history})
        self.chat_history.extend([HumanMessage(content=prompt), AIMessage(content=response['output'])])
        return response['output']
#
# def call_agent(target: Actor, prompt: str) -> str:
#     # if not hasattr(target, 'agent') or not hasattr(target, 'chat_history'):
#     #     return None
#     response = target.agent.invoke({"input": prompt, "chat_history": target.chat_history})
#     target.chat_history.extend([HumanMessage(content=prompt), AIMessage(content=response['output'])])
#     return response['output']







