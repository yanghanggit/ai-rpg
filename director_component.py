from auxiliary.extended_context import ExtendedContext
from typing import List
from loguru import logger
from collections import namedtuple
from director_event import IDirectorEvent

## yh 第一个 扩展型组件，用于处理导演系统的事件
DirectorComponentPrototype = namedtuple('DirectorComponentPrototype', 'name')
class DirectorComponent(DirectorComponentPrototype):

    def __init__(self) -> None:
        self.events: list[IDirectorEvent] = []
        logger.debug(f"DirectorComponent({self.name})")

    def addevent(self, event: IDirectorEvent) -> None:
        self.events.append(event)

    def tonpc(self, target_npc_name: str, extended_context: ExtendedContext) -> List[str]:
        batch: List[str] = []
        for event in self.events:
            batch.append(event.tonpc(target_npc_name, extended_context))
        return batch
    
    def tostage(self, target_stage_name: str, extended_context: ExtendedContext) -> List[str]:
        batch: List[str] = []
        for event in self.events:
            batch.append(event.tostage(target_stage_name, extended_context))
        return batch

    def clear(self) -> None:
        self.events.clear()
