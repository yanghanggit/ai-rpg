from typing import Dict, List, Optional, Set, Type, override

from ..entitas import (
    Component,
    Context,
    ContextData,
    Entity,
    Matcher,
    dump_context,
    dump_entities,
    load_context,
)
from ..models import (
    COMPONENT_TYPES,
    ActorComponent,
    DungeonComponent,
    HomeComponent,
    PlayerComponent,
    StageComponent,
    WorldComponent,
    resolve_component_type,
)


###############################################################################################################################################
def _is_persistable_component(comp_type: Type[Component]) -> bool:
    """组件类型是否已注册（只有注册过的组件才会被整体序列化）。"""
    return COMPONENT_TYPES.get(comp_type.__name__) is not None


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
        entity.name = str(name)
        self._entity_name_index[name] = entity
        return entity

    ###############################################################################################################################################
    @override
    def destroy_entity(self, entity: Entity) -> None:
        """销毁实体并清理索引。"""
        self._entity_name_index.pop(entity.name, None)
        return super().destroy_entity(entity)

    ###############################################################################################################################################
    def serialize_entities(self, entities: Set[Entity]) -> ContextData:
        """将实体集合导出为 name-keyed 的 ContextData（只含已注册组件）。"""
        ordered = sorted(entities, key=lambda entity: entity.index)
        return dump_entities(ordered, component_filter=_is_persistable_component)

    ###############################################################################################################################################
    def serialize_context(self) -> ContextData:
        """将整个 Context 的核心导出为 name-keyed 的 ContextData（只含已注册组件）。"""
        return dump_context(self, component_filter=_is_persistable_component)

    ###############################################################################################################################################
    def restore_context(self, data: ContextData) -> Dict[str, Entity]:
        """从 name-keyed 的 ContextData 还原 Context 核心，并重建名称索引。"""
        restored = load_context(self, data, resolve_component_type)
        self._entity_name_index.update(restored)
        return restored

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
    def get_actors_in_stage(
        self, entity: Entity, matcher: Optional[Matcher] = None
    ) -> Set[Entity]:
        """获取指定场景上匹配 matcher 的 Actor 实体（未传 matcher 时返回全部 Actor）。"""

        stage_entity = self.resolve_stage_entity(entity)
        assert stage_entity is not None, f"entity = {entity}"

        # 补全 all_of 条件，确保其中包含 ActorComponent
        all_of = list(matcher.all_of) if matcher is not None and matcher.all_of else []

        # 确保 all_of 条件中包含 ActorComponent，以便只匹配 Actor 实体
        if ActorComponent not in all_of:
            all_of.append(ActorComponent)

        # 构建用于匹配 Actor 的 Matcher，确保包含 ActorComponent
        actor_matcher = Matcher(
            all_of=all_of,
            any_of=matcher.any_of if matcher is not None else None,
            none_of=matcher.none_of if matcher is not None else None,
        )

        # 直接在这里构建stage到actor的映射
        ret: Set[Entity] = set()

        # 获取所有候选的 Actor 实体，这些实体满足 actor_matcher 的条件
        candidate_entities: Set[Entity] = self.get_group(actor_matcher).entities

        # 以stage为key，actor为value
        for candidate_entity in candidate_entities:
            candidate_stage_entity = self.resolve_stage_entity(candidate_entity)
            assert (
                candidate_stage_entity is not None
            ), f"candidate_entity = {candidate_entity}"
            if candidate_stage_entity != stage_entity:
                # 不同的stage不算在内
                continue

            ret.add(candidate_entity)

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
        """判断 Actor 是否在副本场景中。"""
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
        actors_by_stage = self.get_actors_by_stage()

        for stage_entity, actor_entities in actors_by_stage.items():
            ret[stage_entity.name] = [
                actor_entity.name for actor_entity in actor_entities
            ]

        return ret

    ###############################################################################################################################################
