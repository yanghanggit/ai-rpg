"""
RPG游戏核心类模块

本模块定义了RPG游戏的核心类，提供游戏世界的管理、实体创建、消息处理等核心功能。
"""

import copy
import uuid
from typing import Any, Final, List, Optional, Set
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from loguru import logger
from overrides import override
from .game_data_service import persist_world_data, debug_verbose_world_data, verbose_dir
from ..entitas import Entity
from .game_session import GameSession
from .rpg_entity_manager import RPGEntityManager
from .rpg_game_pipeline_manager import RPGGamePipelineManager
from ..models import (
    Actor,
    ActorComponent,
    ActorType,
    AgentEvent,
    AgentContext,
    AppearanceComponent,
    DungeonComponent,
    EnvironmentComponent,
    AllyComponent,
    HomeComponent,
    KickOffComponent,
    EnemyComponent,
    PlayerComponent,
    CombatStatsComponent,
    RuntimeComponent,
    Stage,
    StageComponent,
    StageType,
    World,
    WorldSystem,
    WorldComponent,
    InventoryComponent,
    SkillBookComponent,
    TransStageEvent,
    PlayerOnlyStageComponent,
)
from .player_session import PlayerSession


#################################################################################################################################################
def _format_stage_departure_message(actor_name: str, stage_name: str) -> str:
    """生成角色离开场景的通知消息"""
    return f"# 通知！{actor_name} 离开了场景: {stage_name}"


#################################################################################################################################################
def _format_stage_arrival_message(actor_name: str, stage_name: str) -> str:
    """生成角色进入场景的通知消息"""
    return f"# 通知！{actor_name} 进入了 场景: {stage_name}"


#################################################################################################################################################
def _format_stage_transition_message(from_stage_name: str, to_stage_name: str) -> str:
    """生成角色自身场景转换的通知消息"""
    return (
        f"# 通知！你从 场景: {from_stage_name} 离开，然后进入了 场景: {to_stage_name}"
    )


#################################################################################################################################################
class RPGGame(GameSession, RPGEntityManager, RPGGamePipelineManager):
    """
    RPG游戏核心类

    整合游戏会话、实体管理和管道管理功能，提供完整的RPG游戏框架。
    负责游戏世界的创建、实体管理、消息处理和场景转换等核心功能。
    """

    def __init__(
        self,
        name: str,
        player_session: PlayerSession,
        world: World,
    ) -> None:

        # 必须按着此顺序实现父类
        GameSession.__init__(self, name)  # 需要传递 name
        RPGEntityManager.__init__(self)  # 继承 Context, 需要调用其 __init__
        RPGGamePipelineManager.__init__(self)  # 管道管理器初始化

        # 初始化player_session 和 world
        self._player_session: Final[PlayerSession] = player_session
        self._world: Final[World] = world

        # 验证玩家信息
        logger.info(
            f"TCGGame init player: {self.player_session.name}: {self.player_session.actor}"
        )
        assert self.player_session.name != "", "玩家名字不能为空"
        assert self.player_session.actor != "", "玩家角色不能为空"

    ###############################################################################################################################################
    @property
    def player_session(self) -> PlayerSession:
        return self._player_session

    ###############################################################################################################################################
    @property
    def world(self) -> World:
        return self._world

    ###############################################################################################################################################
    def get_player_entity(self) -> Optional[Entity]:
        return self.get_entity_by_player_name(self.player_session.name)

    ###############################################################################################################################################
    def get_agent_context(self, entity: Entity) -> AgentContext:
        return self.world.agents_context.setdefault(
            entity.name, AgentContext(name=entity.name, context=[])
        )

    ###############################################################################################################################################
    @override
    def destroy_entity(self, entity: Entity) -> None:
        logger.debug(f"TCGGame destroy entity: {entity.name}")
        if entity.name in self.world.agents_context:
            logger.debug(f"TCGGame destroy entity: {entity.name} in short term memory")
            self.world.agents_context.pop(entity.name, None)
        return super().destroy_entity(entity)

    ###############################################################################################################################################
    @override
    def exit(self) -> None:
        # 关闭所有管道
        self.shutdown_all_pipelines()
        # logger.warning(f"{self.name}, exit!!!!!!!!!!!!!!!!!!!!)")

    ###############################################################################################################################################
    @override
    async def initialize(self) -> None:
        # 初始化所有管道
        await self.initialize_all_pipelines()
        # logger.debug(f"Initialized all pipelines")

    ###############################################################################################################################################
    def new_game(self) -> "RPGGame":

        assert (
            len(self.world.entities_serialization) == 0
        ), "游戏中有实体，不能创建新的游戏"

        ## 第1步，创建world_system
        self._create_world_entities(self.world.blueprint.world_systems)

        ## 第2步，创建actor
        self._create_actor_entities(self.world.blueprint.actors)

        ## 第3步，分配玩家控制的actor
        assert self.player_session.name != "", "玩家名字不能为空"
        assert self.player_session.actor != "", "玩家角色不能为空"
        actor_entity = self.get_actor_entity(self.player_session.actor)
        assert actor_entity is not None
        assert not actor_entity.has(PlayerComponent)
        actor_entity.replace(PlayerComponent, self.player_session.name)
        logger.info(
            f"玩家: {self.player_session.name} 选择控制: {self.player_session.actor}"
        )

        ## 第4步，创建stage
        self._create_stage_entities(self.world.blueprint.stages)

        ## 第5步，标记仅玩家可见的场景
        assert (
            self.world.blueprint.player_only_stage != ""
        ), "player_only_stage 不能为空"
        player_only_stage_entity = self.get_stage_entity(
            self.world.blueprint.player_only_stage
        )
        assert player_only_stage_entity is not None, "player_only_stage_entity is None"
        assert not player_only_stage_entity.has(PlayerOnlyStageComponent)
        player_only_stage_entity.replace(
            PlayerOnlyStageComponent, player_only_stage_entity.name
        )
        logger.info(f"场景: {player_only_stage_entity.name} 已标记为仅玩家可见")

        return self

    ###############################################################################################################################################
    # 测试！回复ecs
    def load_game(self) -> "RPGGame":
        assert (
            len(self.world.entities_serialization) > 0
        ), "游戏中没有实体，不能恢复游戏"
        assert len(self._entities) == 0, "游戏中有实体，不能恢复游戏"
        self.deserialize_entities(self.world.entities_serialization)
        return self

    ###############################################################################################################################################
    def save(self) -> "RPGGame":

        # 生成快照
        self.world.entities_serialization = self.serialize_entities(self._entities)
        # logger.debug(
        #     f"游戏将要保存，实体数量: {len(self.world.entities_serialization)}"
        # )

        # 保存快照
        persist_world_data(
            username=self.player_session.name,
            world=self.world,
            player_session=self.player_session,
        )

        # debug - 调用模块级函数
        debug_verbose_world_data(
            verbose_dir=verbose_dir(
                player_session_name=self.player_session.name, game_name=self.name
            ),
            world=self.world,
            player_session=self.player_session,
        )

        return self

    ###############################################################################################################################################
    def _create_world_entities(
        self,
        world_system_models: List[WorldSystem],
    ) -> List[Entity]:
        """创建世界系统实体，包括运行时组件、系统消息和启动消息"""
        world_entities: List[Entity] = []

        for world_system_model in world_system_models:

            # 创建实体
            world_system_entity = self.__create_entity__(world_system_model.name)
            assert (
                world_system_entity is not None
            ), f"创建world_system_entity失败: {world_system_model.name}"

            # 必要组件：identifier
            self._world.runtime_index += 1
            world_system_entity.add(
                RuntimeComponent,
                world_system_model.name,
                self._world.runtime_index,
                str(uuid.uuid4()),
            )

            # 必要组件：身份类型标记-世界系统
            world_system_entity.add(WorldComponent, world_system_model.name)

            # 添加系统消息
            assert (
                world_system_model.name in world_system_model.system_message
            ), f"world_system_model.system_message 缺少 {world_system_model.name} 的系统消息"
            self.add_system_message(
                world_system_entity, world_system_model.system_message
            )

            # kickoff prompt
            world_system_entity.add(
                KickOffComponent,
                world_system_model.name,
                world_system_model.kick_off_message,
            )

            # 添加到返回值
            world_entities.append(world_system_entity)

        return world_entities

    ###############################################################################################################################################
    def _create_actor_entities(self, actor_models: List[Actor]) -> List[Entity]:
        """创建角色实体，包括属性、外观、背包、技能等组件

        注意：角色私有知识库在环境初始化时已加载（setup_dev_environment.py），此处不再重复加载
        """
        actor_entities: List[Entity] = []

        for actor_model in actor_models:

            # 创建实体
            actor_entity = self.__create_entity__(actor_model.name)
            assert actor_entity is not None, f"创建actor_entity失败: {actor_model.name}"

            # 必要组件：identifier
            self._world.runtime_index += 1
            actor_entity.add(
                RuntimeComponent,
                actor_model.name,
                self._world.runtime_index,
                str(uuid.uuid4()),
            )

            # 必要组件：身份类型标记-角色Actor
            actor_entity.add(
                ActorComponent, actor_model.name, actor_model.character_sheet.name, ""
            )

            # 必要组件：系统消息
            assert (
                actor_model.name in actor_model.system_message
            ), f"actor_model.system_message 缺少 {actor_model.name} 的系统消息"
            self.add_system_message(actor_entity, actor_model.system_message)

            # 必要组件：启动消息
            actor_entity.add(
                KickOffComponent, actor_model.name, actor_model.kick_off_message
            )

            # 必要组件：外观
            actor_entity.add(
                AppearanceComponent,
                actor_model.name,
                actor_model.character_sheet.appearance,
            )

            # 必要组件：基础属性，这里用浅拷贝，不能动原有的。
            actor_entity.add(
                CombatStatsComponent,
                actor_model.name,
                copy.copy(actor_model.character_stats),
                [],
            )

            # 必要组件：类型标记
            match actor_model.character_sheet.type:
                case ActorType.ALLY:
                    actor_entity.add(AllyComponent, actor_model.name)
                case ActorType.ENEMY:
                    actor_entity.add(EnemyComponent, actor_model.name)
                case ActorType.NEUTRAL:
                    # 中立角色，不添加特殊组件
                    logger.warning(
                        f"创建中立角色 Actor: {actor_model.name}, 不添加特殊组件"
                    )
                case _:
                    assert (
                        False
                    ), f"未知的 ActorType: {actor_model.character_sheet.type}"

            # 必要组件：背包组件, 必须copy一份, 不要进行直接引用，而且在此处生成uuid
            copy_items = copy.deepcopy(actor_model.items)
            for item in copy_items:
                assert item.uuid == "", "item.uuid should be empty"
                item.uuid = str(uuid.uuid4())

            actor_entity.add(
                InventoryComponent,
                actor_model.name,
                copy_items,
            )

            # 测试一下 道具！
            inventory_component = actor_entity.get(InventoryComponent)
            assert inventory_component is not None, "inventory_component is None"
            if len(inventory_component.items) > 0:
                logger.debug(
                    f"InventoryComponent 角色 {actor_model.name} 有 {len(inventory_component.items)} 个物品"
                )
                for item in inventory_component.items:
                    logger.info(f"物品: {item.model_dump_json(indent=2)}")

            # 必要组件：技能书组件, 必须copy一份, 不要进行直接引用
            copy_skills = copy.deepcopy(actor_model.skills)
            actor_entity.add(
                SkillBookComponent,
                actor_model.name,
                copy_skills,
            )

            # 添加到返回值
            actor_entities.append(actor_entity)

        return actor_entities

    ###############################################################################################################################################
    def _create_stage_entities(self, stage_models: List[Stage]) -> List[Entity]:
        """创建场景实体，包括环境描述、类型标记，并建立与角色的关系"""
        stage_entities: List[Entity] = []

        for stage_model in stage_models:

            # 创建实体
            stage_entity = self.__create_entity__(stage_model.name)

            # 必要组件: identifier
            self._world.runtime_index += 1
            stage_entity.add(
                RuntimeComponent,
                stage_model.name,
                self._world.runtime_index,
                str(uuid.uuid4()),
            )
            stage_entity.add(
                StageComponent, stage_model.name, stage_model.character_sheet.name
            )

            # 必要组件：系统消息
            assert stage_model.name in stage_model.system_message
            self.add_system_message(stage_entity, stage_model.system_message)

            # 必要组件：启动消息
            stage_entity.add(
                KickOffComponent, stage_model.name, stage_model.kick_off_message
            )

            # 必要组件：环境描述
            stage_entity.add(
                EnvironmentComponent,
                stage_model.name,
                "",
            )

            # 必要组件：类型
            if stage_model.character_sheet.type == StageType.DUNGEON:
                stage_entity.add(DungeonComponent, stage_model.name)
            elif stage_model.character_sheet.type == StageType.HOME:
                stage_entity.add(HomeComponent, stage_model.name)

            ## 重新设置Actor和stage的关系
            for actor_model in stage_model.actors:
                actor_entity = self.get_actor_entity(actor_model.name)
                assert (
                    actor_entity is not None
                ), f"找不到actor_entity: {actor_model.name}"
                actor_entity.replace(
                    ActorComponent,
                    actor_model.name,
                    actor_model.character_sheet.name,
                    stage_model.name,
                )

            stage_entities.append(stage_entity)

        return stage_entities

    ###############################################################################################################################################
    def add_system_message(self, entity: Entity, message_content: str) -> None:
        """添加系统消息到实体的LLM上下文，必须是第一条消息"""
        logger.info(f"add_system_message: {entity.name} => \n{message_content}")
        agent_context = self.get_agent_context(entity)
        assert (
            len(agent_context.context) == 0
        ), "system message should be the first message"
        agent_context.context.append(SystemMessage(content=message_content))

    ###############################################################################################################################################
    def add_human_message(
        self, entity: Entity, message_content: str, **kwargs: Any
    ) -> None:
        """添加用户消息到实体的LLM上下文"""
        # logger.debug(f"add_human_message: {entity.name} => \n{message_content}")
        # if len(kwargs) > 0:
        #     # 如果 **kwargs 不是 空，就打印一下，这种消息比较特殊。
        #     logger.debug(f"kwargs: {kwargs}")

        agent_context = self.get_agent_context(entity)
        agent_context.context.extend([HumanMessage(content=message_content, **kwargs)])

    ###############################################################################################################################################
    def add_ai_message(self, entity: Entity, ai_messages: List[AIMessage]) -> None:
        """添加AI响应消息到实体的LLM上下文"""
        assert len(ai_messages) > 0, "ai_messages should not be empty"
        # for ai_message in ai_messages:
        #     assert isinstance(ai_message, AIMessage)
        #     assert ai_message.content != "", "ai_message content should not be empty"
        #     logger.debug(f"add_ai_message: {entity.name} => \n{ai_message.content}")

        # 添加多条 AIMessage
        agent_context = self.get_agent_context(entity)
        agent_context.context.extend(ai_messages)

    ###############################################################################################################################################
    def broadcast_to_stage(
        self,
        entity: Entity,
        agent_event: AgentEvent,
        exclude_entities: Set[Entity] = set(),
        **kwargs: Any,
    ) -> None:

        stage_entity = self.resolve_stage_entity(entity)
        assert stage_entity is not None, "stage is None, actor无所在场景是有问题的"
        if stage_entity is None:
            return

        need_broadcast_entities = self.get_alive_actors_on_stage(stage_entity)
        need_broadcast_entities.add(stage_entity)

        if len(exclude_entities) > 0:
            need_broadcast_entities = need_broadcast_entities - exclude_entities

        self.notify_entities(need_broadcast_entities, agent_event, **kwargs)

    ###############################################################################################################################################
    def notify_entities(
        self,
        entities: Set[Entity],
        agent_event: AgentEvent,
        **kwargs: Any,
    ) -> None:

        # 正常的添加记忆。
        for entity in entities:
            self.add_human_message(entity, agent_event.message, **kwargs)

        # 最后都要发给客户端。
        self.player_session.add_agent_event_message(agent_event=agent_event)

    ###############################################################################################################################################
    def _validate_stage_transition_prerequisites(
        self, actors: Set[Entity], stage_destination: Entity
    ) -> Set[Entity]:
        """
        验证场景传送的前置条件并过滤有效的角色

        Args:
            actors: 需要传送的角色集合
            stage_destination: 目标场景

        Returns:
            Set[Entity]: 需要实际传送的角色集合（排除已在目标场景的角色）
        """
        # 验证所有角色都有ActorComponent
        for actor in actors:
            assert actor.has(ActorComponent), f"角色 {actor.name} 缺少 ActorComponent"

        # 过滤掉已经在目标场景的角色
        actors_to_transfer = set()
        for actor_entity in actors:
            current_stage = self.resolve_stage_entity(actor_entity)
            assert current_stage is not None, f"角色 {actor_entity.name} 没有当前场景"

            if current_stage == stage_destination:
                logger.warning(
                    f"{actor_entity.name} 已经存在于 {stage_destination.name}"
                )
                continue

            actors_to_transfer.add(actor_entity)

        return actors_to_transfer

    ###############################################################################################################################################
    def _broadcast_departure_notifications(self, actors: Set[Entity]) -> None:
        """
        处理角色离开场景的通知

        Args:
            actors: 要离开的角色集合
        """
        for actor_entity in actors:
            current_stage = self.resolve_stage_entity(actor_entity)
            assert current_stage is not None

            # 向所在场景及所在场景内除自身外的其他人宣布，这货要离开了
            self.broadcast_to_stage(
                entity=current_stage,
                agent_event=AgentEvent(
                    message=_format_stage_departure_message(
                        actor_entity.name, current_stage.name
                    ),
                ),
                exclude_entities={actor_entity},
            )

    ###############################################################################################################################################
    def _update_actors_stage_membership(
        self, actors: Set[Entity], stage_destination: Entity
    ) -> None:
        """
        执行角色的场景传送，包括更新场景归属和行动队列

        Args:
            actors: 要传送的角色集合
            stage_destination: 目标场景
        """
        for actor_entity in actors:
            current_stage = self.resolve_stage_entity(actor_entity)
            assert current_stage is not None, "角色没有当前场景"
            assert current_stage != stage_destination, "不应该传送到当前场景"

            actor_comp = actor_entity.get(ActorComponent)
            assert actor_comp is not None, "actor_comp is None"

            # 更改所处场景的标识
            actor_entity.replace(
                ActorComponent,
                actor_comp.name,
                actor_comp.character_sheet_name,
                stage_destination.name,
            )

            # 通知角色自身的传送过程
            self.notify_entities(
                entities={actor_entity},
                agent_event=TransStageEvent(
                    message=_format_stage_transition_message(
                        current_stage.name, stage_destination.name
                    ),
                    actor=actor_entity.name,
                    from_stage=current_stage.name,
                    to_stage=stage_destination.name,
                ),
            )

    ###############################################################################################################################################
    def _broadcast_arrival_notifications(
        self, actors: Set[Entity], stage_destination: Entity
    ) -> None:
        """
        处理角色进入场景的通知

        Args:
            actors: 进入的角色集合
            stage_destination: 目标场景
        """
        for actor_entity in actors:
            # 向所在场景及所在场景内除自身外的其他人宣布，这货到了
            self.broadcast_to_stage(
                entity=stage_destination,
                agent_event=AgentEvent(
                    message=_format_stage_arrival_message(
                        actor_entity.name, stage_destination.name
                    ),
                ),
                exclude_entities={actor_entity},
            )

    ###############################################################################################################################################
    def stage_transition(self, actors: Set[Entity], stage_destination: Entity) -> None:
        """
        场景传送的主协调函数

        Args:
            actors: 需要传送的角色集合
            stage_destination: 目标场景
        """
        # 0. 访问控制：PlayerOnlyStage 只允许玩家进入
        if stage_destination.has(PlayerOnlyStageComponent):
            for actor in actors:
                assert actor.has(PlayerComponent), (
                    f"角色 {actor.name} 试图进入仅玩家场景 {stage_destination.name}，"
                    "但该角色不是玩家！这是程序逻辑错误。"
                )

        # 1. 验证前置条件并过滤有效角色
        actors_to_transfer = self._validate_stage_transition_prerequisites(
            actors, stage_destination
        )

        # 如果没有角色需要传送，直接返回
        if not actors_to_transfer:
            return

        # 2. 处理角色离开场景
        self._broadcast_departure_notifications(actors_to_transfer)

        # 3. 执行场景传送
        self._update_actors_stage_membership(actors_to_transfer, stage_destination)

        # 4. 处理角色进入场景
        self._broadcast_arrival_notifications(actors_to_transfer, stage_destination)

    #######################################################################################################################################
    def find_human_messages_by_attribute(
        self,
        actor_entity: Entity,
        attribute_key: str,
        attribute_value: str,
        reverse_order: bool = True,
    ) -> List[HumanMessage]:

        found_messages: List[HumanMessage] = []

        context = self.get_agent_context(actor_entity).context

        # 进行查找。
        for chat_message in reversed(context) if reverse_order else context:

            if not isinstance(chat_message, HumanMessage):
                continue

            try:
                # 直接从 HumanMessage 对象获取属性，而不是从嵌套的 kwargs 中获取
                if hasattr(chat_message, attribute_key):
                    if getattr(chat_message, attribute_key) == attribute_value:
                        found_messages.append(chat_message)

            except Exception as e:
                logger.error(f"find_recent_human_message_by_attribute error: {e}")
                continue

        return found_messages

    #######################################################################################################################################
    def delete_human_messages_by_attribute(
        self,
        actor_entity: Entity,
        human_messages: List[HumanMessage],
    ) -> int:

        if len(human_messages) == 0:
            return 0

        context = self.get_agent_context(actor_entity).context
        original_length = len(context)

        # 删除指定的 HumanMessage 对象
        context[:] = [msg for msg in context if msg not in human_messages]

        deleted_count = original_length - len(context)
        if deleted_count > 0:
            logger.debug(
                f"Deleted {deleted_count} HumanMessage(s) from {actor_entity.name}'s chat history."
            )
        return deleted_count

    #######################################################################################################################################
    def remove_message_range(
        self, entity: Entity, begin_message: HumanMessage, end_message: HumanMessage
    ) -> List[SystemMessage | HumanMessage | AIMessage]:
        """
        从实体的上下文中删除指定范围的消息（从 begin_message 到 end_message，包含两端）

        Args:
            entity: 要操作的实体
            begin_message: 范围起始消息
            end_message: 范围结束消息

        Returns:
            被删除的消息列表
        """
        assert (
            begin_message != end_message
        ), "begin_message and end_message should not be the same"

        agent_context = self.get_agent_context(entity)
        begin_message_index = agent_context.context.index(begin_message)
        end_message_index = agent_context.context.index(end_message) + 1

        # 保存要删除的消息
        deleted_messages = agent_context.context[begin_message_index:end_message_index]

        # 开始移除！！！！。
        del agent_context.context[begin_message_index:end_message_index]
        # logger.debug(f"remove_message_range= {entity.name}")
        # logger.debug(f"begin_message: \n{begin_message.model_dump_json(indent=2)}")
        # logger.debug(f"end_message: \n{end_message.model_dump_json(indent=2)}")

        return deleted_messages

    #######################################################################################################################################
