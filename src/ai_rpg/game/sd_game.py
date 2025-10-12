# import copy
# import shutil
# import uuid
# from pathlib import Path
# from typing import Any, Final, List, Optional, Set
# from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
# from loguru import logger
# from overrides import override
# from .config import LOGS_DIR
# from ..entitas import Entity
# from ..game.base_game import BaseGame
# from .rpg_game_context import RPGGameContext
# from ..game.sd_game_process_pipeline import SDGameProcessPipeline
# from ..models import (
#     Actor,
#     ActorComponent,
#     ActorType,
#     AgentEvent,
#     AgentChatHistory,
#     AppearanceComponent,
#     DungeonComponent,
#     EnvironmentComponent,
#     HeroComponent,
#     HomeComponent,
#     KickOffMessageComponent,
#     MonsterComponent,
#     PlayerComponent,
#     RPGCharacterProfile,
#     RPGCharacterProfileComponent,
#     RuntimeComponent,
#     Stage,
#     StageComponent,
#     StageType,
#     World,
#     WorldSystem,
#     WorldComponent,
#     InventoryComponent,
# )
# from .player_client import PlayerClient


# # ################################################################################################################################################
# def _replace_name_with_you(input_text: str, your_name: str) -> str:

#     if len(input_text) == 0 or your_name not in input_text:
#         return input_text

#     at_name = f"@{your_name}"
#     if at_name in input_text:
#         # 如果有@名字，就略过
#         return input_text

#     return input_text.replace(your_name, "你")


# ###############################################################################################################################################
# def _debug_verbose(verbose_dir: Path, world: World) -> None:
#     """调试方法，保存游戏状态到文件"""
#     _verbose_boot_data(verbose_dir, world)
#     _verbose_world_data(verbose_dir, world)
#     _verbose_entities_serialization(verbose_dir, world)
#     _verbose_chat_history(verbose_dir, world)
#     logger.debug(f"Verbose debug info saved to: {verbose_dir}")


# ###############################################################################################################################################
# def _verbose_chat_history(verbose_dir: Path, world: World) -> None:
#     """保存聊天历史到文件"""
#     chat_history_dir = verbose_dir / "chat_history"
#     chat_history_dir.mkdir(parents=True, exist_ok=True)

#     for agent_name, agent_memory in world.agents_chat_history.items():
#         chat_history_path = chat_history_dir / f"{agent_name}.json"
#         chat_history_path.write_text(agent_memory.model_dump_json(), encoding="utf-8")


# ###############################################################################################################################################
# def _verbose_boot_data(verbose_dir: Path, world: World) -> None:
#     """保存启动数据到文件"""
#     boot_data_dir = verbose_dir / "boot_data"
#     boot_data_dir.mkdir(parents=True, exist_ok=True)

#     boot_file_path = boot_data_dir / f"{world.boot.name}.json"
#     if boot_file_path.exists():
#         return  # 如果文件已存在，则不覆盖

#     # 保存 Boot 数据到文件
#     boot_file_path.write_text(world.boot.model_dump_json(), encoding="utf-8")


# ###############################################################################################################################################
# def _verbose_world_data(verbose_dir: Path, world: World) -> None:
#     """保存世界数据到文件"""
#     world_data_dir = verbose_dir / "world_data"
#     world_data_dir.mkdir(parents=True, exist_ok=True)
#     world_file_path = world_data_dir / f"{world.boot.name}.json"
#     world_file_path.write_text(
#         world.model_dump_json(), encoding="utf-8"
#     )  # 保存 World 数据到文件，覆盖


# ###############################################################################################################################################
# def _verbose_entities_serialization(verbose_dir: Path, world: World) -> None:
#     """保存实体快照到文件"""
#     entities_serialization_dir = verbose_dir / "entities_serialization"
#     # 强制删除一次
#     if entities_serialization_dir.exists():
#         shutil.rmtree(entities_serialization_dir)
#     # 创建目录
#     entities_serialization_dir.mkdir(parents=True, exist_ok=True)
#     assert entities_serialization_dir.exists()

#     for entity_serialization in world.entities_serialization:
#         entity_serialization_path = (
#             entities_serialization_dir / f"{entity_serialization.name}.json"
#         )
#         entity_serialization_path.write_text(
#             entity_serialization.model_dump_json(), encoding="utf-8"
#         )


# ###############################################################################################################################################
# class SDGame(BaseGame, RPGGameContext):

#     # Social Deduction Game

#     def __init__(
#         self,
#         name: str,
#         player_client: PlayerClient,
#         world: World,
#     ) -> None:

#         # 必须按着此顺序实现父
#         BaseGame.__init__(self, name)  # 需要传递 name
#         RPGGameContext.__init__(self)  # 继承 Context, 需要调用其 __init__

#         # 世界运行时
#         self._world: Final[World] = world

#         # 常规home 的流程
#         self._main_pipeline: Final[SDGameProcessPipeline] = (
#             SDGameProcessPipeline.create_main_pipline(self)
#         )

#         # 仅处理player的home流程
#         # self._player_home_pipeline: Final[TCGGameProcessPipeline] = (
#         #     TCGGameProcessPipeline.create_player_home_pipline(self)
#         # )

#         # # 地下城战斗流程
#         # self._dungeon_combat_pipeline: Final[TCGGameProcessPipeline] = (
#         #     TCGGameProcessPipeline.create_dungeon_combat_state_pipeline(self)
#         # )

#         self._all_pipelines: List[SDGameProcessPipeline] = [
#             self._main_pipeline,
#             # self._player_home_pipeline,
#             # self._dungeon_combat_pipeline,
#         ]

#         # 玩家
#         self._player_client: Final[PlayerClient] = player_client
#         logger.debug(
#             f"TCGGame init player: {self._player_client.name}: {self._player_client.actor}"
#         )
#         assert self._player_client.name != "", "玩家名字不能为空"
#         assert self._player_client.actor != "", "玩家角色不能为空"

#     ###############################################################################################################################################
#     @property
#     def player_client(self) -> PlayerClient:
#         return self._player_client

#     ###############################################################################################################################################
#     @override
#     def destroy_entity(self, entity: Entity) -> None:
#         logger.debug(f"TCGGame destroy entity: {entity.name}")
#         if entity.name in self.world.agents_chat_history:
#             logger.debug(f"TCGGame destroy entity: {entity.name} in short term memory")
#             self.world.agents_chat_history.pop(entity.name, None)
#         return super().destroy_entity(entity)

#     ###############################################################################################################################################
#     @property
#     def verbose_dir(self) -> Path:

#         dir = LOGS_DIR / f"{self.player_client.name}" / f"{self.name}"
#         if not dir.exists():
#             dir.mkdir(parents=True, exist_ok=True)
#         assert dir.exists()
#         assert dir.is_dir()
#         return dir

#     ###############################################################################################################################################
#     @property
#     def world(self) -> World:
#         return self._world

#     ###############################################################################################################################################
#     @property
#     def main_pipeline(self) -> SDGameProcessPipeline:
#         return self._main_pipeline

#     ###############################################################################################################################################
#     @override
#     def exit(self) -> None:
#         # 关闭所有管道
#         for processor in self._all_pipelines:
#             processor.shutdown()
#             logger.debug(f"Shutdown pipeline: {processor._name}")

#         # 清空
#         self._all_pipelines.clear()
#         logger.warning(f"{self.name}, exit!!!!!!!!!!!!!!!!!!!!")

#     ###############################################################################################################################################
#     @override
#     async def initialize(self) -> None:
#         # 初始化所有管道
#         for processor in self._all_pipelines:
#             processor.activate_reactive_processors()
#             await processor.initialize()
#             logger.debug(f"Initialized pipeline: {processor._name}")

#     ###############################################################################################################################################
#     def new_game(self) -> "SDGame":

#         assert (
#             len(self.world.entities_serialization) == 0
#         ), "游戏中有实体，不能创建新的游戏"

#         ## 第1步，创建world_system
#         self._create_world_entities(self.world.boot.world_systems)

#         ## 第2步，创建actor
#         self._create_actor_entities(self.world.boot.actors)

#         ## 第3步，分配玩家控制的actor
#         self._assign_player_to_actor()

#         ## 第4步，创建stage
#         self._create_stage_entities(self.world.boot.stages)

#         return self

#     ###############################################################################################################################################
#     # 测试！回复ecs
#     def load_game(self) -> "SDGame":
#         assert (
#             len(self.world.entities_serialization) > 0
#         ), "游戏中没有实体，不能恢复游戏"
#         assert len(self._entities) == 0, "游戏中有实体，不能恢复游戏"
#         self.deserialize_entities(self.world.entities_serialization)

#         player_entity = self.get_player_entity()
#         assert player_entity is not None
#         assert player_entity.get(PlayerComponent).player_name == self.player_client.name

#         return self

#     ###############################################################################################################################################
#     def save(self) -> "SDGame":

#         # 生成快照
#         self.world.entities_serialization = self.serialize_entities(self._entities)
#         logger.debug(
#             f"游戏将要保存，实体数量: {len(self.world.entities_serialization)}"
#         )

#         # debug - 调用模块级函数
#         _debug_verbose(
#             verbose_dir=self.verbose_dir,
#             world=self.world,
#         )

#         return self

#     ###############################################################################################################################################
#     def _create_world_entities(
#         self,
#         world_system_models: List[WorldSystem],
#     ) -> List[Entity]:

#         ret: List[Entity] = []

#         for world_system_model in world_system_models:

#             # 创建实体
#             world_system_entity = self.__create_entity__(world_system_model.name)
#             assert world_system_entity is not None

#             # 必要组件
#             world_system_entity.add(
#                 RuntimeComponent,
#                 world_system_model.name,
#                 self.world.next_runtime_index(),
#                 str(uuid.uuid4()),
#             )
#             world_system_entity.add(WorldComponent, world_system_model.name)

#             # system prompt
#             assert world_system_model.name in world_system_model.system_message
#             self.append_system_message(
#                 world_system_entity, world_system_model.system_message
#             )

#             # kickoff prompt
#             world_system_entity.add(
#                 KickOffMessageComponent,
#                 world_system_model.name,
#                 world_system_model.kick_off_message,
#             )

#             # 添加到返回值
#             ret.append(world_system_entity)

#         return ret

#     ###############################################################################################################################################
#     def _create_actor_entities(self, actor_models: List[Actor]) -> List[Entity]:

#         ret: List[Entity] = []
#         for actor_model in actor_models:

#             # 创建实体
#             actor_entity = self.__create_entity__(actor_model.name)
#             assert actor_entity is not None

#             # 必要组件：guid
#             actor_entity.add(
#                 RuntimeComponent,
#                 actor_model.name,
#                 self.world.next_runtime_index(),
#                 str(uuid.uuid4()),
#             )

#             # 必要组件：身份类型标记-角色Actor
#             actor_entity.add(ActorComponent, actor_model.name, "")

#             # 必要组件：系统消息
#             assert actor_model.name in actor_model.system_message
#             self.append_system_message(actor_entity, actor_model.system_message)

#             # 必要组件：启动消息
#             actor_entity.add(
#                 KickOffMessageComponent, actor_model.name, actor_model.kick_off_message
#             )

#             # 必要组件：外观
#             actor_entity.add(
#                 AppearanceComponent,
#                 actor_model.name,
#                 actor_model.character_sheet.appearance,
#             )

#             # 必要组件：基础属性，这里用浅拷贝，不能动原有的。
#             actor_entity.add(
#                 RPGCharacterProfileComponent,
#                 actor_model.name,
#                 copy.copy(actor_model.rpg_character_profile),
#                 [],
#             )

#             # 测试类型。
#             character_profile_component = actor_entity.get(RPGCharacterProfileComponent)
#             assert isinstance(
#                 character_profile_component.rpg_character_profile, RPGCharacterProfile
#             )

#             # 必要组件：类型标记
#             match actor_model.character_sheet.type:
#                 case ActorType.HERO:
#                     actor_entity.add(HeroComponent, actor_model.name)
#                 case ActorType.MONSTER:
#                     actor_entity.add(MonsterComponent, actor_model.name)

#             # 必要组件：背包组件, 必须copy一份, 不要进行直接引用，而且在此处生成uuid
#             copy_items = copy.deepcopy(actor_model.inventory.items)
#             for item in copy_items:
#                 assert item.uuid == "", "item.uuid should be empty"
#                 item.uuid = str(uuid.uuid4())

#             # 添加InventoryComponent！
#             actor_entity.add(
#                 InventoryComponent,
#                 actor_model.name,
#                 copy_items,
#             )

#             # 测试一下
#             inventory_component = actor_entity.get(InventoryComponent)
#             assert inventory_component is not None, "inventory_component is None"
#             if len(inventory_component.items) > 0:
#                 logger.info(
#                     f"InventoryComponent 角色 {actor_model.name} 有 {len(inventory_component.items)} 个物品"
#                 )
#                 for item in inventory_component.items:
#                     logger.info(f"物品: {item.model_dump_json(indent=2)}")

#             # 添加到返回值
#             ret.append(actor_entity)

#         return ret

#     ###############################################################################################################################################
#     def _create_stage_entities(self, stage_models: List[Stage]) -> List[Entity]:

#         ret: List[Entity] = []

#         for stage_model in stage_models:

#             # 创建实体
#             stage_entity = self.__create_entity__(stage_model.name)

#             # 必要组件
#             stage_entity.add(
#                 RuntimeComponent,
#                 stage_model.name,
#                 self.world.next_runtime_index(),
#                 str(uuid.uuid4()),
#             )
#             stage_entity.add(StageComponent, stage_model.name)

#             # system prompt
#             assert stage_model.name in stage_model.system_message
#             self.append_system_message(stage_entity, stage_model.system_message)

#             # kickoff prompt
#             stage_entity.add(
#                 KickOffMessageComponent, stage_model.name, stage_model.kick_off_message
#             )

#             # 必要组件：环境描述
#             stage_entity.add(
#                 EnvironmentComponent,
#                 stage_model.name,
#                 "",
#             )

#             # 必要组件：类型
#             if stage_model.character_sheet.type == StageType.DUNGEON:
#                 stage_entity.add(DungeonComponent, stage_model.name)
#             elif stage_model.character_sheet.type == StageType.HOME:
#                 stage_entity.add(HomeComponent, stage_model.name)

#             ## 重新设置Actor和stage的关系
#             for actor_model in stage_model.actors:
#                 actor_entity: Optional[Entity] = self.get_actor_entity(actor_model.name)
#                 assert actor_entity is not None
#                 actor_entity.replace(ActorComponent, actor_model.name, stage_model.name)

#             ret.append(stage_entity)

#         return []

#     ###############################################################################################################################################
#     def get_player_entity(self) -> Optional[Entity]:
#         return self.get_entity_by_player_name(self.player_client.name)

#     ###############################################################################################################################################
#     def get_agent_chat_history(self, entity: Entity) -> AgentChatHistory:
#         return self.world.agents_chat_history.setdefault(
#             entity.name, AgentChatHistory(name=entity.name, chat_history=[])
#         )

#     ###############################################################################################################################################
#     def append_system_message(self, entity: Entity, chat: str) -> None:
#         logger.debug(f"append_system_message: {entity.name} => \n{chat}")
#         agent_chat_history = self.get_agent_chat_history(entity)
#         assert (
#             len(agent_chat_history.chat_history) == 0
#         ), "system message should be the first message"
#         agent_chat_history.chat_history.append(SystemMessage(content=chat))

#     ###############################################################################################################################################
#     def append_human_message(self, entity: Entity, chat: str, **kwargs: Any) -> None:

#         logger.debug(f"append_human_message: {entity.name} => \n{chat}")
#         if len(kwargs) > 0:
#             # 如果 **kwargs 不是 空，就打印一下，这种消息比较特殊。
#             logger.debug(f"kwargs: {kwargs}")

#         agent_short_term_memory = self.get_agent_chat_history(entity)
#         agent_short_term_memory.chat_history.extend(
#             [HumanMessage(content=chat, **kwargs)]
#         )

#     ###############################################################################################################################################
#     def append_ai_message(self, entity: Entity, ai_messages: List[AIMessage]) -> None:

#         assert len(ai_messages) > 0, "ai_messages should not be empty"
#         for ai_message in ai_messages:
#             assert isinstance(ai_message, AIMessage)
#             assert ai_message.content != "", "ai_message content should not be empty"
#             logger.debug(f"append_ai_message: {entity.name} => \n{ai_message.content}")

#         # 添加多条 AIMessage
#         agent_short_term_memory = self.get_agent_chat_history(entity)
#         agent_short_term_memory.chat_history.extend(ai_messages)

#     ###############################################################################################################################################
#     def _assign_player_to_actor(self) -> bool:
#         assert self.player_client.name != "", "玩家名字不能为空"
#         assert self.player_client.actor != "", "玩家角色不能为空"

#         actor_entity = self.get_actor_entity(self.player_client.actor)
#         assert actor_entity is not None
#         if actor_entity is None:
#             return False

#         assert not actor_entity.has(PlayerComponent)
#         actor_entity.replace(PlayerComponent, self.player_client.name)
#         logger.info(
#             f"玩家: {self.player_client.name} 选择控制: {self.player_client.name}"
#         )
#         return True

#     ###############################################################################################################################################
#     def broadcast_event(
#         self,
#         entity: Entity,
#         agent_event: AgentEvent,
#         exclude_entities: Set[Entity] = set(),
#     ) -> None:

#         stage_entity = self.safe_get_stage_entity(entity)
#         assert stage_entity is not None, "stage is None, actor无所在场景是有问题的"
#         if stage_entity is None:
#             return

#         need_broadcast_entities = self.get_alive_actors_on_stage(stage_entity)
#         need_broadcast_entities.add(stage_entity)

#         if len(exclude_entities) > 0:
#             need_broadcast_entities = need_broadcast_entities - exclude_entities

#         self.notify_event(need_broadcast_entities, agent_event)

#     ###############################################################################################################################################
#     def notify_event(
#         self,
#         entities: Set[Entity],
#         agent_event: AgentEvent,
#     ) -> None:

#         # 正常的添加记忆。
#         for entity in entities:
#             replace_message = _replace_name_with_you(agent_event.message, entity.name)
#             self.append_human_message(entity, replace_message)

#         # 最后都要发给客户端。
#         self.player_client.add_agent_event_message(agent_event=agent_event)

#     #######################################################################################################################################
#     def find_human_messages_by_attribute(
#         self,
#         actor_entity: Entity,
#         attribute_key: str,
#         attribute_value: str,
#         reverse_order: bool = True,
#     ) -> List[HumanMessage]:

#         found_messages: List[HumanMessage] = []

#         chat_history = self.get_agent_chat_history(actor_entity).chat_history

#         # 进行查找。
#         for chat_message in reversed(chat_history) if reverse_order else chat_history:

#             if not isinstance(chat_message, HumanMessage):
#                 continue

#             try:
#                 # 直接从 HumanMessage 对象获取属性，而不是从嵌套的 kwargs 中获取
#                 if hasattr(chat_message, attribute_key):
#                     if getattr(chat_message, attribute_key) == attribute_value:
#                         found_messages.append(chat_message)

#             except Exception as e:
#                 logger.error(f"find_recent_human_message_by_attribute error: {e}")
#                 continue

#         return found_messages

#     #######################################################################################################################################
#     def delete_human_messages_by_attribute(
#         self,
#         actor_entity: Entity,
#         human_messages: List[HumanMessage],
#     ) -> int:

#         if len(human_messages) == 0:
#             return 0

#         chat_history = self.get_agent_chat_history(actor_entity).chat_history
#         original_length = len(chat_history)

#         # 删除指定的 HumanMessage 对象
#         chat_history[:] = [msg for msg in chat_history if msg not in human_messages]

#         deleted_count = original_length - len(chat_history)
#         if deleted_count > 0:
#             logger.debug(
#                 f"Deleted {deleted_count} HumanMessage(s) from {actor_entity.name}'s chat history."
#             )
#         return deleted_count

#     #######################################################################################################################################
#     def compress_combat_chat_history(
#         self, entity: Entity, begin_message: HumanMessage, end_message: HumanMessage
#     ) -> None:
#         assert (
#             begin_message != end_message
#         ), "begin_message and end_message should not be the same"

#         agent_chat_history = self.get_agent_chat_history(entity)
#         begin_message_index = agent_chat_history.chat_history.index(begin_message)
#         end_message_index = agent_chat_history.chat_history.index(end_message) + 1
#         # 开始移除！！！！。
#         del agent_chat_history.chat_history[begin_message_index:end_message_index]
#         logger.debug(f"compress_combat_chat_history！= {entity.name}")
#         logger.debug(f"begin_message: \n{begin_message.model_dump_json(indent=2)}")
#         logger.debug(f"end_message: \n{end_message.model_dump_json(indent=2)}")

#     #######################################################################################################################################
