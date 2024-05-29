from entitas import Entity # type: ignore
from auxiliary.extended_context import ExtendedContext
from typing import List
from collections import namedtuple
from auxiliary.director_event import IDirectorEvent
from auxiliary.cn_builtin_prompt import replace_all_mentions_of_your_name_with_you
#from auxiliary.components import StageComponent
from loguru import logger

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


    def player_client_message(self, target_npc_name: str, extended_context: ExtendedContext) -> List[str]:
        # 哭，循环引用，临时就这么写吧
        from auxiliary.director_event import WhisperEvent
        from auxiliary.director_event import SpeakEvent
        from auxiliary.director_event import BroadcastEvent

        batch: List[str] = []
        for event in self.events:
            check = isinstance(event, WhisperEvent) or isinstance(event, SpeakEvent) or isinstance(event, BroadcastEvent)
            if check:
                # 这3种在TestPlayerUpdateClientMessageSystem会特殊处理，这里不用再导出了。
                continue
            res = event.tonpc(target_npc_name, extended_context)
            if res != "":
                res = replace_all_mentions_of_your_name_with_you(res, target_npc_name)
                batch.append(res)
        return batch

#
def notify_stage_director(context: ExtendedContext, entity: Entity, directevent: IDirectorEvent) -> bool:
    stageentity = context.safe_get_stage_entity(entity)
    if stageentity is None:
        logger.error(f"StageDirectorComponent not found in entity:{entity}")
        return False
    directorcomp: StageDirectorComponent = stageentity.get(StageDirectorComponent)
    directorcomp.addevent(directevent)
    return True