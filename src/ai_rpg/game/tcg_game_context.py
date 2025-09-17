from dataclasses import dataclass
import re
from typing import Dict, List, Optional, Set, override

from loguru import logger

from ..entitas import Context, Entity, Matcher
from ..models import (
    COMPONENTS_REGISTRY,
    ActorComponent,
    AppearanceComponent,
    ComponentSnapshot,
    DeathComponent,
    EntitySnapshot,
    PlayerComponent,
    RuntimeComponent,
    StageComponent,
    WorldSystemComponent,
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


# @dataclass
# class ActorFilterSettings:
#     filter_dead_actors: bool = True


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
        # logger.debug(f"destroy entity: {entity._name}")
        self._query_entities.pop(entity._name, None)
        return super().destroy_entity(entity)

    ###############################################################################################################################################
    def create_entity_snapshot(self, entity: Entity) -> EntitySnapshot:
        entity_snapshot = EntitySnapshot(name=entity._name, components=[])

        for key, value in entity._components.items():
            if COMPONENTS_REGISTRY.get(key.__name__) is None:
                continue
            entity_snapshot.components.append(
                ComponentSnapshot(name=key.__name__, data=value.model_dump())
            )
        return entity_snapshot

    ###############################################################################################################################################
    def make_entities_snapshot(self) -> List[EntitySnapshot]:

        ret: List[EntitySnapshot] = []

        entities_copy = self._entities.copy()

        # 保证有顺序。防止set引起的顺序不一致。
        sort_actors = sorted(
            entities_copy,
            key=lambda entity: entity.get(RuntimeComponent).runtime_index,
        )

        for entity in sort_actors:
            entity_snapshot = self.create_entity_snapshot(entity)
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

                # 使用 Pydantic 的方式直接从字典创建实例
                restore_comp = comp_class(**comp_snapshot.data)
                assert restore_comp is not None

                logger.debug(
                    f"comp_class = {comp_class.__name__}, comp = {restore_comp}"
                )
                entity.set(comp_class, restore_comp)

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
    def get_entity_by_runtime_index(self, runtime_index: int) -> Optional[Entity]:

        for entity in self.get_group(Matcher(RuntimeComponent)).entities:
            guid_comp = entity.get(RuntimeComponent)
            if guid_comp.runtime_index == runtime_index:
                return entity

        return None

    ###############################################################################################################################################
    def get_entity_by_player_name(self, player_name: str) -> Optional[Entity]:
        player_entities = self.get_group(
            Matcher(
                all_of=[PlayerComponent],
            )
        ).entities
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
