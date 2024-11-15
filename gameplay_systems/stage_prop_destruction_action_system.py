# from entitas import Entity, Matcher, ReactiveProcessor, GroupEvent  # type: ignore
# from typing import final, override
# from my_components.action_components import (
#     StagePropDestructionAction,
# )
# from rpg_game.rpg_entitas_context import RPGEntitasContext
# from rpg_game.rpg_game import RPGGame
# from extended_systems.prop_file import PropFile
# from my_components.components import StageComponent
# from my_models.event_models import AgentEvent


# ################################################################################################################################################
# def _generate_stage_prop_missing_notification(stage_name: str, prop_name: str) -> str:
#     return f"""# 提示: 场景 {stage_name} 的道具 {prop_name} 已经不在了，无法对其进行任何操作。
# ## 原因分析:
# 该道具可能已被摧毁并移出场景，或被其他角色拾取。
# """


# ################################################################################################################################################
# def _generate_stage_prop_destruction_statement_prompt(
#     stage_name: str, prop_name: str
# ) -> str:
#     return f"""# 发生事件: 场景 {stage_name} 的道具 {prop_name} 已经被摧毁。"""


# ################################################################################################################################################
# ################################################################################################################################################
# ################################################################################################################################################
# @final
# class StagePropDestructionActionSystem(ReactiveProcessor):

#     def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame) -> None:
#         super().__init__(context)
#         self._context: RPGEntitasContext = context
#         self._game: RPGGame = rpg_game

#     ############################################################################################################
#     @override
#     def get_trigger(self) -> dict[Matcher, GroupEvent]:
#         return {Matcher(StagePropDestructionAction): GroupEvent.ADDED}

#     ############################################################################################################
#     @override
#     def filter(self, entity: Entity) -> bool:
#         return entity.has(StagePropDestructionAction) and entity.has(StageComponent)

#     ############################################################################################################
#     @override
#     def react(self, stage_entities: list[Entity]) -> None:
#         for stage_entity in stage_entities:
#             self._process_stage_prop_destruction(stage_entity)

#     ############################################################################################################
#     def _process_stage_prop_destruction(self, stage_entity: Entity) -> None:
#         stage_prop_destruction_action = stage_entity.get(StagePropDestructionAction)
#         if len(stage_prop_destruction_action.values) == 0:
#             return

#         for prop_name in stage_prop_destruction_action.values:

#             prop_file = self._context._file_system.get_file(
#                 PropFile, stage_prop_destruction_action.name, prop_name
#             )
#             if prop_file is None:
#                 self._notify_stage_prop_loss_event(stage_entity, prop_name)
#                 continue

#             self._context._file_system.remove_file(prop_file)
#             self._notify_stage_prop_destruction_event(stage_entity, prop_name)

#     ############################################################################################################
#     def _notify_stage_prop_loss_event(
#         self, stage_entity: Entity, prop_name: str
#     ) -> None:
#         safe_name = self._context.safe_get_entity_name(stage_entity)
#         self._context.notify_event(
#             set({stage_entity}),
#             AgentEvent(
#                 message=_generate_stage_prop_missing_notification(safe_name, prop_name)
#             ),
#         )

#     ############################################################################################################
#     def _notify_stage_prop_destruction_event(
#         self, stage_entity: Entity, prop_name: str
#     ) -> None:
#         safe_name = self._context.safe_get_entity_name(stage_entity)
#         self._context.notify_event(
#             set({stage_entity}),
#             AgentEvent(
#                 message=_generate_stage_prop_destruction_statement_prompt(
#                     safe_name, prop_name
#                 )
#             ),
#         )

#     ############################################################################################################
