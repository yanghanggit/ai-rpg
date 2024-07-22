from entitas import Entity # type: ignore
from my_entitas.extended_context import ExtendedContext
from ecs_systems.components import PlayerComponent, PlayerIsWebClientComponent, PlayerIsTerminalClientComponent
from typing import List, Any
from collections import namedtuple
from ecs_systems.stage_director_event import IStageDirectorEvent
from builtin_prompt.cn_builtin_prompt import replace_mentions_of_your_name_with_you_prompt
from loguru import logger

##扩展型组件，用于处理导演系统的事件
##########################################################################################################################
StageDirectorComponentPrototype = namedtuple('StageDirectorComponentPrototype', 'name')
class StageDirectorComponent(StageDirectorComponentPrototype):

    def __init__(self, args: Any) -> None:
        assert len(args) == 1
        assert self.name == args[0]
        self._events: List[IStageDirectorEvent] = []
##########################################################################################################################
    def add_event(self, event: IStageDirectorEvent) -> None:
        assert not event in self._events
        self._events.append(event)
##########################################################################################################################
    def to_actor(self, target_actor_name: str, extended_context: ExtendedContext) -> List[str]:
        result: List[str] = []
        for event in self._events:
            res = event.to_actor(target_actor_name, extended_context)
            if res != "":
                res = replace_mentions_of_your_name_with_you_prompt(res, target_actor_name)
                result.append(res)
        return result
##########################################################################################################################
    def to_stage(self, target_stage_name: str, extended_context: ExtendedContext) -> List[str]:
        result: List[str] = []
        for event in self._events:
            res = event.to_stage(target_stage_name, extended_context)
            if res != "":
                result.append(res)
        return result
##########################################################################################################################
    def clear(self) -> None:
        self._events.clear()
##########################################################################################################################
    def to_player(self, target_actor_name: str, extended_context: ExtendedContext) -> List[str]:
        # 哭，循环引用，临时就这么写吧, 这些不用客户端显示
        from ecs_systems.whisper_action_system import StageOrActorWhisperEvent
        from ecs_systems.speak_action_system import StageOrActorSpeakEvent
        from ecs_systems.broadcast_action_system import StageOrActorBroadcastEvent
        from ecs_systems.perception_action_system import ActorPerceptionEvent
        from ecs_systems.check_status_action_system import ActorCheckStatusEvent
        ###
        result: List[str] = []

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
                result.append(res)

        return result
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
def notify_stage_director(context: ExtendedContext, entity: Entity, direct_event: IStageDirectorEvent) -> bool:
    stage_entity = context.safe_get_stage_entity(entity)
    if stage_entity is None or not stage_entity.has(StageDirectorComponent):
        logger.error(f"StageDirectorComponent not found in entity:{entity}")
        return False
    assert stage_entity.has(StageDirectorComponent)
    director_comp = stage_entity.get(StageDirectorComponent)
    director_comp.add_event(direct_event)
    return True
##########################################################################################################################