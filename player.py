from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
from actor import Actor

#
class Player(Actor):
    def __init__(self, name: str):
        super().__init__(name)
        self.stage = None
        self.description = "一个人类"