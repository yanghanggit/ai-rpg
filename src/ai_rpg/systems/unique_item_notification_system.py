# """
# 唯一道具通知系统
# 负责在战斗中为拥有唯一道具的角色添加提示消息。
# 确保每个唯一道具只有一条提示消息,避免重复。
# 该系统在每个游戏循环中执行,在 DrawCardsActionSystem 之前运行。
# """

# from typing import Final, List, final, override
# from loguru import logger
# from ..entitas import Entity, ReactiveProcessor, Matcher, GroupEvent
# from ..game.tcg_game import TCGGame
# from ..models import InventoryComponent, Item, DrawCardsAction, UniqueItem


# #######################################################################################################################################
# def _format_unique_item_notification(item: Item) -> str:
#     """
#     格式化唯一道具通知消息为 Markdown 格式。

#     Args:
#         item: 唯一道具对象

#     Returns:
#         str: 格式化的 Markdown 通知消息，不包含 UUID
#     """
#     return f"""# 提示！你拥有道具: {item.name}

# **类型**: {item.type.value}
# **数量**: {item.count}
# **描述**: {item.description}"""


# #######################################################################################################################################
# @final
# class UniqueItemNotificationSystem(ReactiveProcessor):
#     """
#     唯一道具通知系统。

#     在每个游戏循环中自动执行:
#     1. 检查当前是否在战斗中
#     2. 获取所有拥有库存的实体
#     3. 检查唯一道具并添加/更新提示消息
#     4. 确保提示消息的唯一性
#     """

#     #######################################################################################################################################
#     def __init__(self, game_context: TCGGame) -> None:
#         """
#         初始化唯一道具通知系统。

#         Args:
#             game_context: TCG游戏上下文对象
#         """
#         super().__init__(game_context)
#         self._game: Final[TCGGame] = game_context

#         ####################################################################################################################################

#     @override
#     def get_trigger(self) -> dict[Matcher, GroupEvent]:
#         return {Matcher(DrawCardsAction): GroupEvent.ADDED}

#     ####################################################################################################################################
#     @override
#     def filter(self, entity: Entity) -> bool:
#         return entity.has(DrawCardsAction)

#     #######################################################################################################################################
#     @override
#     @override
#     async def react(self, entities: list[Entity]) -> None:
#         """
#         执行唯一道具通知操作。

#         该方法在每个游戏循环中被调用,负责:
#         1. 检查战斗状态(非战斗中不执行)
#         2. 获取所有具有库存组件的实体
#         3. 为每个实体检查并通知唯一道具

#         Returns:
#             None

#         Note:
#             - 仅在战斗进行中执行
#             - 使用 InventoryComponent 作为查询条件
#             - 自动管理提示消息的唯一性
#         """
#         # 检查是否在战斗中
#         if not self._game.current_combat_sequence.is_ongoing:
#             return

#         logger.debug("UniqueItemNotificationSystem: 开始检查唯一道具")

#         # 获取所有拥有库存的实体
#         # inventory_entities = self._game.get_group(
#         #     Matcher(InventoryComponent)
#         # ).entities.copy()

#         # 为每个实体处理唯一道具通知
#         self._process_unique_items(entities)

#     #######################################################################################################################################
#     def _process_unique_items(self, entities: List[Entity]) -> None:
#         """
#         处理实体的唯一道具,添加提示消息并确保唯一性。

#         Args:
#             entities: 需要检查的实体列表
#         """
#         for entity in entities:
#             if not entity.has(InventoryComponent):
#                 continue

#             inventory_comp = entity.get(InventoryComponent)
#             assert inventory_comp is not None, "Entity must have InventoryComponent"

#             if len(inventory_comp.items) == 0:
#                 continue

#             for item in inventory_comp.items:
#                 if isinstance(item, UniqueItem):
#                     self._notify_unique_item(entity, item)
#                 else:
#                     logger.debug(
#                         f"entity {entity.name} has item {item.model_dump_json()}, 暂时不处理!"
#                     )

#     #######################################################################################################################################
#     def _notify_unique_item(self, entity: Entity, item: Item) -> None:
#         """
#         为实体添加唯一道具的提示消息,并确保不重复。

#         Args:
#             entity: 拥有道具的实体
#             item: 唯一道具对象
#         """
#         logger.debug(f"entity {entity.name} has unique item {item.model_dump_json()}")

#         # 查找并删除已存在的相同道具提示消息
#         existing_human_messages = self._game.filter_human_messages_by_attribute(
#             actor_entity=entity,
#             attribute_key="test_unique_item",
#             attribute_value=item.name,
#         )

#         if len(existing_human_messages) > 0:
#             self._game.remove_human_messages(
#                 actor_entity=entity,
#                 human_messages=existing_human_messages,
#             )

#         # 验证删除成功
#         duplicate_message_test = self._game.filter_human_messages_by_attribute(
#             actor_entity=entity,
#             attribute_key="test_unique_item",
#             attribute_value=item.name,
#         )
#         assert len(duplicate_message_test) == 0, f"test_unique_item not deleted!"

#         # 添加新的提示消息
#         self._game.add_human_message(
#             entity,
#             _format_unique_item_notification(item),
#             test_unique_item=item.name,
#         )
