from entitas import Entity # type: ignore
from auxiliary.extended_context import ExtendedContext
from typing import List
from collections import namedtuple
from auxiliary.director_event import IDirectorEvent
from auxiliary.cn_builtin_prompt import replace_all_mentions_of_your_name_with_you
from loguru import logger

## yh 第一个 扩展型组件，用于处理导演系统的事件
####################################################################################################
DirectorComponentPrototype = namedtuple('DirectorComponentPrototype', 'name')
class StageDirectorComponent(DirectorComponentPrototype):

    def __init__(self) -> None:
        self._events: list[IDirectorEvent] = []
##########################################################################################################################
    def add_event(self, event: IDirectorEvent) -> None:
        self._events.append(event)
##########################################################################################################################
    def to_actor(self, target_actor_name: str, extended_context: ExtendedContext) -> List[str]:
        batch: List[str] = []
        for event in self._events:
            res = event.to_actor(target_actor_name, extended_context)
            if res != "":
                res = replace_all_mentions_of_your_name_with_you(res, target_actor_name)
                batch.append(res)
        return batch
##########################################################################################################################
    def to_stage(self, target_stage_name: str, extended_context: ExtendedContext) -> List[str]:
        batch: List[str] = []
        for event in self._events:
            res = event.to_stage(target_stage_name, extended_context)
            if res != "":
                batch.append(res)
        return batch
##########################################################################################################################
    def clear(self) -> None:
        self._events.clear()
##########################################################################################################################
    def to_player(self, target_actor_name: str, extended_context: ExtendedContext) -> List[str]:
        # 哭，循环引用，临时就这么写吧, 这些不用客户端显示
        from systems.whisper_action_system import WhisperEvent
        from systems.speak_action_system import SpeakEvent
        from systems.broadcast_action_system import BroadcastEvent
        from systems.perception_action_system import ActorPerceptionEvent
        from systems.check_status_action_system import ActorCheckStatusEvent
        ###
        batch: List[str] = []
        for event in self._events:
            check = isinstance(event, WhisperEvent) \
            or isinstance(event, SpeakEvent) \
            or isinstance(event, BroadcastEvent) \
            or isinstance(event, ActorPerceptionEvent) \
            or isinstance(event, ActorCheckStatusEvent)
            if check:
                continue
            res = event.to_actor(target_actor_name, extended_context)
            if res != "":
                res = replace_all_mentions_of_your_name_with_you(res, target_actor_name)
                batch.append(res)
        return batch
##########################################################################################################################
def notify_stage_director(context: ExtendedContext, entity: Entity, directevent: IDirectorEvent) -> bool:
    stageentity = context.safe_get_stage_entity(entity)
    if stageentity is None:
        logger.error(f"StageDirectorComponent not found in entity:{entity}")
        return False
    assert stageentity.has(StageDirectorComponent)
    directorcomp: StageDirectorComponent = stageentity.get(StageDirectorComponent)
    directorcomp.add_event(directevent)
    return True
##########################################################################################################################