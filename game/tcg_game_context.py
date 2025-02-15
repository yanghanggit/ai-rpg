from entitas import Context, Entity, Matcher  # type: ignore
from typing import final, Optional, List, Set
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
from extended_systems.query_component_system import QueryComponentSystem
from agent.lang_serve_system import LangServeSystem
from chaos_engineering.chaos_engineering_system import IChaosEngineering


@final
class TCGGameContext(Context):

    ###############################################################################################################################################
    def __init__(
        self,
        langserve_system: LangServeSystem,
        query_component_system: QueryComponentSystem,
        chaos_engineering_system: IChaosEngineering,
    ) -> None:
        #
        super().__init__()
        self._game: Optional[BaseGame] = None

        # agent 系统
        self._langserve_system: LangServeSystem = langserve_system

        # （方便快速查找用）
        self._query_component_system: QueryComponentSystem = query_component_system

        # 混沌工程系统
        self._chaos_engineering_system: IChaosEngineering = chaos_engineering_system

    ###############################################################################################################################################
    @property
    def langserve_system(self) -> LangServeSystem:
        return self._langserve_system

    ###############################################################################################################################################
    @property
    def query_component_system(self) -> QueryComponentSystem:
        return self._query_component_system

    ###############################################################################################################################################
    @property
    def chaos_engineering_system(self) -> IChaosEngineering:
        return self._chaos_engineering_system

    ###############################################################################################################################################
    def make_snapshot(self) -> List[EntitySnapshot]:

        ret: List[EntitySnapshot] = []

        entities = self._entities
        for entity in entities:
            entity_snapshot = EntitySnapshot(components=[])
            for key, value in entity._components.items():
                entity_snapshot.components.append(
                    ComponentSnapshot(name=key.__name__, data=value._asdict())
                )
            ret.append(entity_snapshot)

        return ret

    ###############################################################################################################################################
    def restore_from_snapshot(self, entity_snapshots: List[EntitySnapshot]) -> None:

        for en_snapshot in entity_snapshots:

            entity = self.create_entity()

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
    def get_player_entities(self) -> Set[Entity]:
        entities: Set[Entity] = self.get_group(
            Matcher(all_of=[PlayerComponent, ActorComponent])
        ).entities
        return entities

    #############################################################################################################################
    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        comp_class = self._query_component_system.get_query_component_class(name)
        if comp_class is None:
            return None
        find_entities = self.get_group(Matcher(comp_class)).entities
        if len(find_entities) > 0:
            assert len(find_entities) == 1
            return next(iter(find_entities))
        return None

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
    def _retrieve_actors_on_stage(self, stage_name: str) -> Set[Entity]:
        # 测试！！！
        stage_tag_component = (
            self._query_component_system.get_stage_tag_component_class(stage_name)
        )
        entities = self.get_group(
            Matcher(all_of=[ActorComponent, stage_tag_component])
        ).entities
        return set(entities)

    #############################################################################################################################
    def retrieve_actors_on_stage(self, entity: Entity) -> Set[Entity]:
        stage_entity = self.safe_get_stage_entity(entity)
        if stage_entity is None:
            return set()
        stage_comp = stage_entity.get(StageComponent)
        return self._retrieve_actors_on_stage(stage_comp.name)

    #############################################################################################################################
    def retrieve_actor_names_on_stage(self, entity: Entity) -> Set[str]:
        actors = self.retrieve_actors_on_stage(entity)
        ret: Set[str] = set()
        for actor in actors:
            actor_comp = actor.get(ActorComponent)
            ret.add(actor_comp.name)
        return ret

    #############################################################################################################################
    def safe_get_stage_entity(self, entity: Entity) -> Optional[Entity]:
        if entity.has(StageComponent):
            return entity
        elif entity.has(ActorComponent):
            actor_comp = entity.get(ActorComponent)
            return self.get_stage_entity(actor_comp.current_stage)
        return None

    #############################################################################################################################
    def safe_get_entity_name(self, entity: Entity) -> str:
        if entity.has(ActorComponent):
            return entity.get(ActorComponent).name
        elif entity.has(StageComponent):
            return entity.get(StageComponent).name
        elif entity.has(WorldSystemComponent):
            return entity.get(WorldSystemComponent).name
        return ""

    #############################################################################################################################
    def get_entity_by_guid(self, guid: int) -> Optional[Entity]:

        for entity in self.get_group(Matcher(GUIDComponent)).entities:
            guid_comp = entity.get(GUIDComponent)
            if guid_comp.GUID == guid:
                return entity

        return None

    #############################################################################################################################
    # 更改场景的标记组件
    def update_stage_tag_component(
        self, entity: Entity, previous_stage_name: str, target_stage_name: str
    ) -> None:

        if not entity.has(ActorComponent):
            assert False, "实体不是Actor, 目前场景标记只给Actor"
            return

        # 查看一下，如果一样基本就是错误
        if previous_stage_name == target_stage_name:
            logger.error(f"stagename相同，无需修改: {previous_stage_name}")

        # 删除旧的
        previous_stage_tag_component_class = (
            self._query_component_system.get_stage_tag_component_class(
                previous_stage_name
            )
        )
        if previous_stage_tag_component_class is not None and entity.has(
            previous_stage_tag_component_class
        ):
            entity.remove(previous_stage_tag_component_class)

        # 添加新的
        target_stage_tag_component_class = (
            self._query_component_system.get_stage_tag_component_class(
                target_stage_name
            )
        )
        if target_stage_tag_component_class is not None and not entity.has(
            target_stage_tag_component_class
        ):
            entity.add(target_stage_tag_component_class, target_stage_name)
    #############################################################################################################################