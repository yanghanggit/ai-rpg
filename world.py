from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
from actor import Actor

class World(Actor):
    def __init__(self, name: str):
        self.name = name
        self.stages = []

    def add_stage(self, stage) -> None:
        self.stages.append(stage)




