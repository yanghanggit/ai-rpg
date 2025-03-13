from entitas import Context, Entity, Matcher  # type: ignore
from typing import Optional, List, Set, override, Dict
from tcg_models.v_0_0_1 import ComponentSnapshot, EntitySnapshot
from components.components import (
    WorldSystemComponent,
    StageComponent,
    ActorComponent,
    GUIDComponent,
    HeroActorFlagComponent,
    FinalAppearanceComponent,
)

from components.registry import COMPONENTS_REGISTRY
from loguru import logger

"""
少做事，
只做合ecs相关的事情，
这些事情大多数是“检索”，以及不影响状态的调用，例如组织场景与角色的映射。
有2件比较关键的事，存储与复位。
"""


class TCGGameContext(Context):

    ###############################################################################################################################################
    def __init__(
        self,
    ) -> None:
        super().__init__()
        self._query_entities: Dict[str, Entity] = {}  # （方便快速查找用）

    ###############################################################################################################################################
    def __create_entity__(self, name: str) -> Entity:
        entity = super().create_entity()
        entity._name = name
        self._query_entities[name] = entity
        return entity

    ###############################################################################################################################################
    @override
    def destroy_entity(self, entity: Entity) -> None:
        self._query_entities.pop(entity._name, None)
        return super().destroy_entity(entity)

    ###############################################################################################################################################
    def make_entities_snapshot(self) -> List[EntitySnapshot]:

        ret: List[EntitySnapshot] = []

        entities = self._entities
        for entity in entities:
            entity_snapshot = EntitySnapshot(name=entity._name, components=[])
            for key, value in entity._components.items():

                if COMPONENTS_REGISTRY.get(key.__name__) is None:
                    continue

                entity_snapshot.components.append(
                    ComponentSnapshot(name=key.__name__, data=value._asdict())
                )
            ret.append(entity_snapshot)

        return ret

    ###############################################################################################################################################
    def restore_entities_from_snapshot(
        self, entity_snapshots: List[EntitySnapshot]
    ) -> None:

        assert len(self._entities) == 0
        if len(self._entities) > 0:
            return

        for en_snapshot in entity_snapshots:

            entity = self.__create_entity__(en_snapshot.name)

            for comp_snapshot in en_snapshot.components:

                comp_class = COMPONENTS_REGISTRY.get(comp_snapshot.name)
                assert comp_class is not None

                restore_comp = comp_class(**comp_snapshot.data)
                assert restore_comp is not None

                logger.info(
                    f"comp_class = {comp_class.__name__}, comp = {restore_comp}"
                )
                entity.insert(comp_class, restore_comp)

    ###############################################################################################################################################
    def get_world_entity(self, world_name: str) -> Optional[Entity]:
        entity: Optional[Entity] = self.get_entity_by_name(world_name)
        if entity is not None and entity.has(WorldSystemComponent):
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
    def get_entity_by_guid(self, guid: int) -> Optional[Entity]:

        for entity in self.get_group(Matcher(GUIDComponent)).entities:
            guid_comp = entity.get(GUIDComponent)
            if guid_comp.GUID == guid:
                return entity

        return None

    ###############################################################################################################################################
    def retrieve_stage_actor_mapping(self) -> Dict[Entity, Set[Entity]]:

        ret: Dict[Entity, Set[Entity]] = {}

        actor_entities: Set[Entity] = self.get_group(
            Matcher(all_of=[ActorComponent])
        ).entities

        # 以stage为key，actor为value
        for actor_entity in actor_entities:

            stage_entity = self.safe_get_stage_entity(actor_entity)
            assert stage_entity is not None
            if stage_entity is None:
                continue
            ret.setdefault(stage_entity, set()).add(actor_entity)

        # 补一下没有actor的stage
        stage_entities: Set[Entity] = self.get_group(
            Matcher(all_of=[StageComponent])
        ).entities
        for stage_entity in stage_entities:
            if stage_entity not in ret:
                ret.setdefault(stage_entity, set())

        return ret

    ###############################################################################################################################################
    def retrieve_actors_on_stage(self, entity: Entity) -> Set[Entity]:
        stage_entity = self.safe_get_stage_entity(entity)
        if stage_entity is None:
            return set()

        ret: Set[Entity] = set()

        actor_entities: Set[Entity] = self.get_group(
            Matcher(all_of=[ActorComponent])
        ).entities

        for actor_entity in actor_entities:
            if (
                actor_entity.get(ActorComponent).current_stage
                == stage_entity.get(StageComponent).name
            ):
                ret.add(actor_entity)

        return ret

    ###############################################################################################################################################
    # 以actor的final_appearance.name为key，final_appearance.final_appearance为value
    def retrieve_actor_appearance_on_stage_mapping(
        self, entity: Entity
    ) -> Dict[str, str]:
        ret: Dict[str, str] = {}
        for actor in self.retrieve_actors_on_stage(entity):
            if actor.has(FinalAppearanceComponent):
                final_appearance = actor.get(FinalAppearanceComponent)
                ret.setdefault(final_appearance.name, final_appearance.final_appearance)
        return ret

    ###############################################################################################################################################
    def retrieve_all_hero_entities(self) -> Set[Entity]:
        return self.get_group(
            Matcher(
                all_of=[
                    ActorComponent,
                    HeroActorFlagComponent,
                ],
            )
        ).entities

    ###############################################################################################################################################
