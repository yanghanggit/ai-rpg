from entitas import Context, Entity, Matcher  # type: ignore
from typing import final, Optional, List, Set, override, Dict
from game.base_game import BaseGame
from models.tcg_models import ComponentSnapshot, EntitySnapshot, WorldRoot
from components.components import (
    WorldSystemComponent,
    StageComponent,
    ActorComponent,
    PlayerComponent,
    GUIDComponent,
    COMPONENTS_REGISTRY,
)
from loguru import logger
from agent.lang_serve_system import LangServeSystem
from chaos_engineering.chaos_engineering_system import IChaosEngineering


@final
class TCGGameContext(Context):

    ###############################################################################################################################################
    def __init__(
        self,
        langserve_system: LangServeSystem,
        chaos_engineering_system: IChaosEngineering,
    ) -> None:
        #
        super().__init__()
        self._game: Optional[BaseGame] = None

        # agent 系统
        self._langserve_system: LangServeSystem = langserve_system

        # 混沌工程系统
        self._chaos_engineering_system: IChaosEngineering = chaos_engineering_system

        # （方便快速查找用）
        self._query_entities: Dict[str, Entity] = {}

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
    @property
    def langserve_system(self) -> LangServeSystem:
        return self._langserve_system

    ###############################################################################################################################################
    @property
    def chaos_engineering_system(self) -> IChaosEngineering:
        return self._chaos_engineering_system

    ###############################################################################################################################################
    def make_snapshot(self) -> List[EntitySnapshot]:

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
    def restore_from_snapshot(self, entity_snapshots: List[EntitySnapshot]) -> None:

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

    #############################################################################################################################
    def get_player_entity(self, player_name: str) -> Optional[Entity]:
        entities: Set[Entity] = self.get_group(
            Matcher(all_of=[PlayerComponent, ActorComponent])
        ).entities
        for entity in entities:
            player_comp = entity.get(PlayerComponent)
            if player_comp.name == player_name:
                return entity
        return None

    #############################################################################################################################
    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        return self._query_entities.get(name, None)

    #############################################################################################################################
    def get_stage_entity(self, stage_name: str) -> Optional[Entity]:
        entity: Optional[Entity] = self.get_entity_by_name(stage_name)
        if entity is not None and entity.has(StageComponent):
            return entity
        return None

    #############################################################################################################################
    def get_actor_entity(self, actor_name: str) -> Optional[Entity]:
        entity: Optional[Entity] = self.get_entity_by_name(actor_name)
        if entity is not None and entity.has(ActorComponent):
            return entity
        return None

    #############################################################################################################################
    def safe_get_stage_entity(self, entity: Entity) -> Optional[Entity]:
        if entity.has(StageComponent):
            return entity
        elif entity.has(ActorComponent):
            actor_comp = entity.get(ActorComponent)
            return self.get_stage_entity(actor_comp.current_stage)
        return None

    #############################################################################################################################
    def get_entity_by_guid(self, guid: int) -> Optional[Entity]:

        for entity in self.get_group(Matcher(GUIDComponent)).entities:
            guid_comp = entity.get(GUIDComponent)
            if guid_comp.GUID == guid:
                return entity

        return None

    #############################################################################################################################
