
from auxiliary.extended_context import ExtendedContext
from typing import List

"""
directorscripts
"""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class DirectorEvent:
    def convert(self, stage_or_npc_name: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class BroadcastEvent(DirectorEvent):
    def __init__(self, npcname: str, stagename: str, content: str) -> None:
        self.npcname = npcname
        self.stagename = stagename
        self.content = content

    def __str__(self) -> str:
        return f"BroadcastEvent({self.npcname}, {self.stagename}, {self.content})"
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################

###
class Director:

    def __init__(self, name: str) -> None:
        self.name = name
        self.events: list[DirectorEvent] = []

    def addevent(self, event: DirectorEvent) -> None:
        self.events.append(event)

    def convert(self, stage_or_npc_name: str, extended_context: ExtendedContext) -> List[str]:
        batch: List[str] = []
        for event in self.events:
            batch.append(event.convert(stage_or_npc_name, extended_context))
        return batch

    def clear(self) -> None:
        self.events.clear()
    
