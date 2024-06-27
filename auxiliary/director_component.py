from entitas import Entity # type: ignore
from my_entitas.extended_context import ExtendedContext
from auxiliary.components import PlayerComponent, PlayerIsWebClientComponent, PlayerIsTerminalClientComponent
from typing import List
from collections import namedtuple
from auxiliary.director_event import IDirectorEvent
from builtin_prompt.cn_builtin_prompt import replace_mentions_of_your_name_with_you_prompt
from loguru import logger

##扩展型组件，用于处理导演系统的事件
##########################################################################################################################
DirectorComponentPrototype = namedtuple('DirectorComponentPrototype', 'name')
class StageDirectorComponent(DirectorComponentPrototype):

    def __init__(self) -> None:
        self._events: List[IDirectorEvent] = []
##########################################################################################################################
    def add_event(self, event: IDirectorEvent) -> None:
        self._events.append(event)
##########################################################################################################################
    def to_actor(self, target_actor_name: str, extended_context: ExtendedContext) -> List[str]:
        batch: List[str] = []
        for event in self._events:
            res = event.to_actor(target_actor_name, extended_context)
            if res != "":
                res = replace_mentions_of_your_name_with_you_prompt(res, target_actor_name)
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
        from systems.whisper_action_system import StageOrActorWhisperEvent
        from systems.speak_action_system import StageOrActorSpeakEvent
        from systems.broadcast_action_system import StageOrActorBroadcastEvent
        from systems.perception_action_system import ActorPerceptionEvent
        from systems.check_status_action_system import ActorCheckStatusEvent
        ###
        batch: List[str] = []
        for event in self._events:

            ignore_type1 = isinstance(event, StageOrActorWhisperEvent) \
            or isinstance(event, StageOrActorSpeakEvent) \
            or isinstance(event, StageOrActorBroadcastEvent)
            if ignore_type1:
                # 不收集这个消息。
                continue
            
            if self.is_player_web_client(target_actor_name, extended_context):
                ignore_type2 = isinstance(event, ActorPerceptionEvent) or isinstance(event, ActorCheckStatusEvent)
                if ignore_type2:
                    # 立即模式下（就是Web模式下），不收集这个消息。马上反应，就是终端测试下收集这个消息。
                    continue
            
            res = event.to_actor(target_actor_name, extended_context)
            if res != "":
                res = replace_mentions_of_your_name_with_you_prompt(res, target_actor_name)
                batch.append(res)
        return batch
##########################################################################################################################
    def is_player_web_client(self, actor_name: str, extended_context: ExtendedContext) -> bool:
        entity = extended_context.get_actor_entity(actor_name)
        if entity is None:
            assert False, f"ActorEntity not found in entity:{actor_name}"
            return False
        
        if not entity.has(PlayerComponent):
            assert False, f"PlayerComponent not found in entity:{actor_name}"
            return False
        
        assert entity.has(PlayerIsWebClientComponent) or entity.has(PlayerIsTerminalClientComponent)
        return entity.has(PlayerIsWebClientComponent)
##########################################################################################################################
##########################################################################################################################
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