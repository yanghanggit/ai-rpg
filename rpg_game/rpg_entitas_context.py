from entitas import Entity, Matcher, Context  # type: ignore
from loguru import logger
from my_components.components import (
    WorldComponent,
    StageComponent,
    ActorComponent,
    PlayerComponent,
    AppearanceComponent,
    GUIDComponent,
    RoundEventsComponent,
)
from extended_systems.file_system import FileSystem
from extended_systems.code_name_component_system import CodeNameComponentSystem
from my_agent.lang_serve_agent_system import LangServeAgentSystem
from chaos_engineering.chaos_engineering_system import IChaosEngineering
from typing import Optional, Dict, Set, cast, Any
import gameplay_systems.public_builtin_prompt as public_builtin_prompt
from my_models.models_def import AgentEvent


class RPGEntitasContext(Context):

    #
    def __init__(
        self,
        file_system: FileSystem,
        langserve_agent_system: LangServeAgentSystem,
        codename_component_system: CodeNameComponentSystem,
        chaos_engineering_system: IChaosEngineering,
    ) -> None:

        #
        super().__init__()

        # 文件系统
        self._file_system: FileSystem = file_system

        # agent 系统
        self._langserve_agent_system: LangServeAgentSystem = langserve_agent_system

        # 代码名字组件系统（方便快速查找用）
        self._codename_component_system: CodeNameComponentSystem = (
            codename_component_system
        )

        # 混沌工程系统
        self._chaos_engineering_system: IChaosEngineering = chaos_engineering_system

        #
        self._game: Any = None

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
        comp_class = self._codename_component_system.get_code_name_component_class(name)
        if comp_class is None:
            return None
        find_entities = self.get_group(Matcher(comp_class)).entities
        if len(find_entities) > 0:
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

    def _get_actors_in_stage(self, stage_name: str) -> Set[Entity]:
        # 测试！！！
        stage_tag_component = (
            self._codename_component_system.get_stage_tag_component_class(stage_name)
        )
        entities = self.get_group(
            Matcher(all_of=[ActorComponent, stage_tag_component])
        ).entities
        return set(entities)

    #############################################################################################################################

    def get_actors_in_stage(self, entity: Entity) -> Set[Entity]:
        stage_entity = self.safe_get_stage_entity(entity)
        if stage_entity is None:
            return set()
        stage_comp = stage_entity.get(StageComponent)
        return self._get_actors_in_stage(stage_comp.name)

    #############################################################################################################################

    def get_actor_names_in_stage(self, entity: Entity) -> Set[str]:
        actors = self.get_actors_in_stage(entity)
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
    ##给一个实体添加记忆，尽量统一走这个方法, add_human_message_to_entity
    def safe_add_human_message_to_entity(
        self, entity: Entity, message_content: str
    ) -> bool:

        if message_content == "":
            logger.error("消息内容为空，无法添加记忆")
            return False

        name = self.safe_get_entity_name(entity)
        if name == "":
            logger.error("实体没有名字，无法添加记忆")
            return False

        self._langserve_agent_system.append_human_message_to_chat_history(
            name, message_content
        )
        return True

    #############################################################################################################################
    def safe_add_ai_message_to_entity(
        self, entity: Entity, message_content: str
    ) -> bool:

        if message_content == "":
            logger.error("消息内容为空，无法添加记忆")
            return False

        name = self.safe_get_entity_name(entity)
        if name == "":
            logger.error("实体没有名字，无法添加记忆")
            return False

        self._langserve_agent_system.append_ai_message_to_chat_history(
            name, message_content
        )
        return True

    #############################################################################################################################
    # 更改场景的标记组件
    def change_stage_tag_component(
        self, entity: Entity, from_stage_name: str, to_stage_name: str
    ) -> None:

        if not entity.has(ActorComponent):
            logger.error("实体不是Actor, 目前场景标记只给Actor")
            return

        # 查看一下，如果一样基本就是错误
        if from_stage_name == to_stage_name:
            logger.error(f"stagename相同，无需修改: {from_stage_name}")

        # 删除旧的
        from_stagetag_comp_class = (
            self._codename_component_system.get_stage_tag_component_class(
                from_stage_name
            )
        )
        if from_stagetag_comp_class is not None and entity.has(
            from_stagetag_comp_class
        ):
            entity.remove(from_stagetag_comp_class)

        # 添加新的
        to_stagetag_comp_class = (
            self._codename_component_system.get_stage_tag_component_class(to_stage_name)
        )
        if to_stagetag_comp_class is not None and not entity.has(
            to_stagetag_comp_class
        ):
            entity.add(to_stagetag_comp_class, to_stage_name)

    #############################################################################################################################
    # 获取场景内所有的角色的外观信息
    def get_appearance_in_stage(self, entity: Entity) -> Dict[str, str]:

        ret: Dict[str, str] = {}
        for actor in self.get_actors_in_stage(entity):
            if not actor.has(AppearanceComponent):
                continue

            appearance_comp = actor.get(AppearanceComponent)
            ret[appearance_comp.name] = str(appearance_comp.appearance)

        return ret

    #############################################################################################################################
    def get_entity_by_guid(self, guid: int) -> Optional[Entity]:

        for entity in self.get_group(Matcher(GUIDComponent)).entities:
            guid_comp = entity.get(GUIDComponent)
            if guid_comp.GUID == guid:
                return entity

        return None

    #############################################################################################################################
    def broadcast_event_in_stage(
        self,
        entity: Entity,
        agent_event: AgentEvent,
        exclude_entities: Set[Entity] = set(),
    ) -> None:

        stage_entity = self.safe_get_stage_entity(entity)
        if stage_entity is None:
            return

        need_broadcast_entities = self.get_actors_in_stage(stage_entity)
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
        self._notify_event_players(entities, agent_event)

    #############################################################################################################################
    def _notify_event(self, entities: Set[Entity], agent_event: AgentEvent) -> None:

        for entity in entities:

            safe_name = self.safe_get_entity_name(entity)
            replace_message = public_builtin_prompt.replace_you(
                agent_event.message_content, safe_name
            )

            #
            self._langserve_agent_system.append_human_message_to_chat_history(
                safe_name, replace_message
            )

            # 记录历史
            if entity.has(RoundEventsComponent):
                round_events_comp = entity.get(RoundEventsComponent)
                round_events_comp.events.append(replace_message)

    #############################################################################################################################
    def _notify_event_players(
        self, entities: Set[Entity], agent_event: AgentEvent
    ) -> None:

        if len(entities) == 0:
            return

        player_entities: Set[Entity] = set()
        for entity in entities:
            if entity.has(PlayerComponent):
                player_entities.add(entity)

        from rpg_game.rpg_game import RPGGame

        cast(RPGGame, self._game).add_message_to_players(player_entities, agent_event)

    #############################################################################################################################
