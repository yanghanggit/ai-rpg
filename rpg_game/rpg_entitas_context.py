from entitas import (Entity, Matcher, Context)# type: ignore   
from loguru import logger
from ecs_systems.components import (WorldComponent, StageComponent, ActorComponent, PlayerComponent, AppearanceComponent, GUIDComponent)
from file_system.file_system import FileSystem
from extended_systems.kick_off_message_system import KickOffMessageSystem
from extended_systems.code_name_component_system import CodeNameComponentSystem
from my_agent.lang_serve_agent_system import LangServeAgentSystem
from chaos_engineering.chaos_engineering_system import IChaosEngineering
from typing import Optional, Dict, List, Set
from extended_systems.guid_generator import GUIDGenerator

class RPGEntitasContext(Context):

    """
    对 entitas 的 Context 进行扩展，增加了一些常用的方法。
    """

    #
    def __init__(self, 
                 file_system: FileSystem, 
                 kick_off_message_system: KickOffMessageSystem, 
                 langserve_agent_system: LangServeAgentSystem, 
                 codename_component_system: CodeNameComponentSystem,
                 chaos_engineering_system: IChaosEngineering,
                 guid_generator: GUIDGenerator) -> None:
        
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
        
        # 世界运行的回合数
        self._execute_count: int = 0

        #        
        assert self._file_system is not None, "self.file_system is None"
        assert self._kick_off_message_system is not None, "self.memory_system is None"
        assert self._langserve_agent_system is not None, "self.agent_connect_system is None"
        assert self._codename_component_system is not None, "self.code_name_component_system is None"
        assert self._chaos_engineering_system is not None, "self.chaos_engineering_system is None"
#############################################################################################################################
    #世界基本就一个（或者及其少的数量），所以就遍历一下得了。
    def get_world_entity(self, worldname: str) -> Optional[Entity]:
        entity: Optional[Entity] = self.get_entity_by_codename_component(worldname)
        if entity is not None and entity.has(WorldComponent):
            return entity
        return None
#############################################################################################################################
    # 通过玩家名字来获得actor。
    def get_player_entity(self, player_name: str) -> Optional[Entity]:
        entities: Set[Entity] = self.get_group(Matcher(all_of=[PlayerComponent, ActorComponent])).entities
        for entity in entities:
            player_comp: PlayerComponent = entity.get(PlayerComponent)
            if player_comp.name == player_name:
                return entity
        return None
#############################################################################################################################
    def get_entity_by_codename_component(self, name: str) -> Optional[Entity]:
        compclass = self._codename_component_system.get_component_class_by_name(name)
        if compclass is None:
            return None
        find_stages: Set[Entity] = self.get_group(Matcher(compclass)).entities
        if len(find_stages) > 0:
            return next(iter(find_stages))
        return None
#############################################################################################################################
    def get_stage_entity(self, stage_name: str) -> Optional[Entity]:
        entity: Optional[Entity] = self.get_entity_by_codename_component(stage_name)
        if entity is not None and entity.has(StageComponent):
            return entity
        return None
#############################################################################################################################
    def get_actor_entity(self, actor_name: str) -> Optional[Entity]:
        entity: Optional[Entity] = self.get_entity_by_codename_component(actor_name)
        if entity is not None and entity.has(ActorComponent):
            return entity
        return None
#############################################################################################################################
    # 目标场景中的所有角色
    def actors_in_stage(self, stage_name: str) -> List[Entity]:   
        # 测试！！！
        stage_tag_component = self._codename_component_system.get_stage_tag_component_class_by_name(stage_name)
        entities: Set[Entity] =  self.get_group(Matcher(all_of=[ActorComponent, stage_tag_component])).entities
        return list(entities)
#############################################################################################################################
    # actors_in_stage 的另外一个实现
    def actors_in_stage_(self, entity: Entity) -> List[Entity]: 
        stage_entity = self.safe_get_stage_entity(entity)
        if stage_entity is None:
            return []
        stage_comp = stage_entity.get(StageComponent)
        return self.actors_in_stage(stage_comp.name)
#############################################################################################################################
     # 直接从实体中获取场景实体，如果是Actor，就获取当前场景，如果是场景，就是自己
    def safe_get_stage_entity(self, entity: Entity) -> Optional[Entity]:
        if entity.has(StageComponent):
            return entity 
        elif entity.has(ActorComponent):
            actor_comp = entity.get(ActorComponent)
            return self.get_stage_entity(actor_comp.current_stage)
        return None
#############################################################################################################################
    # 特定的如下几种类型来获取名字
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
    def safe_add_human_message_to_entity(self, entity: Entity, message_content: str) -> bool:
        
        if message_content == "":
            logger.error("消息内容为空，无法添加记忆")
            return False
        
        name = self.safe_get_entity_name(entity)
        if name == "":
            logger.error("实体没有名字，无法添加记忆")
            return False
        
        self._langserve_agent_system.add_human_message_to_chat_history(name, message_content)
        return True
#############################################################################################################################
    # 更改场景的标记组件
    def change_stage_tag_component(self, entity: Entity, from_stage_name: str, to_stage_name: str) -> None:

        if not entity.has(ActorComponent):
            logger.error("实体不是Actor, 目前场景标记只给Actor")
            return
        
        # 查看一下，如果一样基本就是错误
        if from_stage_name == to_stage_name:
            logger.error(f"stagename相同，无需修改: {from_stage_name}")

        # 删除旧的
        from_stagetag_comp_class = self._codename_component_system.get_stage_tag_component_class_by_name(from_stage_name)
        if from_stagetag_comp_class is not None and entity.has(from_stagetag_comp_class):
            entity.remove(from_stagetag_comp_class)

        # 添加新的
        to_stagetag_comp_class = self._codename_component_system.get_stage_tag_component_class_by_name(to_stage_name)
        if to_stagetag_comp_class is not None and not entity.has(to_stagetag_comp_class):
            entity.add(to_stagetag_comp_class, to_stage_name)
#############################################################################################################################
    # 获取场景内所有的角色的外观信息
    def appearance_in_stage(self, entity: Entity) -> Dict[str, str]:
        
        ret: Dict[str, str] = {}
        stage_entity = self.safe_get_stage_entity(entity)
        if stage_entity is None:
            return ret
        
        safe_stage_name = self.safe_get_entity_name(stage_entity)
        actors_int_stage: List[Entity] = self.actors_in_stage(safe_stage_name)
        for actor in actors_int_stage:
            if actor.has(AppearanceComponent):
                actor_comp = actor.get(ActorComponent)
                appearance_comp = actor.get(AppearanceComponent)
                ret[actor_comp.name] = str(appearance_comp.appearance)
            else:
                logger.error(f"{actor_comp.name}没有AppearanceComponent?!")

        return ret
#############################################################################################################################
    def get_entity_by_guid(self, guid: int) -> Optional[Entity]:
        entities = self.get_group(Matcher(GUIDComponent)).entities
        for entity in entities:
            guid_comp = entity.get(GUIDComponent)
            if guid_comp.GUID == guid:
                return entity
        return None
#############################################################################################################################
        
