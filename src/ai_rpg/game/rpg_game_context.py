from enum import IntEnum, unique
from typing import Dict, List, Optional, Set, final, override
from loguru import logger
from ..entitas import Context, Entity, Matcher
from ..models import (
    COMPONENTS_REGISTRY,
    ActorComponent,
    AppearanceComponent,
    ComponentSerialization,
    DeathComponent,
    EntitySerialization,
    PlayerComponent,
    RuntimeComponent,
    StageComponent,
    WorldComponent,
    HomeComponent,
    DungeonComponent,
)

"""
少做事，
只做合ecs相关的事情，
这些事情大多数是“检索”，以及不影响状态的调用，例如组织场景与角色的映射。
有2件比较关键的事，存储与复位。
"""
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################


###############################################################################################################################################
@unique
@final
class InteractionValidationResult(IntEnum):
    SUCCESS = 0
    TARGET_NOT_FOUND = 1
    INITIATOR_NOT_IN_STAGE = 2
    DIFFERENT_STAGES = 3


###############################################################################################################################################
class RPGGameContext(Context):

    ###############################################################################################################################################
    def __init__(
        self,
    ) -> None:
        super().__init__()
        self._query_entities: Dict[str, Entity] = {}  # （方便快速查找用）

    ###############################################################################################################################################
    def __create_entity__(self, name: str) -> Entity:
        entity = super().create_entity()
        entity._name = str(name)
        self._query_entities[name] = entity
        return entity

    ###############################################################################################################################################
    @override
    def destroy_entity(self, entity: Entity) -> None:
        # logger.debug(f"destroy entity: {entity._name}")
        self._query_entities.pop(entity.name, None)
        return super().destroy_entity(entity)

    ###############################################################################################################################################
    def _serialize_entity(self, entity: Entity) -> EntitySerialization:
        entity_serialization = EntitySerialization(name=entity.name, components=[])

        for key, value in entity._components.items():
            if COMPONENTS_REGISTRY.get(key.__name__) is None:
                continue
            entity_serialization.components.append(
                ComponentSerialization(name=key.__name__, data=value.model_dump())
            )
        return entity_serialization

    ###############################################################################################################################################
    def serialize_entities(self, entities: Set[Entity]) -> List[EntitySerialization]:

        ret: List[EntitySerialization] = []

        entities_copy = list(entities)

        # 保证有顺序。防止set引起的顺序不一致。
        sort_actors = sorted(
            entities_copy,
            key=lambda entity: entity.get(RuntimeComponent).runtime_index,
        )

        for entity in sort_actors:
            entity_serialization = self._serialize_entity(entity)
            ret.append(entity_serialization)

        return ret

    ###############################################################################################################################################
    def deserialize_entities(
        self, entities_serialization: List[EntitySerialization]
    ) -> Set[Entity]:

        ret: Set[Entity] = set()

        # assert len(self._entities) == 0
        # if len(self._entities) > 0:
        #     return ret

        for entity_serialization in entities_serialization:

            assert (
                self.get_entity_by_name(entity_serialization.name) is None
            ), f"Entity with name already exists: {entity_serialization.name}"

            entity = self.__create_entity__(entity_serialization.name)
            ret.add(entity)  # 添加到返回的集合中

            for comp_serialization in entity_serialization.components:

                comp_class = COMPONENTS_REGISTRY.get(comp_serialization.name)
                assert comp_class is not None

                # 使用 Pydantic 的方式直接从字典创建实例
                restore_comp = comp_class(**comp_serialization.data)
                assert restore_comp is not None

                logger.debug(
                    f"comp_class = {comp_class.__name__}, comp = {restore_comp}"
                )
                entity.set(comp_class, restore_comp)

        return ret

    ###############################################################################################################################################
    def get_world_entity(self, world_name: str) -> Optional[Entity]:
        entity: Optional[Entity] = self.get_entity_by_name(world_name)
        if entity is not None and entity.has(WorldComponent):
            return entity
        return None

    ###############################################################################################################################################
    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        return self._query_entities.get(name, None)

    ###############################################################################################################################################
    def get_stage_entity(self, stage_name: str) -> Optional[Entity]:
        entity: Optional[Entity] = self.get_entity_by_name(stage_name)
        if entity is not None and entity.has(StageComponent):
            return entity
        return None

    ###############################################################################################################################################
    def get_actor_entity(self, actor_name: str) -> Optional[Entity]:
        entity: Optional[Entity] = self.get_entity_by_name(actor_name)
        if entity is not None and entity.has(ActorComponent):
            return entity
        return None

    ###############################################################################################################################################
    def safe_get_stage_entity(self, entity: Entity) -> Optional[Entity]:
        if entity.has(StageComponent):
            return entity
        elif entity.has(ActorComponent):
            actor_comp = entity.get(ActorComponent)
            return self.get_stage_entity(actor_comp.current_stage)
        return None

    ###############################################################################################################################################
    def get_entity_by_player_name(self, player_name: str) -> Optional[Entity]:
        player_entities = self.get_group(
            Matcher(
                all_of=[PlayerComponent],
            )
        ).entities

        assert len(player_entities) <= 1, "There should be at most one player entity."
        for player_entity in player_entities:
            player_comp = player_entity.get(PlayerComponent)
            if player_comp.player_name == player_name:
                return player_entity
        return None

    ###############################################################################################################################################
    def get_all_actors_on_stage(self, entity: Entity) -> Set[Entity]:

        stage_entity = self.safe_get_stage_entity(entity)
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
            actor_stage_entity = self.safe_get_stage_entity(actor_entity)
            assert actor_stage_entity is not None, f"actor_entity = {actor_entity}"
            if actor_stage_entity != stage_entity:
                # 不同的stage不算在内
                continue

            ret.add(actor_entity)

        return ret

    ###############################################################################################################################################
    def get_alive_actors_on_stage(self, entity: Entity) -> Set[Entity]:
        ret = self.get_all_actors_on_stage(entity)
        return {actor for actor in ret if not actor.has(DeathComponent)}

    ###############################################################################################################################################
    # 以actor的final_appearance.name为key，final_appearance.final_appearance为value
    def get_stage_actor_appearances(self, entity: Entity) -> Dict[str, str]:
        ret: Dict[str, str] = {}
        for actor in self.get_alive_actors_on_stage(entity):
            if actor.has(AppearanceComponent):
                final_appearance = actor.get(AppearanceComponent)
                ret.setdefault(final_appearance.name, final_appearance.appearance)
        return ret

    ###############################################################################################################################################
    def is_actor_at_home(self, actor_entity: Entity) -> bool:
        assert actor_entity.has(ActorComponent), "actor_entity must have ActorComponent"
        if not actor_entity.has(ActorComponent):
            return False

        stage_entity = self.safe_get_stage_entity(actor_entity)
        assert stage_entity is not None, "stage_entity is None"
        if stage_entity is None:
            return False

        if stage_entity.has(HomeComponent):
            assert not stage_entity.has(
                DungeonComponent
            ), "stage_entity has both HomeComponent and DungeonComponent!"

        return stage_entity.has(HomeComponent)

    ###############################################################################################################################################
    def is_actor_in_dungeon(self, actor_entity: Entity) -> bool:
        assert actor_entity.has(ActorComponent), "actor_entity must have ActorComponent"
        if not actor_entity.has(ActorComponent):
            return False

        stage_entity = self.safe_get_stage_entity(actor_entity)
        assert stage_entity is not None, "stage_entity is None"
        if stage_entity is None:
            return False

        if stage_entity.has(DungeonComponent):
            assert not stage_entity.has(
                HomeComponent
            ), "stage_entity has both DungeonComponent and HomeComponent!"

        return stage_entity.has(DungeonComponent)

    ###############################################################################################################################################
    def validate_interaction(
        self, initiator_entity: Entity, target_name: str
    ) -> InteractionValidationResult:

        actor_entity: Optional[Entity] = self.get_actor_entity(target_name)
        if actor_entity is None:
            return InteractionValidationResult.TARGET_NOT_FOUND

        current_stage_entity = self.safe_get_stage_entity(initiator_entity)
        if current_stage_entity is None:
            return InteractionValidationResult.INITIATOR_NOT_IN_STAGE

        target_stage_entity = self.safe_get_stage_entity(actor_entity)
        if target_stage_entity != current_stage_entity:
            return InteractionValidationResult.DIFFERENT_STAGES

        return InteractionValidationResult.SUCCESS

    ###############################################################################################################################################
    def get_stage_actor_distribution(
        self,
    ) -> Dict[Entity, List[Entity]]:

        ret: Dict[Entity, List[Entity]] = {}

        actor_entities: Set[Entity] = self.get_group(
            Matcher(all_of=[ActorComponent])
        ).entities

        # 以stage为key，actor为value
        for actor_entity in actor_entities:

            stage_entity = self.safe_get_stage_entity(actor_entity)
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
    def get_stage_actor_distribution_mapping(
        self,
    ) -> Dict[str, List[str]]:

        ret: Dict[str, List[str]] = {}
        mapping = self.get_stage_actor_distribution()

        for stage_entity, actor_entities in mapping.items():
            ret[stage_entity.name] = [
                actor_entity.name for actor_entity in actor_entities
            ]

        return ret

    ###############################################################################################################################################
