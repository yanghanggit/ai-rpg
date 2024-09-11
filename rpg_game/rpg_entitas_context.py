from entitas import Entity, Matcher, Context  # type: ignore
from loguru import logger
from gameplay_systems.components import (
    WorldComponent,
    StageComponent,
    ActorComponent,
    PlayerComponent,
    AppearanceComponent,
    GUIDComponent,
)
from extended_systems.file_system import FileSystem
from extended_systems.kick_off_message_system import KickOffMessageSystem
from extended_systems.code_name_component_system import CodeNameComponentSystem
from my_agent.lang_serve_agent_system import LangServeAgentSystem
from chaos_engineering.chaos_engineering_system import IChaosEngineering
from typing import Optional, Dict, List, Set, cast, Any
from extended_systems.guid_generator import GUIDGenerator
import gameplay_systems.cn_builtin_prompt as builtin_prompt
from player.player_proxy import PlayerProxy


class RPGEntitasContext(Context):

    #
    def __init__(
        self,
        file_system: FileSystem,
        kick_off_message_system: KickOffMessageSystem,
        langserve_agent_system: LangServeAgentSystem,
        codename_component_system: CodeNameComponentSystem,
        chaos_engineering_system: IChaosEngineering,
        guid_generator: GUIDGenerator,
    ) -> None:

        #
        super().__init__()

        # 文件系统
        self._file_system = file_system

        # 读取启动记忆系统
        self._kick_off_message_system = kick_off_message_system

        # agent 系统
        self._langserve_agent_system = langserve_agent_system

        # 代码名字组件系统（方便快速查找用）
        self._codename_component_system = codename_component_system

        # 混沌工程系统
        self._chaos_engineering_system = chaos_engineering_system

        # guid 生成器
        self._guid_generator = guid_generator

        # 临时收集会话的历史
        self._round_messages: Dict[str, List[str]] = {}

        #
        self._game: Any = None

        #
        assert self._file_system is not None, "self.file_system is None"
        assert self._kick_off_message_system is not None, "self.memory_system is None"
        assert (
            self._langserve_agent_system is not None
        ), "self.agent_connect_system is None"
        assert (
            self._codename_component_system is not None
        ), "self.code_name_component_system is None"
        assert (
            self._chaos_engineering_system is not None
        ), "self.chaos_engineering_system is None"

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
    def get_entity_by_name(self, name: str) -> Optional[Entity]:
        comp_class = self._codename_component_system.get_component_class_by_name(name)
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
            self._codename_component_system.get_stage_tag_component_class_by_name(
                stage_name
            )
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
            actor_comp = entity.get(ActorComponent)
            return str(actor_comp.name)
        elif entity.has(StageComponent):
            stage_comp = entity.get(StageComponent)
            return str(stage_comp.name)
        elif entity.has(WorldComponent):
            world_comp = entity.get(WorldComponent)
            return str(world_comp.name)
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

        self._langserve_agent_system.add_human_message_to_chat_history(
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

        self._langserve_agent_system.add_ai_message_to_chat_history(
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
            self._codename_component_system.get_stage_tag_component_class_by_name(
                from_stage_name
            )
        )
        if from_stagetag_comp_class is not None and entity.has(
            from_stagetag_comp_class
        ):
            entity.remove(from_stagetag_comp_class)

        # 添加新的
        to_stagetag_comp_class = (
            self._codename_component_system.get_stage_tag_component_class_by_name(
                to_stage_name
            )
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
            if cast(int, guid_comp.GUID) == guid:
                return entity

        return None

    #############################################################################################################################
    def broadcast_entities_in_stage(
        self,
        entity: Entity,
        message_content: str,
        exclude_entities: Set[Entity] = set(),
    ) -> None:
        stage_entity = self.safe_get_stage_entity(entity)
        if stage_entity is None:
            return

        notify_entities = self.get_actors_in_stage(stage_entity)
        notify_entities.add(stage_entity)

        if len(exclude_entities) > 0:
            notify_entities = notify_entities - exclude_entities

        self._broadcast_entities(notify_entities, message_content)

    #############################################################################################################################
    def broadcast_entities(
        self,
        entities: Set[Entity],
        message_content: str,
    ) -> None:

        # 可能做点啥。目前没想好todo
        ##.....

        ## 真正的实现。
        self._broadcast_entities(entities, message_content)

        ##
        self._broadcast_players(entities, message_content)

    #############################################################################################################################
    def _broadcast_players(self, entities: Set[Entity], message_content: str) -> None:

        if len(entities) == 0:
            return

        first_entity = next(iter(entities))
        player_entities_in_stage = self.get_players_in_stage(first_entity)

        player_proxies: Set[PlayerProxy] = set()
        for player_entity in player_entities_in_stage:
            player_proxy = self.get_player_proxy(player_entity)
            if player_proxy is None:
                continue
            player_proxies.add(player_proxy)

        for player_proxy in player_proxies:
            for entity in entities:
                safe_name = self.safe_get_entity_name(entity)
                replace_message = builtin_prompt.replace_you(
                    message_content, player_proxy._controlled_actor_name
                )
                if entity.has(ActorComponent):
                    player_proxy.add_actor_message(safe_name, replace_message)
                elif entity.has(StageComponent):
                    player_proxy.add_stage_message(safe_name, replace_message)
                else:
                    assert False, "不应该到这里"

    #############################################################################################################################
    def get_players_in_stage(self, stage_entity: Entity) -> Set[Entity]:

        ret: Set[Entity] = set()

        actor_entities_in_stage = self.get_actors_in_stage(stage_entity)
        for actor_entity in actor_entities_in_stage:
            if not actor_entity.has(PlayerComponent):
                continue
            ret.add(actor_entity)

        return ret

    #############################################################################################################################
    def get_player_proxy(self, player_entity: Entity) -> Optional[PlayerProxy]:
        if not player_entity.has(PlayerComponent):
            return None
        player_comp = player_entity.get(PlayerComponent)
        return self._get_player_proxy(player_comp.name)

    #############################################################################################################################
    def _get_player_proxy(self, player_name: str) -> Optional[PlayerProxy]:
        from rpg_game.rpg_game import RPGGame

        if self._game is None:
            return None
        return cast(RPGGame, self._game).get_player(player_name)

    #############################################################################################################################
    def _broadcast_entities(self, entities: Set[Entity], message_content: str) -> None:

        for entity in entities:

            safe_name = self.safe_get_entity_name(entity)
            replace_message = builtin_prompt.replace_you(message_content, safe_name)

            #
            self._langserve_agent_system.add_human_message_to_chat_history(
                safe_name, replace_message
            )

            # 记录历史
            self._round_messages.get(safe_name, []).append(replace_message)

            # 如果是player 就特殊处理 todo
            # if self._game is not None and entity.has(PlayerComponent):
            #     from rpg_game.rpg_game import RPGGame

            #     player_comp = entity.get(PlayerComponent)
            #     player_proxy = cast(RPGGame, self._game).get_player(player_comp.name)
            #     if player_proxy is not None:
            #         player_proxy.add_actor_message(safe_name, replace_message)

    #############################################################################################################################
    def get_round_messages(self, entity: Entity) -> List[str]:
        safe_name = self.safe_get_entity_name(entity)
        return self._round_messages.get(safe_name, [])


#############################################################################################################################
