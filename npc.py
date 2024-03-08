from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
from actor import Actor
#
class NPC(Actor): 
    def __init__(self, name: str):
        super().__init__(name)
        self.stage = None

        #测试的
        self.max_hp = 100
        self.hp = 100
        self.damage = 10