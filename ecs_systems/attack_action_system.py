# from entitas import Matcher, ReactiveProcessor, GroupEvent, Entity  # type: ignore
# from ecs_systems.action_components import AttackAction, DeadAction
# from ecs_systems.components import (
#     RPGAttributesComponent,
#     RPGCurrentWeaponComponent,
#     RPGCurrentClothesComponent,
# )
# from rpg_game.rpg_entitas_context import RPGEntitasContext

# # from my_agent.agent_action import AgentAction
# from loguru import logger
# from ecs_systems.stage_director_component import StageDirectorComponent
# from ecs_systems.stage_director_event import IStageDirectorEvent
# from typing import cast, override
# import gameplay.conversation_helper
# import ecs_systems.cn_builtin_prompt as builtin_prompt
# import file_system.helper
# from file_system.files_def import PropFile


# ####################################################################################################################################
# ####################################################################################################################################
# ####################################################################################################################################
# class StageOrActorKillEvent(IStageDirectorEvent):
#     """
#     事件通知：在Attack之后，直接杀死了某个人。
#     """

#     def __init__(self, attacker: str, target: str) -> None:
#         self.attacker: str = attacker
#         self.target: str = target

#     def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
#         event = builtin_prompt.kill_prompt(self.attacker, self.target)
#         return event

#     def to_stage(self, stagename: str, extended_context: RPGEntitasContext) -> str:
#         event = builtin_prompt.kill_prompt(self.attacker, self.target)
#         return event


# ####################################################################################################################################
# ####################################################################################################################################
# ####################################################################################################################################
# class StageOrActorAttackEvent(IStageDirectorEvent):
#     """
#     事件通知：Attack行动的通知
#     """

#     def __init__(
#         self, attacker: str, target: str, damage: int, curhp: int, maxhp: int
#     ) -> None:
#         self.attacker: str = attacker
#         self.target: str = target
#         self.damage: int = damage
#         self.curhp: int = curhp
#         self.maxhp: int = maxhp

#     def to_actor(self, actor_name: str, extended_context: RPGEntitasContext) -> str:
#         event = builtin_prompt.attack_prompt(
#             self.attacker, self.target, self.damage, self.curhp, self.maxhp
#         )
#         return event

#     def to_stage(self, stagename: str, extended_context: RPGEntitasContext) -> str:
#         event = builtin_prompt.attack_prompt(
#             self.attacker, self.target, self.damage, self.curhp, self.maxhp
#         )
#         return event


# ####################################################################################################################################
# ####################################################################################################################################
# ####################################################################################################################################
# class AttackActionSystem(ReactiveProcessor):
#     """
#     处理：AttackAction 的系统
#     要求：AttackAction 和 SimpleRPGAttrComponent 必须同时存在，否则无法处理。
#     """

#     def __init__(self, context: RPGEntitasContext) -> None:
#         super().__init__(context)
#         self._context: RPGEntitasContext = context

#     ######################################################################################################################################################
#     @override
#     def get_trigger(self) -> dict[Matcher, GroupEvent]:
#         return {Matcher(AttackAction): GroupEvent.ADDED}

#     ######################################################################################################################################################
#     @override
#     def filter(self, entity: Entity) -> bool:
#         return entity.has(AttackAction) and entity.has(RPGAttributesComponent)

#     ######################################################################################################################################################
#     @override
#     def react(self, entities: list[Entity]) -> None:
#         for entity in entities:
#             self.handle(entity)

#     ######################################################################################################################################################
#     # todo 函数太长了，后续可以考虑拆分！！！！！
#     def handle(self, actor_or_stage_entity: Entity) -> None:
#         context = self._context
#         rpg_attr_comp = actor_or_stage_entity.get(RPGAttributesComponent)
#         attack_action = actor_or_stage_entity.get(AttackAction)
#         # action: AgentAction = attack_action.action
#         for value_as_target_name in attack_action.values:

#             target_entity = context.get_entity_by_name(value_as_target_name)
#             if target_entity is None:
#                 logger.warning(
#                     f"攻击者{attack_action.name}意图攻击的对象{value_as_target_name}无法被找到,本次攻击无效."
#                 )
#                 continue

#             if not target_entity.has(RPGAttributesComponent):
#                 logger.warning(
#                     f"攻击者{attack_action.name}意图攻击的对象{value_as_target_name}没有SimpleRPGComponent,本次攻击无效."
#                 )
#                 continue

#             conversation_check_error = (
#                 gameplay.conversation_helper.check_conversation_enable(
#                     self._context, actor_or_stage_entity, value_as_target_name
#                 )
#             )
#             if (
#                 conversation_check_error
#                 != gameplay.conversation_helper.ErrorConversationEnable.VALID
#             ):
#                 if (
#                     conversation_check_error
#                     == gameplay.conversation_helper.ErrorConversationEnable.TARGET_DOES_NOT_EXIST
#                 ):
#                     logger.error(
#                         f"攻击者{attack_action.name}意图攻击的对象{value_as_target_name}不存在,本次攻击无效."
#                     )
#                     # todo 是否应该因该提示发起人？做一下矫正？

#                 elif (
#                     conversation_check_error
#                     == gameplay.conversation_helper.ErrorConversationEnable.WITHOUT_BEING_IN_STAGE
#                 ):
#                     logger.error(
#                         f"攻击者{attack_action.name}不在任何舞台上,本次攻击无效.? 这是一个严重的错误！"
#                     )
#                     assert False  # 不要继续了，因为出现了严重的错误

#                 elif (
#                     conversation_check_error
#                     == gameplay.conversation_helper.ErrorConversationEnable.NOT_IN_THE_SAME_STAGE
#                 ):

#                     # 名字拿出来，看一下
#                     assert actor_or_stage_entity is not None
#                     stage1 = self._context.safe_get_stage_entity(actor_or_stage_entity)
#                     assert stage1 is not None
#                     stage1_name = self._context.safe_get_entity_name(stage1)

#                     assert target_entity is not None
#                     stage2 = self._context.safe_get_stage_entity(target_entity)
#                     assert stage2 is not None
#                     stage2_name = self._context.safe_get_entity_name(stage2)

#                     logger.error(
#                         f"攻击者 {attack_action.name}:{stage1_name} 和攻击对象 {value_as_target_name}:{stage2_name} 不在同一个舞台上,本次攻击无效."
#                     )

#                 # 跳过去，不能继续了！
#                 continue

#             # 目标拿出来
#             target_rpg_comp = target_entity.get(RPGAttributesComponent)

#             # 简单的战斗计算，简单的血减掉伤害
#             hp = target_rpg_comp.hp
#             damage = self.final_attack_val(actor_or_stage_entity)  # rpgcomp.attack
#             # 必须控制在0和最大值之间
#             damage = damage - self.final_defense_val(
#                 target_entity
#             )  # targetsrpgcomp.defense
#             if damage < 0:
#                 damage = 0

#             lefthp = hp - damage
#             lefthp = max(0, min(lefthp, target_rpg_comp.maxhp))

#             # 结果修改
#             target_entity.replace(
#                 RPGAttributesComponent,
#                 target_rpg_comp.name,
#                 target_rpg_comp.maxhp,
#                 lefthp,
#                 target_rpg_comp.attack,
#                 target_rpg_comp.defense,
#             )

#             ##死亡是关键
#             isdead = lefthp <= 0

#             ## 死后处理大流程，step1——道具怎么办？后续可以封装的复杂一些: 夺取唯一性道具.
#             if isdead:
#                 pass
#                 # self.unique_prop_be_taken_away(actor_or_stage_entity, target_entity)

#             ## 可以加一些别的。。。。。。。。。。。。

#             ## 。。。。。。。。。。。。。。。。。。。

#             ## 死后处理大流程，step最后——死亡组件系统必须要添加
#             if isdead:
#                 if not target_entity.has(DeadAction):
#                     # 复制一个，不用以前的，怕GC不掉
#                     target_entity.add(
#                         DeadAction,
#                         attack_action.name,
#                         attack_action.action_name,
#                         attack_action.values,
#                     )

#             ## 导演系统，单独处理，有旧的代码
#             if isdead:
#                 # 直接打死
#                 StageDirectorComponent.add_event_to_stage_director(
#                     context,
#                     actor_or_stage_entity,
#                     StageOrActorKillEvent(rpg_attr_comp.name, value_as_target_name),
#                 )
#             else:
#                 # 没有打死，就把伤害通知给导演
#                 StageDirectorComponent.add_event_to_stage_director(
#                     context,
#                     actor_or_stage_entity,
#                     StageOrActorAttackEvent(
#                         rpg_attr_comp.name,
#                         value_as_target_name,
#                         damage,
#                         lefthp,
#                         target_rpg_comp.maxhp,
#                     ),
#                 )

#     ######################################################################################################################################################
#     ## 杀死对方就直接夺取唯一性道具。
#     # def unique_prop_be_taken_away(
#     #     self, attacker_entity: Entity, target_entity: Entity
#     # ) -> None:

#     #     rpg_attr_comp = attacker_entity.get(RPGAttributesComponent)
#     #     target_rpg_attr_comp = target_entity.get(RPGAttributesComponent)
#     #     logger.info(f"{rpg_attr_comp.name} kill => {target_rpg_attr_comp.name}")

#     #     prop_files = self._context._file_system.get_files(
#     #         PropFile, target_rpg_attr_comp.name
#     #     )
#     #     for prop_file in prop_files:
#     #         if not prop_file.is_unique:
#     #             logger.info(
#     #                 f"the propfile {prop_file._name} is not unique, so it will not be taken away."
#     #             )
#     #             continue
#     #         # 交换文件，即交换道具文件即可
#     #         # self._context._file_system.give_prop_file(target_rpg_comp.name, rpg_comp.name, prop_file._name)
#     #         file_system.helper.give_prop_file(
#     #             self._context._file_system,
#     #             target_rpg_attr_comp.name,
#     #             rpg_attr_comp.name,
#     #             prop_file._name,
#     #         )

#     ######################################################################################################################################################
#     def final_attack_val(self, entity: Entity) -> int:
#         # 最后的攻击力
#         final: int = 0

#         # # 基础的伤害
#         # rpg_attr_comp = entity.get(RPGAttributesComponent)
#         # final += cast(int, rpg_attr_comp.attack)

#         # # 计算武器带来的伤害
#         # if entity.has(RPGCurrentWeaponComponent):
#         #     weaponcomp = entity.get(RPGCurrentWeaponComponent)
#         #     final += cast(int, weaponcomp.attack)

#         return final

#     ######################################################################################################################################################
#     def final_defense_val(self, entity: Entity) -> int:
#         # 最后的防御力
#         final: int = 0

#         # 基础防御力
#         # rpg_attr_comp = entity.get(RPGAttributesComponent)
#         # final += cast(int, rpg_attr_comp.defense)

#         # # 计算衣服带来的防御力
#         # if entity.has(RPGCurrentClothesComponent):
#         #     armorcomp = entity.get(RPGCurrentClothesComponent)
#         #     final += cast(int, armorcomp.defense)

#         return final


# ######################################################################################################################################################
