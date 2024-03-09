from langchain_core.messages import HumanMessage, AIMessage, BaseMessage, SystemMessage
from langserve import RemoteRunnable
import sys
import json
from actor import Actor
from world import World
from stage import Stage
from stage import NPC
from player import Player
from action import Action, FIGHT, STAY, LEAVE
from make_plan import stage_plan, npc_plan, MakePlan
from console import Console
from director import Director
       
class StageEvents():
    def __init__(self, name:str):
        self.name = name
        self.events = []

    def add_event(self, event: str) -> None:
        self.events.append(event)
        print(f"{self.name}?", event)

    def combine_events(self) -> str:
        return "\n".join(self.events)