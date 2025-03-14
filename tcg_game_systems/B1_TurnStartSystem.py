# from overrides import override
# from entitas import ExecuteProcessor, Matcher  # type: ignore
# from entitas.entity import Entity

# # from game.tcg_game_context import TCGGameContext
# from game.tcg_game import TCGGame
# from typing import List, cast

# # from tcg_models.v_0_0_1 import ActorInstance
# from components.components import ActorComponent, AttributeCompoment


# class B1_TurnStartSystem(ExecuteProcessor):

#     def __init__(self, game_context: TCGGame) -> None:
#         self._game: TCGGame = game_context

#     @override
#     def execute(self) -> None:
#         if self._game._battle_manager._battle_end_flag:
#             return
#         if self._game._battle_manager._new_turn_flag:
#             self._fresh_turn()

#     def _fresh_turn(self) -> None:
#         actor_entities = self._game.get_group(
#             Matcher(
#                 all_of=[
#                     ActorComponent,
#                 ],
#             )
#         ).entities
#         if len(actor_entities) == 0:
#             return

#         # 删掉不和player在同一个stage里的
#         current_stage = self._game.get_current_stage_entity()
#         assert current_stage is not None
#         actor_entities = {
#             actor
#             for actor in actor_entities
#             if actor.get(ActorComponent).current_stage == current_stage._name
#         }

#         # 更新回合数
#         self._game._battle_manager._turn_num += 1
#         self._game._battle_manager.add_history(
#             f"回合{self._game._battle_manager._turn_num}开始！"
#         )
#         # 需不需要让角色也接收这个信息？

#         # 双重保险，清一下新回合的东西
#         self._game._battle_manager._order_queue.clear()
#         self._game._battle_manager._hits_stack.stack.clear()

#         # 重置flag
#         self._game._battle_manager._battle_end_flag = False
#         self._game._battle_manager._new_turn_flag = False
#         self._game._battle_manager._event_msg.done_flag = False

#         # 根据速度给每个活着的排行动顺序
#         self._set_order(list(actor_entities.copy()))

#         # 对每个角色，更新状态，没考虑回合开始时触发的事件
#         for actor in actor_entities:
#             comp = actor.get(AttributeCompoment)
#             # 减少buff轮数
#             buffs = comp.buffs
#             remove_list = []
#             for buff_name, last_time in buffs.items():
#                 buffs[buff_name] -= 1
#                 if buffs[buff_name] <= 0:
#                     msg = f"{actor._name} 的 {buff_name} 的持续时间结束了。"
#                     self._game._battle_manager.add_history(msg)
#                     remove_list.append(buff_name)
#                     # 要不要加到角色的history里?
#             for buff_name in remove_list:
#                 buffs.pop(buff_name)
#             # 回复行动力
#             actor.replace(
#                 AttributeCompoment,
#                 comp.name,
#                 comp.hp,
#                 comp.maxhp,
#                 comp.max_action_times,
#                 comp.max_action_times,
#                 comp.strength,
#                 comp.agility,
#                 comp.wisdom,
#                 comp.buffs,
#                 comp.active_skills,
#                 comp.trigger_skills,
#             )

#     def _set_order(self, actor_entities: List[Entity]) -> None:
#         actor_list = sorted(
#             (actor for actor in actor_entities if actor.get(AttributeCompoment).hp > 0),
#             key=lambda x: x.get(AttributeCompoment).agility,
#             reverse=True,
#         )
#         for actor in actor_list:
#             self._game._battle_manager._order_queue.append(
#                 actor.get(AttributeCompoment).name
#             )
