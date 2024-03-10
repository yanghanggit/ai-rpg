from actor import Actor
from npc import NPC
from rpg import RPG

from typing import Optional
from player import Player

#
class Stage(Actor, RPG):

    def __init__(self, name:str):
        Actor.__init__(self, name)  # 显式地初始化Actor基类
        RPG.__init__(self)          # 显式地初始化RPG基类
        
        self.actors: list[ NPC | Player ] = []

        from world import World
        self.world: Optional[World] = None
        
        self.stage: Stage = self

    def add_actor(self, actor: NPC|Player)-> None:
        self.actors.append(actor)
        actor.stage = self
      
    def get_actor(self, name: str) -> Optional[NPC|Player]:
        for actor in self.actors:
            if actor.name == name:
                return actor
        return None
    
    def remove_actor(self, actor: NPC|Player) -> None:
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
    
    def add_memory(self, content: str) -> bool:
        super().add_memory(content)
        for actor in self.actors:
            actor.add_memory(content)
        return True

       


