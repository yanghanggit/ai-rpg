from auxiliary.extended_context import ExtendedContext
from typing import List
from loguru import logger
from collections import namedtuple
from director_event import DirectorEvent


## yh 第一个 扩展型组件，用于处理导演系统的事件
DirectorComponentPrototype = namedtuple('DirectorComponentPrototype', 'name')
class DirectorComponent(DirectorComponentPrototype):

    def __init__(self) -> None:
        self.events: list[DirectorEvent] = []
        logger.debug(f"DirectorComponent({self.name})")

    def addevent(self, event: DirectorEvent) -> None:
        self.events.append(event)

    def convert(self, targetname: str, extended_context: ExtendedContext) -> List[str]:
        batch: List[str] = []
        for event in self.events:
            batch.append(event.convert(targetname, extended_context))
        return batch

    def clear(self) -> None:
        self.events.clear()
