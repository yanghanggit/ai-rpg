from enum import IntEnum, unique
from typing import Dict, List, Optional, Set, final, override
from loguru import logger
from ..entitas import Context, Entity, Matcher
from ..models import (
    COMPONENT_TYPES,
    ActorComponent,
    AppearanceComponent,
    ComponentSerialization,
    DeathComponent,
    EntitySerialization,
    PlayerComponent,
    IdentityComponent,
    StageComponent,
    WorldComponent,
    HomeComponent,
    DungeonComponent,
)


###############################################################################################################################################
@unique
@final
class InteractionError(IntEnum):
    """Actor 交互验证的错误类型枚举。

    用于表示 validate_actor_interaction 函数的验证结果。
    值为 NONE 表示验证通过，其他值表示具体的错误类型。
    """

    NONE = 0  # 无错误
    TARGET_NOT_FOUND = 1  # 目标未找到
    INITIATOR_NOT_ON_STAGE = 2  # 发起者不在场景中
    DIFFERENT_STAGES = 3  # 不在同一场景


###############################################################################################################################################
class RPGEntityManager(Context):
    """RPG 游戏的实体管理器，基于 ECS 架构。

    核心职责：
    1. 实体生命周期管理：创建、销毁、维护名称索引以支持快速查找
    2. 实体序列化：支持游戏状态的保存与恢复
    3. 类型化查询：提供 World、Stage、Actor、Player 等类型特定的实体查询方法
    4. 关系查询：查询场景上的角色分布、角色外观、交互验证等

    设计原则：专注于"检索"和不改变状态的操作，保持职责单一。
    """

    ###############################################################################################################################################
    def __init__(
        self,
    ) -> None:
        super().__init__()
        self._entity_name_index: Dict[str, Entity] = {}  # （方便快速查找用）

    ###############################################################################################################################################
    def _create_entity(self, name: str) -> Entity:
        """创建并注册一个新实体（内部方法）。

        调用父类的 create_entity 创建实体，并将其注册到内部名称索引中。
        这确保每个实体都可以通过名称快速查找。

        Args:
            name: 实体名称，必须唯一

        Returns:
            Entity: 新创建的实体
        """
        entity = super().create_entity()
        entity._name = str(name)
        self._entity_name_index[name] = entity
        return entity

    ###############################################################################################################################################
    @override
    def destroy_entity(self, entity: Entity) -> None:
        """销毁实体并清理索引。

        重写父类的 destroy_entity 方法，在销毁实体前先从内部名称索引中移除。
        这确保名称索引与实际存在的实体保持一致。

        Args:
            entity: 要销毁的实体
        """
        self._entity_name_index.pop(entity.name, None)
        return super().destroy_entity(entity)

    ###############################################################################################################################################
    def _serialize_entity(self, entity: Entity) -> EntitySerialization:
        """序列化单个实体（内部方法）。

        将单个 Entity 对象转换为 EntitySerialization 数据结构。
        只序列化在 COMPONENTS_REGISTRY 中注册的组件，忽略未注册的组件。
        由 serialize_entities 公共方法调用。

        Args:
            entity: 要序列化的实体

        Returns:
            EntitySerialization: 序列化后的实体数据
        """
        entity_serialization = EntitySerialization(name=entity.name, components=[])

        for key, value in entity._components.items():
            if COMPONENT_TYPES.get(key.__name__) is None:
                continue
            entity_serialization.components.append(
                ComponentSerialization(name=key.__name__, data=value.model_dump())
            )
        return entity_serialization

    ###############################################################################################################################################
    def serialize_entities(self, entities: Set[Entity]) -> List[EntitySerialization]:
        """将实体集合序列化为可持久化的数据结构。

        将 Entity 对象集合转换为 EntitySerialization 列表，用于保存游戏状态、
        网络传输或其他持久化需求。序列化过程会按 IdentityComponent.creation_order
        排序，确保输出顺序的一致性。

        Args:
            entities: 要序列化的实体集合

        Returns:
            List[EntitySerialization]: 序列化后的实体数据列表，按 creation_order 排序
        """
        entity_serializations: List[EntitySerialization] = []

        entities_copy = list(entities)

        # 保证有顺序。防止set引起的顺序不一致。
        sort_actors = sorted(
            entities_copy,
            key=lambda entity: entity.get(IdentityComponent).creation_order,
        )

        for entity in sort_actors:
            entity_serialization = self._serialize_entity(entity)
            entity_serializations.append(entity_serialization)

        return entity_serializations

    ###############################################################################################################################################
    def deserialize_entities(
        self, entities_serialization: List[EntitySerialization]
    ) -> Set[Entity]:
        """从序列化数据还原实体集合。

        将 EntitySerialization 列表反序列化为 Entity 对象集合，用于加载游戏状态、
        接收网络数据或其他数据恢复场景。会自动创建实体并恢复所有组件数据。

        注意：如果实体名称已存在，会触发断言错误，确保不会重复创建同名实体。

        Args:
            entities_serialization: 序列化的实体数据列表

        Returns:
            Set[Entity]: 反序列化后的实体集合

        Raises:
            AssertionError: 当实体名称已存在时
        """
        deserialized_entities: Set[Entity] = set()

        for entity_serialization in entities_serialization:

            assert (
                self.get_entity_by_name(entity_serialization.name) is None
            ), f"Entity with name already exists: {entity_serialization.name}"

            entity = self._create_entity(entity_serialization.name)
            deserialized_entities.add(entity)  # 添加到返回的集合中

            for comp_serialization in entity_serialization.components:

                comp_class = COMPONENT_TYPES.get(comp_serialization.name)
                assert comp_class is not None

                # 使用 Pydantic 的方式直接从字典创建实例
                restore_comp = comp_class(**comp_serialization.data)
                assert restore_comp is not None

                logger.debug(
                    f"comp_class = {comp_class.__name__}, comp = {restore_comp}"
                )
                entity.set(comp_class, restore_comp)

        return deserialized_entities

    ###############################################################################################################################################
    def get_world_entity(self, world_name: str) -> Optional[Entity]:
        """通过世界名称获取世界实体。

        查找具有指定名称且包含 WorldComponent 的实体。

        Args:
            world_name: 世界名称

        Returns:
            Optional[Entity]: 匹配的世界实体，如果不存在则返回 None
        """
        entity: Optional[Entity] = self.get_entity_by_name(world_name)
        if entity is not None and entity.has(WorldComponent):
            return entity
        return None

    ###############################################################################################################################################
    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        """通过名称获取实体。

        从内部名称索引中查找实体，不区分实体类型。
        这是最基础的实体查找方法，其他类型特定的查找方法都基于此实现。

        Args:
            name: 实体名称

        Returns:
            Optional[Entity]: 匹配的实体，如果不存在则返回 None
        """
        return self._entity_name_index.get(name, None)

    ###############################################################################################################################################
    def get_stage_entity(self, stage_name: str) -> Optional[Entity]:
        """通过场景名称获取场景实体。

        查找具有指定名称且包含 StageComponent 的实体。

        Args:
            stage_name: 场景名称

        Returns:
            Optional[Entity]: 匹配的场景实体，如果不存在则返回 None
        """
        entity: Optional[Entity] = self.get_entity_by_name(stage_name)
        if entity is not None and entity.has(StageComponent):
            return entity
        return None

    ###############################################################################################################################################
    def get_actor_entity(self, actor_name: str) -> Optional[Entity]:
        """通过角色名称获取角色实体。

        查找具有指定名称且包含 ActorComponent 的实体。

        Args:
            actor_name: 角色名称

        Returns:
            Optional[Entity]: 匹配的角色实体，如果不存在则返回 None
        """
        entity: Optional[Entity] = self.get_entity_by_name(actor_name)
        if entity is not None and entity.has(ActorComponent):
            return entity
        return None

    ###############################################################################################################################################
    def resolve_stage_entity(self, entity: Entity) -> Optional[Entity]:
        """解析并返回 Stage 实体。

        这是一个类型解析函数，能够智能地从不同类型的实体中获取对应的 Stage 实体：
        - 如果传入的是 Stage 实体，直接返回该实体本身
        - 如果传入的是 Actor 实体，返回该 Actor 当前所在的 Stage 实体
        - 如果传入的实体既不是 Stage 也不是 Actor，返回 None

        这个函数常用于需要获取场景信息的场景，无论调用者持有的是 Stage 还是 Actor 的引用。

        Args:
            entity: 要解析的实体，可以是 Stage 实体或 Actor 实体

        Returns:
            Optional[Entity]: 解析出的 Stage 实体，如果无法解析则返回 None
        """
        if entity.has(StageComponent):
            return entity
        elif entity.has(ActorComponent):
            actor_comp = entity.get(ActorComponent)
            return self.get_stage_entity(actor_comp.current_stage)
        return None

    ###############################################################################################################################################
    def get_player_entity(self, player_name: Optional[str] = None) -> Optional[Entity]:
        """获取玩家实体。

        通过 PlayerComponent 查找玩家实体。系统中应该最多只有一个玩家实体。
        如果不指定 player_name，返回系统中唯一的玩家实体（如果存在）。
        如果指定 player_name，返回匹配该名称的玩家实体。

        Args:
            player_name: 玩家名称（PlayerComponent.player_name 字段）。
                        如果为 None，返回系统中唯一的玩家实体。

        Returns:
            Optional[Entity]: 匹配的玩家实体，如果不存在则返回 None
        """
        player_entities = self.get_group(
            Matcher(
                all_of=[PlayerComponent],
            )
        ).entities

        assert len(player_entities) <= 1, "There should be at most one player entity."

        # 如果没有指定 player_name，返回唯一的玩家实体
        if player_name is None:
            return next(iter(player_entities), None)

        # 如果指定了 player_name，通过名称匹配
        for player_entity in player_entities:
            player_comp = player_entity.get(PlayerComponent)
            if player_comp.player_name == player_name:
                return player_entity
        return None

    ###############################################################################################################################################
    def get_actors_on_stage(self, entity: Entity) -> Set[Entity]:
        """获取指定场景上的所有 Actor 实体。

        返回与传入实体在同一场景中的所有 Actor（包括活着和死亡的）。
        传入的实体可以是 Stage 本身，也可以是场景中的某个 Actor。

        Args:
            entity: Stage 实体或 Actor 实体

        Returns:
            Set[Entity]: 该场景上的所有 Actor 实体集合（包括已死亡的）
        """
        stage_entity = self.resolve_stage_entity(entity)
        assert stage_entity is not None
        if stage_entity is None:
            return set()

        # 直接在这里构建stage到actor的映射
        ret: Set[Entity] = set()

        actor_entities: Set[Entity] = self.get_group(
            Matcher(all_of=[ActorComponent])
        ).entities

        # 以stage为key，actor为value
        for actor_entity in actor_entities:
            actor_stage_entity = self.resolve_stage_entity(actor_entity)
            assert actor_stage_entity is not None, f"actor_entity = {actor_entity}"
            if actor_stage_entity != stage_entity:
                # 不同的stage不算在内
                continue

            ret.add(actor_entity)

        return ret

    ###############################################################################################################################################
    def get_alive_actors_on_stage(self, entity: Entity) -> Set[Entity]:
        """获取指定场景上存活的 Actor 实体。

        过滤掉带有 DeathComponent 的 Actor，只返回活着的 Actor。

        Args:
            entity: Stage 实体或 Actor 实体

        Returns:
            Set[Entity]: 该场景上存活的 Actor 实体集合（不包括已死亡的）
        """
        ret = self.get_actors_on_stage(entity)
        return {actor for actor in ret if not actor.has(DeathComponent)}

    ###############################################################################################################################################
    def get_actor_appearances_on_stage(self, entity: Entity) -> Dict[str, str]:
        """获取场景上存活 Actor 的外观信息映射。

        仅返回存活且具有 AppearanceComponent 的 Actor 的外观信息。
        常用于生成场景描述或增强消息内容。

        Args:
            entity: Stage 实体或 Actor 实体

        Returns:
            Dict[str, str]: 角色名称到外观描述的映射 {角色名: 外观描述}
        """
        ret: Dict[str, str] = {}
        for actor in self.get_alive_actors_on_stage(entity):
            if actor.has(AppearanceComponent):
                final_appearance = actor.get(AppearanceComponent)
                ret.setdefault(final_appearance.name, final_appearance.appearance)
        return ret

    ###############################################################################################################################################
    def is_actor_in_home_stage(self, actor_entity: Entity) -> bool:
        """判断 Actor 是否在家园场景中。

        检查 Actor 所在的 Stage 是否具有 HomeComponent。

        Args:
            actor_entity: Actor 实体

        Returns:
            bool: 在家园场景中返回 True，否则返回 False
        """
        assert actor_entity.has(ActorComponent), "actor_entity must have ActorComponent"
        if not actor_entity.has(ActorComponent):
            return False

        stage_entity = self.resolve_stage_entity(actor_entity)
        assert stage_entity is not None, "stage_entity is None"
        if stage_entity is None:
            return False

        if stage_entity.has(HomeComponent):
            assert not stage_entity.has(
                DungeonComponent
            ), "stage_entity has both HomeComponent and DungeonComponent!"

        return stage_entity.has(HomeComponent)

    ###############################################################################################################################################
    def is_actor_in_dungeon_stage(self, actor_entity: Entity) -> bool:
        """判断 Actor 是否在地下城场景中。

        检查 Actor 所在的 Stage 是否具有 DungeonComponent。

        Args:
            actor_entity: Actor 实体

        Returns:
            bool: 在地下城场景中返回 True，否则返回 False
        """
        assert actor_entity.has(ActorComponent), "actor_entity must have ActorComponent"
        if not actor_entity.has(ActorComponent):
            return False

        stage_entity = self.resolve_stage_entity(actor_entity)
        assert stage_entity is not None, "stage_entity is None"
        if stage_entity is None:
            return False

        if stage_entity.has(DungeonComponent):
            assert not stage_entity.has(
                HomeComponent
            ), "stage_entity has both DungeonComponent and HomeComponent!"

        return stage_entity.has(DungeonComponent)

    ###############################################################################################################################################
    def validate_actor_interaction(
        self, initiator_entity: Entity, target_name: str
    ) -> InteractionError:
        """验证两个 Actor 之间是否可以进行交互。

        检查发起者和目标是否满足交互条件：
        1. 目标 Actor 必须存在
        2. 发起者必须在某个场景中
        3. 发起者和目标必须在同一场景中

        Args:
            initiator_entity: 发起交互的实体
            target_name: 目标 Actor 的名称

        Returns:
            InteractionError: 验证结果，NONE 表示可以交互，其他值表示具体错误
        """
        actor_entity: Optional[Entity] = self.get_actor_entity(target_name)
        if actor_entity is None:
            return InteractionError.TARGET_NOT_FOUND

        current_stage_entity = self.resolve_stage_entity(initiator_entity)
        if current_stage_entity is None:
            return InteractionError.INITIATOR_NOT_ON_STAGE

        target_stage_entity = self.resolve_stage_entity(actor_entity)
        if target_stage_entity != current_stage_entity:
            return InteractionError.DIFFERENT_STAGES

        return InteractionError.NONE

    ###############################################################################################################################################
    def get_actors_by_stage(
        self,
    ) -> Dict[Entity, List[Entity]]:
        """获取所有场景到 Actor 的分组映射。

        返回以 Stage 实体为键、Actor 实体列表为值的字典。
        包含所有 Stage，即使某个 Stage 上没有任何 Actor（对应空列表）。

        Returns:
            Dict[Entity, List[Entity]]: Stage 实体到 Actor 实体列表的映射
        """
        ret: Dict[Entity, List[Entity]] = {}

        actor_entities: Set[Entity] = self.get_group(
            Matcher(all_of=[ActorComponent])
        ).entities

        # 以stage为key，actor为value
        for actor_entity in actor_entities:

            stage_entity = self.resolve_stage_entity(actor_entity)
            assert stage_entity is not None, f"actor_entity = {actor_entity}"
            if stage_entity is None:
                continue

            ret.setdefault(stage_entity, []).append(actor_entity)

        # 补一下没有actor的stage
        stage_entities: Set[Entity] = self.get_group(
            Matcher(all_of=[StageComponent])
        ).entities
        for stage_entity in stage_entities:
            if stage_entity not in ret:
                ret.setdefault(stage_entity, [])

        return ret

    ###############################################################################################################################################
    def get_actors_by_stage_as_names(
        self,
    ) -> Dict[str, List[str]]:
        """获取所有场景到 Actor 的分组映射（名称版本）。

        返回以 Stage 名称为键、Actor 名称列表为值的字典。
        这是 get_actors_by_stage 的字符串版本，用于序列化或 API 响应。

        Returns:
            Dict[str, List[str]]: Stage 名称到 Actor 名称列表的映射
        """
        ret: Dict[str, List[str]] = {}
        mapping = self.get_actors_by_stage()

        for stage_entity, actor_entities in mapping.items():
            ret[stage_entity.name] = [
                actor_entity.name for actor_entity in actor_entities
            ]

        return ret

    ###############################################################################################################################################
