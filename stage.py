from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
from actor import Actor
from npc import NPC

#
class Stage(Actor):
    def __init__(self, name:str):
        super().__init__(name)
        self.actors = []
        self.world = None

    def add_actor(self, actor: Actor)-> None:
        self.actors.append(actor)
        actor.stage = self
      
    def get_actor(self, name: str) -> Actor:
        for actor in self.actors:
            if actor.name == name:
                return actor
        return None
    
    def remove_actor(self, actor: Actor) -> None:
        if not actor in self.actors:
            print(0, f"actor {actor.name} not in stage {self.name}")
            return
        self.actors.remove(actor)
        actor.stage = None


    def get_all_npcs(self) -> list[NPC]:
        npcs = []
        for actor in self.actors:
            if isinstance(actor, NPC):
                npcs.append(actor)
        return npcs
    
    def add_memory(self, content: str)-> None:
        super().add_memory(content)
        for actor in self.actors:
            actor.add_memory(content)

       


