from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
from actor import Actor
from npc import NPC

#
class Stage(Actor):
    def __init__(self, name:str):
        self.name = name
        self.actors = []
        self.world = None
        self.npcs = []

    def add_actor(self, actor: Actor)-> None:
        self.actors.append(actor)
        if isinstance(actor, NPC):
            self.npcs.append(actor)

    def get_actor(self, name: str) -> Actor:
        for actor in self.actors:
            if actor.name == name:
                return actor
        return None
    
    def remove_actor(self, actor: Actor) -> None:
        self.actors.remove(actor)
        if isinstance(actor, NPC):
            self.npcs.remove(actor)


