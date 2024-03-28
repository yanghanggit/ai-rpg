
from auxiliary.extended_context import ExtendedContext
from typing import List
from auxiliary.prompt_maker import broadcast_action_prompt
from loguru import logger
from auxiliary.print_in_color import Color

"""
directorscripts
"""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class DirectorEvent:
    ### 这一步处理可以达到每个人看到的事件有不同的陈述，而不是全局唯一的陈述
    def convert(self, targetname: str, extended_context: ExtendedContext) -> str:
        return ""
####################################################################################################################################
####################################################################################################################################
####################################################################################################################################
class BroadcastEvent(DirectorEvent):
    def __init__(self, who_broadcast: str, stagename: str, content: str) -> None:
        self.who_broadcast = who_broadcast
        self.stagename = stagename
        self.content = content

    def __str__(self) -> str:
        return f"BroadcastEvent({self.who_broadcast}, {self.stagename}, {self.content})"
    
    def convert(self, targetname: str, extended_context: ExtendedContext) -> str:
        if targetname != self.who_broadcast:
            logger.error(f"BroadcastEvent: {targetname} != {self.who_broadcast}")
        broadcast_say = broadcast_action_prompt(self.who_broadcast, self.stagename, self.content, extended_context)
        logger.info(f"{Color.HEADER}{broadcast_say}{Color.ENDC}")
        return broadcast_say
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

    def convert(self, targetname: str, extended_context: ExtendedContext) -> List[str]:
        batch: List[str] = []
        for event in self.events:
            batch.append(event.convert(targetname, extended_context))
        return batch

    def clear(self) -> None:
        self.events.clear()
    
