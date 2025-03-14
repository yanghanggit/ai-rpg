# from overrides import override
# from pydantic import BaseModel
# from agent.chat_request_handler import ChatRequestHandler
# from entitas import ExecuteProcessor  # type: ignore

# # from entitas.entity import Entity
# from game.tcg_game_context import TCGGameContext
# from game.tcg_game import TCGGame
# from typing import Deque, List, cast

# # from tcg_models.v_0_0_1 import ActorInstance, ActiveSkill
# from components.components import (
#     AttributeCompoment,
#     FinalAppearanceComponent,
#     StageEnvironmentComponent,
# )
# from loguru import logger


# class B3_ActorTriggerSystem(ExecuteProcessor):

#     def __init__(self, context: TCGGameContext) -> None:
#         self._context: TCGGameContext = context
#         self._game: TCGGame = cast(TCGGame, context._game)
#         assert self._game is not None

#     @override
#     def execute(self) -> None:
#         pass

#     @override
#     async def a_execute1(self) -> None:
#         pass

#     async def _check(self) -> None:
#         if self._game._battle_manager._new_turn_flag:
#             return
#         if self._game._battle_manager._battle_end_flag:
#             return
#         if len(self._game._battle_manager._order_queue) == 0:
#             return
#         if len(self._game._battle_manager._hits_stack) == 0:
#             return

#         for hit in reversed(self._game._battle_manager._hits_stack):
#             source_name = hit.source
#             target_name = hit.target
#             source = self._context.get_entity_by_name(source_name)
#             target = self._context.get_entity_by_name(target_name)
#             if source is None:
#                 assert False, "source is None"
#             if target is None:
#                 assert False, "target is None"
#             source_comp = source.get(AttributeCompoment)
#             target_comp = target.get(AttributeCompoment)
#             if source_comp is None:
#                 assert False, "source_comp is None"
#             if target_comp is None:
#                 assert False, "target_comp is None"
