from entitas import Entity, Matcher, Context  # type: ignore
from loguru import logger
from my_components.components import (
    WorldComponent,
    StageComponent,
    ActorComponent,
    PlayerComponent,
    FinalAppearanceComponent,
    GUIDComponent,
    RoundEventsRecordComponent,
)
from extended_systems.file_system import FileSystem
from extended_systems.query_component_system import QueryComponentSystem
from my_agent.lang_serve_agent_system import LangServeAgentSystem
from chaos_engineering.chaos_engineering_system import IChaosEngineering
from typing import Optional, Dict, Set
import gameplay_systems.prompt_utils as prompt_utils
from my_models.event_models import AgentEvent
from rpg_game.base_game import BaseGame
from my_agent.lang_serve_agent import LangServeAgent


class RPGEntitasContext(Context):

    #
    def __init__(
        self,
        file_system: FileSystem,
        langserve_agent_system: LangServeAgentSystem,
        query_component_system: QueryComponentSystem,
        chaos_engineering_system: IChaosEngineering,
    ) -> None:

        #
        super().__init__()

        # 文件系统
        self._file_system: FileSystem = file_system

        # agent 系统
        self._agent_system: LangServeAgentSystem = langserve_agent_system

        # 代码名字组件系统（方便快速查找用）
        self._query_component_system: QueryComponentSystem = query_component_system

        # 混沌工程系统
        self._chaos_engineering_system: IChaosEngineering = chaos_engineering_system

        # 游戏对象记录下
        self._game: Optional[BaseGame] = None

    #############################################################################################################################
    @property
    def file_system(self) -> FileSystem:
        return self._file_system

    #############################################################################################################################
    @property
    def agent_system(self) -> LangServeAgentSystem:
        return self._agent_system

    #############################################################################################################################
    @property
    def query_component_system(self) -> QueryComponentSystem:
        return self._query_component_system

    #############################################################################################################################
    @property
    def chaos_engineering_system(self) -> IChaosEngineering:
        return self._chaos_engineering_system

    #############################################################################################################################
    def get_world_entity(self, world_name: str) -> Optional[Entity]:
        entity: Optional[Entity] = self.get_entity_by_name(world_name)
        if entity is not None and entity.has(WorldComponent):
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
    def _retrieve_actors_in_stage(self, stage_name: str) -> Set[Entity]:
        # 测试！！！
        stage_tag_component = (
            self._query_component_system.get_stage_tag_component_class(stage_name)
        )
        entities = self.get_group(
            Matcher(all_of=[ActorComponent, stage_tag_component])
        ).entities
        return set(entities)

    #############################################################################################################################
    def retrieve_actors_in_stage(self, entity: Entity) -> Set[Entity]:
        stage_entity = self.safe_get_stage_entity(entity)
        if stage_entity is None:
            return set()
        stage_comp = stage_entity.get(StageComponent)
        return self._retrieve_actors_in_stage(stage_comp.name)

    #############################################################################################################################
    def retrieve_actor_names_in_stage(self, entity: Entity) -> Set[str]:
        actors = self.retrieve_actors_in_stage(entity)
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
        elif entity.has(WorldComponent):
            return entity.get(WorldComponent).name
        return ""

    #############################################################################################################################
    def safe_add_human_message(
        self, target_entity: Entity, message_content: str
    ) -> None:
        logger.warning(
            f"请检查调用这个函数的调用点，确定合理，safe_add_human_message_to_entity: {message_content}"
        )
        self.agent_system.append_human_message(
            self.safe_get_entity_name(target_entity), message_content
        )

    #############################################################################################################################
    def safe_add_ai_message(self, target_entity: Entity, message_content: str) -> None:
        logger.warning(
            f"请检查调用这个函数的调用点，确定合理，safe_add_ai_message_to_entity: {message_content}"
        )
        self.agent_system.append_ai_message(
            self.safe_get_entity_name(target_entity), message_content
        )

    #############################################################################################################################
    def discard_last_human_ai_conversation(self, entity: Entity) -> None:
        agent = self.safe_get_agent(entity)
        self.agent_system._discard_last_human_ai_conversation(agent.name)

    #############################################################################################################################
    # 更改场景的标记组件
    def update_stage_tag_component(
        self, entity: Entity, previous_stage_name: str, target_stage_name: str
    ) -> None:

        if not entity.has(ActorComponent):
            logger.error("实体不是Actor, 目前场景标记只给Actor")
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
    def retrieve_stage_actor_appearance(self, actor_entity: Entity) -> Dict[str, str]:

        ret: Dict[str, str] = {}
        for actor in self.retrieve_actors_in_stage(actor_entity):
            if not actor.has(FinalAppearanceComponent):
                continue

            appearance_comp = actor.get(FinalAppearanceComponent)
            ret[appearance_comp.name] = str(appearance_comp.final_appearance)

        return ret

    #############################################################################################################################
    def get_entity_by_guid(self, guid: int) -> Optional[Entity]:

        for entity in self.get_group(Matcher(GUIDComponent)).entities:
            guid_comp = entity.get(GUIDComponent)
            if guid_comp.GUID == guid:
                return entity

        return None

    #############################################################################################################################
    def broadcast_event(
        self,
        entity: Entity,
        agent_event: AgentEvent,
        exclude_entities: Set[Entity] = set(),
    ) -> None:

        stage_entity = self.safe_get_stage_entity(entity)
        assert stage_entity is not None, "stage is None, actor无所在场景是有问题的"
        if stage_entity is None:
            return

        need_broadcast_entities = self.retrieve_actors_in_stage(stage_entity)
        need_broadcast_entities.add(stage_entity)

        if len(exclude_entities) > 0:
            need_broadcast_entities = need_broadcast_entities - exclude_entities

        self.notify_event(need_broadcast_entities, agent_event)

    #############################################################################################################################
    def notify_event(
        self,
        entities: Set[Entity],
        agent_event: AgentEvent,
    ) -> None:

        self._notify_event(entities, agent_event)
        self._notify_event_to_players(entities, agent_event)

    #############################################################################################################################
    def _notify_event(self, entities: Set[Entity], agent_event: AgentEvent) -> None:

        for entity in entities:

            safe_name = self.safe_get_entity_name(entity)
            replace_message = prompt_utils.replace_you(agent_event.message, safe_name)

            self.agent_system.append_human_message(safe_name, replace_message)
            logger.info(f"{safe_name} ==> {replace_message}")

            if entity.has(RoundEventsRecordComponent):
                round_events_comp = entity.get(RoundEventsRecordComponent)
                round_events_comp.events.append(replace_message)

    #############################################################################################################################
    def _notify_event_to_players(
        self, entities: Set[Entity], agent_event: AgentEvent
    ) -> None:

        if len(entities) == 0:
            return

        player_proxy_names: Set[str] = set()
        for entity in entities:
            if entity.has(PlayerComponent):
                player_comp = entity.get(PlayerComponent)
                player_proxy_names.add(player_comp.name)

        if len(player_proxy_names) == 0:
            return

        assert self._game is not None
        self._game.send_event(player_proxy_names, agent_event)

    #############################################################################################################################
    def safe_get_agent(self, entity: Entity) -> LangServeAgent:
        safe_name = self.safe_get_entity_name(entity)
        agent = self.agent_system.get_agent(safe_name)
        assert agent is not None, f"无法找到agent: {safe_name}"
        if agent is None:
            return LangServeAgent.create_empty()
        return agent

    #############################################################################################################################
