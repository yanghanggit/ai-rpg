import copy
import uuid
from typing import Any, Final, List, Set
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
    RPG游戏核心类 - 整合ECS架构与LLM驱动的智能游戏世界

    RPGGame 是整个RPG游戏系统的中央控制器，通过多重继承整合了三个核心功能模块：
    - GameSession: 提供游戏会话管理和生命周期控制
    - RPGEntityManager: 基于ECS（实体-组件-系统）架构的实体管理
    - RPGGamePipelineManager: LLM处理管道和异步任务管理

    核心架构：
        本类采用 ECS（Entity-Component-System）架构，所有游戏对象（角色、场景、世界系统）
        都是实体（Entity），通过添加不同的组件（Component）来定义其属性和行为。
        每个实体都拥有独立的LLM上下文，可以进行智能对话和决策。

    主要职责：
        1. 游戏世界管理：创建、加载、保存游戏世界状态
        2. 实体生命周期：创建和销毁世界系统、角色、场景等实体
        3. 消息系统：管理实体间的消息传递和LLM上下文
        4. 场景管理：处理角色在不同场景间的转换
        5. 事件广播：向场景中的多个实体分发游戏事件
        6. 管道协调：管理LLM处理管道和异步任务执行

    核心概念：
        - Entity（实体）: 游戏中的基本对象，如角色、场景、世界系统
        - Component（组件）: 定义实体属性的数据容器，如 ActorComponent、StageComponent
        - AgentContext（代理上下文）: 实体的LLM消息历史，包含 SystemMessage、HumanMessage、AIMessage
        - World（世界）: 包含游戏蓝图配置和运行时状态的容器
        - PlayerSession（玩家会话）: 玩家的连接和状态信息

    生命周期方法：
        - new_game(): 创建新游戏，初始化所有实体
        - load_game(): 从序列化数据恢复游戏状态
        - save_game(): 保存当前游戏状态到持久化存储
        - initialize(): 异步初始化所有管道
        - exit(): 清理资源并关闭管道

    实体类型：
        1. WorldSystem（世界系统）: 全局规则管理器、叙事者
        2. Actor（角色）: 玩家角色、NPC、敌人，拥有属性、背包、技能
        3. Stage（场景）: 游戏事件发生的地点，包含环境描述和居住角色

    消息管理：
        - add_system_message(): 添加系统提示词（必须是第一条消息）
        - add_human_message(): 添加用户输入消息
        - add_ai_message(): 添加LLM响应消息
        - broadcast_to_stage(): 向场景广播事件
        - notify_entities(): 向指定实体集合发送通知

    场景转换：
        - stage_transition(): 处理角色在场景间的移动
        - 自动处理离开/到达通知
        - 支持访问控制（如仅玩家场景）

    Attributes:
        player_session: 玩家会话对象，包含玩家信息
        world: 游戏世界对象，包含蓝图配置和运行时状态

    Note:
        - 必须按照特定顺序初始化父类（GameSession → RPGEntityManager → RPGGamePipelineManager）
        - 所有实体自动分配唯一的 runtime_index 和 UUID
        - 实体的LLM上下文存储在 world.agents_context 中
        - 场景转换会自动广播通知给相关实体
        - 支持链式调用（方法返回 self）

    Example:
        >>> # 创建新游戏
        >>> game = RPGGame(
        ...     name="MyRPG",
        ...     player_session=PlayerSession(name="Player1", actor="勇者"),
        ...     world=World(blueprint=game_blueprint)
        ... )
        >>> await game.initialize()  # 初始化管道
        >>> game.new_game()  # 创建游戏世界
        >>>
        >>> # 获取玩家角色
        >>> player = game.get_actor_entity("勇者")
        >>>
        >>> # 添加消息到角色上下文
        >>> game.add_human_message(player, "你好，世界！")
        >>>
        >>> # 场景转换
        >>> dungeon = game.get_stage_entity("地下城")
        >>> game.stage_transition(actors={player}, stage_destination=dungeon)
        >>>
        >>> # 保存游戏
        >>> game.save_game()
        >>>
        >>> # 清理资源
        >>> game.exit()

    See Also:
        - GameSession: 游戏会话基类
        - RPGEntityManager: 实体管理器
        - RPGGamePipelineManager: 管道管理器
        - World: 游戏世界模型
        - PlayerSession: 玩家会话模型
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
    def get_agent_context(self, entity: Entity) -> AgentContext:
        """
        获取或创建实体的LLM上下文（短期记忆）

        从游戏世界的 agents_context 字典中获取指定实体的 AgentContext。
        如果该实体还没有上下文记录，会自动创建一个空的 AgentContext 并返回。
        这个上下文用于存储实体与LLM交互的消息历史（SystemMessage、HumanMessage、AIMessage）。

        Args:
            entity: 要获取上下文的实体

        Returns:
            AgentContext: 实体的上下文对象，包含消息历史列表

        Note:
            - 使用 setdefault 确保线程安全的获取或创建操作
            - 新创建的 AgentContext 会自动添加到 world.agents_context 中
            - 返回的是可变对象引用，对其修改会直接影响游戏世界状态
            - 上下文包含三种消息类型：SystemMessage（系统提示）、HumanMessage（用户输入）、AIMessage（AI响应）

        Example:
            >>> context = game.get_agent_context(player_entity)
            >>> print(len(context.context))  # 查看消息历史长度
            >>> context.context.append(HumanMessage(content="Hello"))
        """
        return self.world.agents_context.setdefault(
            entity.name, AgentContext(name=entity.name, context=[])
        )

    ###############################################################################################################################################
    @override
    def destroy_entity(self, entity: Entity) -> None:
        """
        销毁实体并清理其相关资源

        覆盖父类的实体销毁方法，在调用父类销毁逻辑前，先清理实体的LLM上下文（短期记忆）。
        这确保了实体被完全移除时，其关联的所有数据都得到正确清理，避免内存泄漏。

        Args:
            entity: 要销毁的实体对象

        Note:
            - 该方法会先检查并移除实体在 world.agents_context 中的记录
            - 然后调用父类的 destroy_entity 完成实体从ECS系统中的移除
            - 销毁顺序：短期记忆清理 → 实体组件清理 → 实体从管理器移除
            - 销毁后该实体的所有组件和上下文都将不可访问
            - 如果实体不存在于 agents_context 中，不会抛出异常

        Warning:
            销毁实体是不可逆操作，请确保不再需要该实体及其数据

        Example:
            >>> # 销毁战斗中死亡的敌人实体
            >>> if enemy.get(CombatStatsComponent).hp <= 0:
            ...     game.destroy_entity(enemy)
        """
        logger.debug(f"TCGGame destroy entity: {entity.name}")
        if entity.name in self.world.agents_context:
            logger.debug(f"TCGGame destroy entity: {entity.name} in short term memory")
            self.world.agents_context.pop(entity.name, None)
        return super().destroy_entity(entity)

    ###############################################################################################################################################
    @override
    def exit(self) -> None:
        # 关闭所有管道
        self.shutdown_pipelines()
        # logger.warning(f"{self.name}, exit!!!!!!!!!!!!!!!!!!!!)")

    ###############################################################################################################################################
    @override
    async def initialize(self) -> None:
        # 初始化所有管道
        await self.initialize_pipelines()
        # logger.debug(f"Initialized all pipelines")

    ###############################################################################################################################################
    def new_game(self) -> "RPGGame":
        """
        创建并初始化一个新的RPG游戏世界

        按照预定义的顺序创建游戏世界中的所有核心实体，包括世界系统、角色、场景等，
        并建立它们之间的关联关系。该方法只能在空游戏世界中调用。

        执行步骤：
            1. 创建世界系统实体（WorldSystem）
            2. 创建角色实体（Actor）
            3. 分配玩家控制的角色（添加 PlayerComponent）
            4. 创建场景实体（Stage）
            5. 标记仅玩家可见的场景（添加 PlayerOnlyStageComponent）

        Returns:
            RPGGame: 返回自身实例，支持链式调用

        Raises:
            AssertionError: 如果游戏世界中已存在实体（entities_serialization 不为空）
            AssertionError: 如果玩家名字或角色为空
            AssertionError: 如果找不到玩家选择的角色实体
            AssertionError: 如果 player_only_stage 配置为空或找不到对应场景

        Note:
            - 该方法要求 world.entities_serialization 必须为空
            - 玩家信息必须在构造函数中正确设置（player_session.name 和 player_session.actor）
            - 所有实体创建完成后会自动建立角色与场景的关联关系

        Example:
            >>> game = RPGGame(name="MyGame", player_session=session, world=world)
            >>> game.new_game()  # 创建新游戏世界
        """
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
    def load_game(self) -> "RPGGame":
        """
        从序列化数据中恢复游戏世界状态

        将之前保存的游戏世界实体数据反序列化，重建整个游戏世界的状态。
        该方法只能在空的实体管理器中调用，且要求存在有效的序列化数据。

        Returns:
            RPGGame: 返回自身实例，支持链式调用

        Raises:
            AssertionError: 如果 world.entities_serialization 为空（没有可恢复的数据）
            AssertionError: 如果当前实体管理器中已存在实体（_entities 不为空）

        Note:
            - 恢复前必须确保当前游戏世界为空（_entities 长度为 0）
            - 序列化数据必须存在且有效（entities_serialization 长度大于 0）
            - 所有实体的状态、组件、上下文都会从序列化数据中完整恢复

        Example:
            >>> game = RPGGame(name="MyGame", player_session=session, world=world)
            >>> game.load_game()  # 从 world.entities_serialization 中恢复游戏
        """
        assert (
            len(self.world.entities_serialization) > 0
        ), "游戏中没有实体，不能恢复游戏"
        assert len(self._entities) == 0, "游戏中有实体，不能恢复游戏"
        self.deserialize_entities(self.world.entities_serialization)
        return self

    ###############################################################################################################################################
    def save_game(self) -> "RPGGame":
        """
        保存当前游戏世界状态到持久化存储

        将当前游戏世界中所有实体的状态序列化，并通过以下两种方式持久化：
        1. 正式保存：通过 persist_world_data 保存到数据库或文件系统
        2. 调试输出：通过 debug_verbose_world_data 生成详细的调试信息

        执行步骤：
            1. 序列化所有实体到 world.entities_serialization
            2. 调用 persist_world_data 持久化游戏数据
            3. 调用 debug_verbose_world_data 生成调试输出（仅开发环境）

        Returns:
            RPGGame: 返回自身实例，支持链式调用

        Note:
            - 序列化包括所有实体的组件、状态和LLM上下文
            - 保存操作会覆盖之前的 world.entities_serialization 数据
            - 调试输出保存在 verbose_dir 指定的目录中
            - 该方法是非阻塞的，不会等待持久化操作完成

        Example:
            >>> game.save_game()  # 保存当前游戏状态
            >>> # 支持链式调用
            >>> game.process_turn().save_game()
        """
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
        """
        创建世界系统实体，作为游戏世界的全局管理者

        世界系统是特殊的实体，不代表具体的角色或场景，而是作为游戏世界的
        全局规则管理器、叙事者或环境控制者。每个世界系统都拥有自己的LLM上下文，
        可以参与游戏事件的处理和叙述。

        为每个世界系统创建的组件：
            - RuntimeComponent: 运行时标识（名字、索引、UUID）
            - WorldComponent: 世界系统类型标记
            - SystemMessage: 系统级LLM提示词，定义其行为模式
            - KickOffComponent: 启动消息，用于游戏开始时的初始化

        Args:
            world_system_models: 世界系统模型列表，来自游戏蓝图配置

        Returns:
            List[Entity]: 创建完成的世界系统实体列表

        Raises:
            AssertionError: 如果实体创建失败
            AssertionError: 如果系统消息中缺少对应的实体名称

        Note:
            - 每个世界系统都会自动递增 world.runtime_index
            - 系统消息必须包含实体名称作为键
            - 这是 new_game 流程的第一步，在创建角色和场景之前执行
            - 世界系统不属于任何场景，是全局存在的

        Example:
            >>> world_systems = world.blueprint.world_systems
            >>> entities = game._create_world_entities(world_systems)
            >>> print(f"创建了 {len(entities)} 个世界系统")
        """
        world_entities: List[Entity] = []

        for world_system_model in world_system_models:

            # 创建实体
            world_system_entity = self._create_entity(world_system_model.name)
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
        """
        创建角色实体，包括玩家角色、NPC和敌人

        角色是游戏中最复杂的实体类型，拥有丰富的属性、能力和状态。
        每个角色都拥有独立的LLM上下文，可以进行智能对话和决策。
        此方法负责从蓝图数据中实例化角色，并为其初始化所有必要组件。

        为每个角色创建的组件：
            - RuntimeComponent: 运行时标识（名字、索引、UUID）
            - ActorComponent: 角色标记和场景归属（初始为空）
            - SystemMessage: 角色性格和行为提示词
            - KickOffComponent: 角色的启动对话
            - AppearanceComponent: 外观描述
            - CombatStatsComponent: 战斗属性（HP、攻击、防御等）
            - AllyComponent/EnemyComponent: 阵营标记（中立角色无特殊组件）
            - InventoryComponent: 背包系统，包含道具列表（每个道具自动生成UUID）
            - SkillBookComponent: 技能书，包含技能列表

        Args:
            actor_models: 角色模型列表，来自游戏蓝图配置

        Returns:
            List[Entity]: 创建完成的角色实体列表

        Raises:
            AssertionError: 如果实体创建失败
            AssertionError: 如果系统消息中缺少对应的角色名称
            AssertionError: 如果遇到未知的 ActorType
            AssertionError: 如果道具UUID不为空（应在此处生成）

        Note:
            - 角色私有知识库在环境初始化时已加载（setup_dev_environment.py）
            - 背包和技能使用 deepcopy 避免引用原始数据
            - 每个道具都会自动生成唯一的UUID
            - 战斗属性使用浅拷贝，保持内部对象引用
            - 这是 new_game 流程的第二步，在世界系统创建后执行
            - 初始创建时角色未分配场景，会在场景创建时建立关联

        Example:
            >>> actors = world.blueprint.actors
            >>> entities = game._create_actor_entities(actors)
            >>> for entity in entities:
            ...     inv = entity.get(InventoryComponent)
            ...     print(f"{entity.name} 有 {len(inv.items)} 个道具")
        """
        actor_entities: List[Entity] = []

        for actor_model in actor_models:

            # 创建实体
            actor_entity = self._create_entity(actor_model.name)
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
            # TODO: 未来需要从角色表中读取 base_body，目前暂时使用空字符串占位
            actor_entity.add(
                AppearanceComponent,
                actor_model.name,
                actor_model.character_sheet.base_body,  # base_body - TODO: 从 character_sheet 中读取基础身体形态
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
        """
        创建场景实体，并建立角色与场景的关联关系

        场景是游戏事件发生的地点，每个场景都有自己的环境描述、类型和居住的角色。
        场景也拥有LLM上下文，可以作为环境观察者参与事件描述。
        此方法不仅创建场景实体，还会更新所有角色的 ActorComponent，
        将其分配到对应的场景中。

        为每个场景创建的组件：
            - RuntimeComponent: 运行时标识（名字、索引、UUID）
            - StageComponent: 场景标记和类型信息
            - SystemMessage: 场景环境和氛围描述
            - KickOffComponent: 场景的初始描述
            - EnvironmentComponent: 动态环境状态（初始为空）
            - DungeonComponent: 地牢类型标记（如果适用）
            - HomeComponent: 家园/安全区类型标记（如果适用）

        Args:
            stage_models: 场景模型列表，来自游戏蓝图配置

        Returns:
            List[Entity]: 创建完成的场景实体列表

        Raises:
            AssertionError: 如果找不到场景中应该存在的角色实体

        Note:
            - 这是 new_game 流程的第四步，在角色创建后执行
            - 会遍历每个场景中的角色列表，更新其 ActorComponent 的 stage 字段
            - 初始环境描述为空，会在游戏运行时动态生成
            - 场景类型（DUNGEON/HOME）决定了添加哪个特殊组件
            - 此方法建立了角色与场景之间的双向关联

        Example:
            >>> stages = world.blueprint.stages
            >>> entities = game._create_stage_entities(stages)
            >>> for stage_entity in entities:
            ...     actors_here = game.get_alive_actors_on_stage(stage_entity)
            ...     print(f"场景 {stage_entity.name} 有 {len(actors_here)} 个角色")
        """
        stage_entities: List[Entity] = []

        for stage_model in stage_models:

            # 创建实体
            stage_entity = self._create_entity(stage_model.name)

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
        logger.debug(f"add_human_message: {entity.name} => \n{message_content}")
        if len(kwargs) > 0:
            # 如果 **kwargs 不是 空，就打印一下，这种消息比较特殊。
            logger.debug(f"kwargs: {kwargs}")

        agent_context = self.get_agent_context(entity)
        agent_context.context.extend([HumanMessage(content=message_content, **kwargs)])

    ###############################################################################################################################################
    def add_ai_message(self, entity: Entity, ai_messages: List[AIMessage]) -> None:
        """添加AI响应消息到实体的LLM上下文"""
        assert len(ai_messages) > 0, "ai_messages should not be empty"
        for ai_message in ai_messages:
            assert isinstance(ai_message, AIMessage)
            assert ai_message.content != "", "ai_message content should not be empty"
            logger.debug(f"add_ai_message: {entity.name} => \n{ai_message.content}")

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
        """
        向场景中的所有存活角色和场景实体广播事件消息

        该方法会自动解析实体所在的场景，然后向场景中所有存活的角色以及场景实体本身
        发送消息。可以通过 exclude_entities 参数排除特定的接收者（例如消息发起者本身）。

        Args:
            entity: 参考实体，用于确定目标场景（通常是消息发起者或场景实体）
            agent_event: 要广播的事件消息
            exclude_entities: 要排除的实体集合，这些实体不会收到广播消息
            **kwargs: 传递给 HumanMessage 的额外关键字参数（如自定义属性标记）

        Note:
            - 广播范围包括场景中所有存活角色 + 场景实体本身
            - 如果无法解析场景，方法会提前返回
            - 最终通过 notify_entities 完成实际的消息分发

        Example:
            >>> # 向场景广播角色行动，但排除行动者自己
            >>> game.broadcast_to_stage(
            ...     entity=actor,
            ...     agent_event=AgentEvent(message="某角色使用了技能"),
            ...     exclude_entities={actor}
            ... )
        """
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
        """
        向指定的实体集合发送通知消息，并同步到玩家客户端

        该方法执行两个关键操作：
        1. 将消息添加到每个实体的 LLM 上下文（短期记忆）
        2. 将事件消息发送到玩家会话，用于客户端显示

        Args:
            entities: 要接收通知的实体集合（可以是角色、场景等）
            agent_event: 要发送的事件消息对象
            **kwargs: 传递给 HumanMessage 的额外关键字参数（如事件类型、时间戳等）

        Note:
            - 每个实体都会在其上下文中添加一条 HumanMessage
            - 无论通知多少实体，只会向玩家客户端发送一次事件消息
            - 适用于需要同时通知多个实体的场景（如广播、群体通知等）

        Example:
            >>> # 通知场景中的多个角色
            >>> game.notify_entities(
            ...     entities={player, npc1, npc2, stage},
            ...     agent_event=AgentEvent(message="战斗开始！"),
            ...     event_type="combat_start"
            ... )
        """
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
    def filter_human_messages_by_attribute(
        self,
        actor_entity: Entity,
        attribute_key: str,
        attribute_value: str,
        reverse_order: bool = True,
    ) -> List[HumanMessage]:
        """
        根据指定的属性键值对过滤实体上下文中的 HumanMessage

        从实体的LLM上下文中筛选出具有特定属性值的所有 HumanMessage。
        支持正序或逆序遍历，默认从最新消息开始查找。

        Args:
            actor_entity: 要查询的实体
            attribute_key: 要匹配的属性键名（使用 hasattr 检查）
            attribute_value: 要匹配的属性值
            reverse_order: 是否逆序遍历（从最新到最旧），默认为 True

        Returns:
            List[HumanMessage]: 匹配的 HumanMessage 列表，如果没有找到则返回空列表

        Example:
            >>> # 查找所有标记为特定事件类型的消息
            >>> messages = game.filter_human_messages_by_attribute(
            ...     actor_entity=player,
            ...     attribute_key="event_type",
            ...     attribute_value="combat"
            ... )
        """
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
    def remove_human_messages(
        self,
        actor_entity: Entity,
        human_messages: List[HumanMessage],
    ) -> int:
        """
        从实体的上下文中删除指定的 HumanMessage 对象

        根据对象引用（非内容比较）从实体的LLM上下文中移除指定的消息列表。
        通常与 filter_human_messages_by_attribute 配合使用，先查找再删除。

        Args:
            actor_entity: 要操作的实体
            human_messages: 要删除的 HumanMessage 对象列表

        Returns:
            int: 实际删除的消息数量

        Example:
            >>> # 先查找特定类型的消息，然后删除
            >>> messages_to_remove = game.filter_human_messages_by_attribute(
            ...     actor_entity=player,
            ...     attribute_key="temp_hint",
            ...     attribute_value="true"
            ... )
            >>> deleted_count = game.remove_human_messages(player, messages_to_remove)
            >>> print(f"Deleted {deleted_count} temporary hints")
        """
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
