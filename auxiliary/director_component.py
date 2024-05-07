from entitas import Entity # type: ignore
from auxiliary.extended_context import ExtendedContext
from typing import List
from collections import namedtuple
from auxiliary.director_event import IDirectorEvent
from auxiliary.cn_builtin_prompt import replace_all_mentions_of_your_name_with_you
from auxiliary.components import StageComponent

## yh 第一个 扩展型组件，用于处理导演系统的事件
DirectorComponentPrototype = namedtuple('DirectorComponentPrototype', 'name')
class StageDirectorComponent(DirectorComponentPrototype):

    def __init__(self) -> None:
        self.events: list[IDirectorEvent] = []

    def addevent(self, event: IDirectorEvent) -> None:
        self.events.append(event)

    def tonpc(self, target_npc_name: str, extended_context: ExtendedContext) -> List[str]:
        batch: List[str] = []
        for event in self.events:
            res = event.tonpc(target_npc_name, extended_context)
            if res != "":
                res = replace_all_mentions_of_your_name_with_you(res, target_npc_name)
                batch.append(res)
        return batch
    
    def tostage(self, target_stage_name: str, extended_context: ExtendedContext) -> List[str]:
        batch: List[str] = []
        for event in self.events:
            res = event.tostage(target_stage_name, extended_context)
            if res != "":
                batch.append(res)
        return batch

    def clear(self) -> None:
        self.events.clear()

#
def notify_stage_director(context: ExtendedContext, entity: Entity, directevent: IDirectorEvent) -> bool:
    stageentity = context.safe_get_stage_entity(entity)
    if stageentity is None:
        return False
    directorcomp: StageDirectorComponent = stageentity.get(StageDirectorComponent)
    directorcomp.addevent(directevent)
    return True