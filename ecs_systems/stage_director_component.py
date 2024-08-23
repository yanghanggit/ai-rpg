# from entitas import Entity  # type: ignore
# from rpg_game.rpg_entitas_context import RPGEntitasContext
# from ecs_systems.components import (
#     PlayerComponent,
#     PlayerIsWebClientComponent,
#     PlayerIsTerminalClientComponent,
# )
# from typing import List, Any
# from collections import namedtuple
# #from ecs_systems.stage_director_event import IStageDirectorEvent
# import ecs_systems.cn_builtin_prompt as builtin_prompt


# OnEnterStageComponent = namedtuple("OnEnterStageComponent", "stage_name")

# ##扩展型组件，用于处理导演系统的事件
# ##############################################################################################################################################################
# StageDirectorComponentPrototype = namedtuple("StageDirectorComponentPrototype", "name")


# class StageDirectorComponent(StageDirectorComponentPrototype):

#     # @staticmethod
#     # def add_event_to_stage_director(
#     #     context: RPGEntitasContext, entity: Entity, direct_event: IStageDirectorEvent
#     # ) -> None:
#     #     stage_entity = context.safe_get_stage_entity(entity)
#     #     if stage_entity is None or not stage_entity.has(StageDirectorComponent):
#     #         return
#     #     stage_entity.get(StageDirectorComponent).add_event(direct_event)

#     ##############################################################################################################################################################
#     def __init__(self, args: Any) -> None:
#         assert len(args) == 1
#         assert self.name == args[0]
#         #self._director_events: List[IStageDirectorEvent] = []

#     ##############################################################################################################################################################
#     # def add_event(self, event: IStageDirectorEvent) -> None:
#     #     assert not event in self._director_events
#     #     self._director_events.append(event)

#     ##############################################################################################################################################################
#     def to_actor(
#         self, target_actor_name: str, extended_context: RPGEntitasContext
#     ) -> List[str]:
#         return self._to_actor(
#             target_actor_name, extended_context, self._director_events
#         )

#     ##############################################################################################################################################################
#     def _to_actor(
#         self,
#         target_actor_name: str,
#         extended_context: RPGEntitasContext,
#         director_events: List[IStageDirectorEvent],
#     ) -> List[str]:
#         ret: List[str] = []
#         for event in director_events:
#             event_content = event.to_actor(target_actor_name, extended_context)
#             if event_content != "":
#                 event_content_replace_mentions_of_your_name = (
#                     builtin_prompt.replace_mentions_of_your_name_with_you_prompt(
#                         event_content, target_actor_name
#                     )
#                 )
#                 ret.append(event_content_replace_mentions_of_your_name)
#         return ret

#     ##############################################################################################################################################################
#     def to_stage(
#         self, target_stage_name: str, extended_context: RPGEntitasContext
#     ) -> List[str]:
#         return self._to_stage(
#             target_stage_name, extended_context, self._director_events
#         )

#     ##############################################################################################################################################################
#     def _to_stage(
#         self,
#         target_stage_name: str,
#         extended_context: RPGEntitasContext,
#         director_events: List[IStageDirectorEvent],
#     ) -> List[str]:
#         ret: List[str] = []
#         for event in director_events:
#             event_content = event.to_stage(target_stage_name, extended_context)
#             if event_content != "":
#                 ret.append(event_content)
#         return ret

#     ##############################################################################################################################################################
#     def clear(self) -> None:
#         self._director_events.clear()

#     ##############################################################################################################################################################
#     def to_player(
#         self, target_actor_name: str, extended_context: RPGEntitasContext
#     ) -> List[str]:
#         return self._to_player(
#             target_actor_name, extended_context, self._director_events
#         )

#     ##############################################################################################################################################################
#     def _to_player(
#         self,
#         target_actor_name: str,
#         extended_context: RPGEntitasContext,
#         director_events: List[IStageDirectorEvent],
#     ) -> List[str]:
#         # 哭，循环引用，临时就这么写吧, 这些不用客户端显示
#         from ecs_systems.whisper_action_system import StageOrActorWhisperEvent
#         from ecs_systems.speak_action_system import StageOrActorSpeakEvent
#         from ecs_systems.broadcast_action_system import StageOrActorBroadcastEvent
#         from ecs_systems.perception_action_system import ActorPerceptionEvent
#         from ecs_systems.check_status_action_system import ActorCheckStatusEvent

#         ###
#         ret: List[str] = []

#         for event in director_events:

#             need_ignore_conversation_event = (
#                 isinstance(event, StageOrActorWhisperEvent)
#                 or isinstance(event, StageOrActorSpeakEvent)
#                 or isinstance(event, StageOrActorBroadcastEvent)
#             )
#             if need_ignore_conversation_event:
#                 # 不收集这个消息。
#                 continue

#             if self.is_player_web_client(target_actor_name, extended_context):
#                 if isinstance(event, ActorPerceptionEvent) or isinstance(
#                     event, ActorCheckStatusEvent
#                 ):
#                     # 立即模式下（就是Web模式下），不收集这个消息。马上反应，就是终端测试下收集这个消息。
#                     continue

#             event_content = event.to_actor(target_actor_name, extended_context)
#             if event_content != "":
#                 event_content_replace_mentions_of_your_name = (
#                     builtin_prompt.replace_mentions_of_your_name_with_you_prompt(
#                         event_content, target_actor_name
#                     )
#                 )
#                 ret.append(event_content_replace_mentions_of_your_name)

#         return ret

#     ##############################################################################################################################################################
#     def is_player_web_client(
#         self, actor_name: str, extended_context: RPGEntitasContext
#     ) -> bool:
#         entity = extended_context.get_actor_entity(actor_name)
#         if entity is None or not entity.has(PlayerComponent):
#             return False
#         assert entity.has(PlayerIsWebClientComponent) or entity.has(
#             PlayerIsTerminalClientComponent
#         )
#         return entity.has(PlayerIsWebClientComponent)


# ##############################################################################################################################################################
