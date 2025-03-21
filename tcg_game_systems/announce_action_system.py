# from components.components import StageComponent
# from entitas import Entity, Matcher, GroupEvent  # type: ignore
# from components.actions import (
#     AnnounceAction,
# )
# from typing import final, override
# from rpg_models.event_models import AnnounceEvent
# from tcg_game_systems.base_action_reactive_system import BaseActionReactiveSystem


# @final
# class AnnounceActionSystem(BaseActionReactiveSystem):

#     ####################################################################################################################################
#     @override
#     def get_trigger(self) -> dict[Matcher, GroupEvent]:
#         return {Matcher(AnnounceAction): GroupEvent.ADDED}

#     ####################################################################################################################################
#     @override
#     def filter(self, entity: Entity) -> bool:
#         return entity.has(AnnounceAction)

#     ####################################################################################################################################
#     @override
#     def react(self, entities: list[Entity]) -> None:
#         for entity in entities:
#             self._process_announce_action(entity)

#     ####################################################################################################################################
#     def _process_announce_action(self, entity: Entity) -> None:
#         stage_entity = self._game.safe_get_stage_entity(entity)
#         if stage_entity is None:
#             return

#         announce_action = entity.get(AnnounceAction)
#         assert announce_action is not None

#         stage_name = stage_entity.get(StageComponent).name

#         content = " ".join(announce_action.values)
#         self._game.broadcast_event(
#             stage_entity,
#             AnnounceEvent(
#                 message=_generate_announce_prompt(
#                     announce_action.name,
#                     stage_name,
#                     content,
#                 ),
#                 announcer_name=announce_action.name,
#                 stage_name=stage_name,
#                 content=content,
#             ),
#         )

#     ####################################################################################################################################


# def _generate_announce_prompt(speaker_name: str, stage_name: str, content: str) -> str:
#     return f"# 发生事件: {speaker_name} 对 {stage_name} 里的所有角色说: {content}"
