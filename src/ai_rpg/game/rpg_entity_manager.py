from typing import Dict, List, Optional, Set, override
from ..entitas import Context, Entity, Matcher
from ..models import (
    COMPONENT_TYPES,
    ActorComponent,
    ComponentSerialization,
    EntitySerialization,
    PlayerComponent,
    IdentityComponent,
    StageComponent,
    WorldComponent,
    HomeComponent,
    DungeonComponent,
)
from loguru import logger


###############################################################################################################################################
class RPGEntityManager(Context):
    """RPG 游戏的实体管理器"""

    ###############################################################################################################################################
    def __init__(
        self,
    ) -> None:
        super().__init__()
        self._entity_name_index: Dict[str, Entity] = {}  # （方便快速查找用）

    ###############################################################################################################################################
    def _create_entity(self, name: str) -> Entity:
        """创建并注册一个新实体（内部方法）。"""
        entity = super().create_entity()
        entity._name = str(name)
        self._entity_name_index[name] = entity
        return entity

    ###############################################################################################################################################
    @override
    def destroy_entity(self, entity: Entity) -> None:
        """销毁实体并清理索引。"""
        self._entity_name_index.pop(entity.name, None)
        return super().destroy_entity(entity)

    ###############################################################################################################################################
    def _serialize_entity(self, entity: Entity) -> EntitySerialization:
        """序列化单个实体（内部方法）。"""
        components = [
            ComponentSerialization(name=key.__name__, data=value.model_dump())
            for key, value in entity._components.items()
            if COMPONENT_TYPES.get(key.__name__) is not None
        ]
        return EntitySerialization(name=entity.name, components=components)

    ###############################################################################################################################################
    def serialize_entities(self, entities: Set[Entity]) -> List[EntitySerialization]:
        """将实体集合序列化为可持久化的数据结构。"""
        entity_serializations: List[EntitySerialization] = []

        entities_copy = list(entities)

        # 保证有顺序。防止set引起的顺序不一致。
        sort_actors = sorted(
            entities_copy,
            key=lambda entity: entity.get(IdentityComponent).creation_order,
        )

        # 遍历排序后的实体列表，依次序列化每个实体并添加到结果列表中
        for entity in sort_actors:
            entity_serialization = self._serialize_entity(entity)
            entity_serializations.append(entity_serialization)

        return entity_serializations

    ###############################################################################################################################################
    def deserialize_entities(
        self, entities_serialization: List[EntitySerialization]
    ) -> Set[Entity]:
        """从序列化数据还原实体集合。"""
        deserialized_entities: Set[Entity] = set()

        for entity_serialization in entities_serialization:

            assert (
                self.get_entity_by_name(entity_serialization.name) is None
            ), f"Entity with name already exists: {entity_serialization.name}"

            entity = self._create_entity(entity_serialization.name)
            deserialized_entities.add(entity)  # 添加到返回的集合中

            for comp_serialization in entity_serialization.components:

                comp_class = COMPONENT_TYPES.get(comp_serialization.name)
                assert (
                    comp_class is not None
                ), f"Component class not found for {comp_serialization.name}"

                # 使用 Pydantic 的方式直接从字典创建实例
                restore_comp = comp_class(**comp_serialization.data)
                assert (
                    restore_comp is not None
                ), f"Failed to restore component {comp_class.__name__} for entity {entity_serialization.name}"

                logger.debug(
                    f"comp_class = {comp_class.__name__}, comp = {restore_comp}"
                )
                entity.set(comp_class, restore_comp)

        return deserialized_entities

    ###############################################################################################################################################
    def get_world_entity(self, world_name: str) -> Optional[Entity]:
        """通过世界名称获取世界实体。"""
        entity: Optional[Entity] = self.get_entity_by_name(world_name)
        if entity is not None and entity.has(WorldComponent):
            return entity
        return None

    ###############################################################################################################################################
    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        """通过名称获取实体。"""
        return self._entity_name_index.get(name, None)

    ###############################################################################################################################################
    def get_stage_entity(self, stage_name: str) -> Optional[Entity]:
        """通过场景名称获取场景实体。"""
        entity: Optional[Entity] = self.get_entity_by_name(stage_name)
        if entity is not None and entity.has(StageComponent):
            return entity
        return None

    ###############################################################################################################################################
    def get_actor_entity(self, actor_name: str) -> Optional[Entity]:
        """通过角色名称获取角色实体。"""
        entity: Optional[Entity] = self.get_entity_by_name(actor_name)
        if entity is not None and entity.has(ActorComponent):
            return entity
        return None

    ###############################################################################################################################################
    def resolve_stage_entity(self, entity: Entity) -> Optional[Entity]:
        """解析并返回 Stage 实体。"""

        if entity.has(StageComponent):

            # 如果传入的是 Stage 实体，直接返回该实体本身
            return entity

        elif entity.has(ActorComponent):

            # 如果传入的是 Actor 实体，则尝试获取该 Actor 当前所在的 Stage 实体
            actor_comp = entity.get(ActorComponent)
            return self.get_stage_entity(actor_comp.current_stage)

        else:
            assert (
                False
            ), f"无法解析 Stage 实体，传入的实体既不是 Stage 也不是 Actor: {entity}"

        return None

    ###############################################################################################################################################
    def get_player_entity(self) -> Optional[Entity]:
        """获取玩家实体"""
        player_entities = self.get_group(
            Matcher(
                all_of=[PlayerComponent],
            )
        ).entities

        assert len(player_entities) == 1, "There should be exactly one player entity."
        # 如果没有指定 player_name，返回唯一的玩家实体
        return next(iter(player_entities), None)

    ###############################################################################################################################################
    def get_actors_in_stage(self, entity: Entity) -> Set[Entity]:
        """获取指定场景上的所有 Actor 实体。"""

        stage_entity = self.resolve_stage_entity(entity)
        assert stage_entity is not None, f"entity = {entity}"

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
    def is_actor_in_home_stage(self, actor_entity: Entity) -> bool:
        """判断 Actor 是否在家园场景中。"""
        assert actor_entity.has(ActorComponent), "actor_entity must have ActorComponent"
        stage_entity = self.resolve_stage_entity(actor_entity)
        assert stage_entity is not None, "stage_entity is None"
        assert not (
            stage_entity.has(HomeComponent) and stage_entity.has(DungeonComponent)
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
        stage_entity = self.resolve_stage_entity(actor_entity)
        assert stage_entity is not None, "stage_entity is None"
        assert not (
            stage_entity.has(DungeonComponent) and stage_entity.has(HomeComponent)
        ), "stage_entity has both DungeonComponent and HomeComponent!"

        return stage_entity.has(DungeonComponent)

    ###############################################################################################################################################
    def get_actors_by_stage(
        self,
    ) -> Dict[Entity, List[Entity]]:
        """获取所有场景到 Actor 的分组映射。"""
        ret: Dict[Entity, List[Entity]] = {}

        actor_entities: Set[Entity] = self.get_group(
            Matcher(all_of=[ActorComponent])
        ).entities

        # 以stage为key，actor为value
        for actor_entity in actor_entities:

            stage_entity = self.resolve_stage_entity(actor_entity)
            assert stage_entity is not None, f"actor_entity = {actor_entity}"
            ret.setdefault(stage_entity, []).append(actor_entity)

        # 补一下没有actor的stage
        stage_entities: Set[Entity] = self.get_group(
            Matcher(all_of=[StageComponent])
        ).entities

        # 确保每个 stage 都在字典中，即使没有任何 actor 关联它
        for stage_entity in stage_entities:
            if stage_entity not in ret:
                ret.setdefault(stage_entity, [])

        return ret

    ###############################################################################################################################################
    def get_actors_by_stage_as_names(
        self,
    ) -> Dict[str, List[str]]:
        """获取所有场景到 Actor 的分组映射（名称版本）。"""
        ret: Dict[str, List[str]] = {}
        mapping = self.get_actors_by_stage()

        for stage_entity, actor_entities in mapping.items():
            ret[stage_entity.name] = [
                actor_entity.name for actor_entity in actor_entities
            ]

        return ret

    ###############################################################################################################################################
