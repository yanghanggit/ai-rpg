# from entitas import ReactiveProcessor, Matcher, GroupEvent, Entity  # type: ignore
# from rpg_game.rpg_entitas_context import RPGEntitasContext
# from gameplay_systems.components import StageComponent, ActorComponent
# from gameplay_systems.action_components import PerceptionAction, DeadAction
# from loguru import logger
# from typing import List, Dict, override
# import gameplay_systems.cn_builtin_prompt as builtin_prompt
# from file_system.files_def import PropFile
# from rpg_game.rpg_game import RPGGame


# ####################################################################################################################################
# ####################################################################################################################################
# ####################################################################################################################################
# class PerceptionActionHelper:
#     """
#     辅助的类，把常用的行为封装到这里，方便别的地方再调用
#     """

#     def __init__(self, context: RPGEntitasContext):
#         self._context: RPGEntitasContext = context
#         self._props_in_stage: List[str] = []
#         self._actors_in_stage: Dict[str, str] = {}

#     ###################################################################################################################
#     def perception(self, entity: Entity) -> None:
#         stage_entity = self._context.safe_get_stage_entity(entity)
#         if stage_entity is None:
#             logger.error(
#                 f"PerceptionActionHelper: {self._context.safe_get_entity_name(entity)} can't find the stage"
#             )
#             return
#         self._actors_in_stage = self.perception_actors_in_stage(entity, stage_entity)
#         self._props_in_stage = self.perception_props_in_stage(entity, stage_entity)

#     ###################################################################################################################
#     def perception_actors_in_stage(
#         self, entity: Entity, stage_entity: Entity
#     ) -> Dict[str, str]:
#         all: Dict[str, str] = self._context.get_appearance_in_stage(entity)
#         safe_name = self._context.safe_get_entity_name(entity)
#         all.pop(safe_name, None)  # 删除自己，自己是不必要的。
#         assert all.get(safe_name) is None
#         return all

#     ###################################################################################################################
#     def perception_props_in_stage(
#         self, entity: Entity, stage_entity: Entity
#     ) -> List[str]:
#         res: List[str] = []
#         stage_comp = stage_entity.get(StageComponent)
#         prop_files = self._context._file_system.get_files(PropFile, stage_comp.name)
#         for prop in prop_files:
#             res.append(prop._name)
#         return res


# ####################################################################################################################################
# ####################################################################################################################################
# ####################################################################################################################################
# class PerceptionActionSystem(ReactiveProcessor):
#     """
#     处理PerceptionActionComponent行为的系统
#     """

#     def __init__(self, context: RPGEntitasContext, rpg_game: RPGGame):
#         super().__init__(context)
#         self._context: RPGEntitasContext = context
#         self._game: RPGGame = rpg_game

#     ###################################################################################################################
#     @override
#     def get_trigger(self) -> dict[Matcher, GroupEvent]:
#         return {Matcher(PerceptionAction): GroupEvent.ADDED}

#     ###################################################################################################################
#     @override
#     def filter(self, entity: Entity) -> bool:
#         return (
#             entity.has(PerceptionAction)
#             and entity.has(ActorComponent)
#             and not entity.has(DeadAction)
#         )

#     ###################################################################################################################
#     @override
#     def react(self, entities: list[Entity]) -> None:
#         for entity in entities:
#             self.perception(entity)

#     ###################################################################################################################
#     def perception(self, entity: Entity) -> None:
#         safe_name = self._context.safe_get_entity_name(entity)
#         #
#         helper = PerceptionActionHelper(self._context)
#         helper.perception(entity)
#         #
#         stage_entity = self._context.safe_get_stage_entity(entity)
#         assert stage_entity is not None
#         safe_stage_name = self._context.safe_get_entity_name(stage_entity)

#         self._context.add_agent_context_message(
#             set({entity}),
#             builtin_prompt.make_perception_action_prompt(
#                 safe_name,
#                 safe_stage_name,
#                 helper._actors_in_stage,
#                 helper._props_in_stage,
#             ),
#         )


# ###################################################################################################################
