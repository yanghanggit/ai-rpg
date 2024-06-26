from loguru import logger
from auxiliary.data_base_system import DataBaseSystem
from entitas import (Entity, # type: ignore
                    Matcher, 
                    Context)
from auxiliary.components import (WorldComponent, 
                        StageComponent, 
                        ActorComponent, 
                        PlayerComponent, 
                        AppearanceComponent)
from file_system.file_system import FileSystem
from auxiliary.kick_off_memory_system import KickOffMemorySystem
from typing import Optional
from auxiliary.lang_serve_agent_system import LangServeAgentSystem
from auxiliary.code_name_component_system import CodeNameComponentSystem
from auxiliary.chaos_engineering_system import IChaosEngineering
from typing import Optional, Dict, List, Set


class ExtendedContext(Context):
    #
    def __init__(self, 
                 filesystem: FileSystem, 
                 kick_off_memory_system: KickOffMemorySystem, 
                 agentconnectsys: LangServeAgentSystem, 
                 codenamecompsys: CodeNameComponentSystem,
                 databasesys: DataBaseSystem, 
                 chaossystem: IChaosEngineering) -> None:
        
        #
        super().__init__()
        
        #
        self.file_system = filesystem
        self.kick_off_memory_system = kick_off_memory_system
        self.agent_connect_system = agentconnectsys
        self.code_name_component_system = codenamecompsys
        self.data_base_system = databasesys
        self.chaos_engineering_system = chaossystem
        
        # 世界运行的回合数
        self.execute_count: int = 0
        
        #        
        assert self.file_system is not None, "self.file_system is None"
        assert self.kick_off_memory_system is not None, "self.memory_system is None"
        assert self.agent_connect_system is not None, "self.agent_connect_system is None"
        assert self.code_name_component_system is not None, "self.code_name_component_system is None"
        assert self.data_base_system is not None, "self.data_base_system is None"
        assert self.chaos_engineering_system is not None, "self.chaos_engineering_system is None"
############################################################################################################
    #世界基本就一个（或者及其少的数量），所以就遍历一下得了。
    def get_world_entity(self, worldname: str) -> Optional[Entity]:
        entity: Optional[Entity] = self.get_entity_by_code_name_component(worldname)
        if entity is not None and entity.has(WorldComponent):
            return entity
        return None
############################################################################################################
    #玩家基本就一个（或者及其少的数量），所以就遍历一下得了，注意是playername，比如yanghang。
    def get_player_entity(self, playername: str) -> Optional[Entity]:
        entities: Set[Entity] = self.get_group(Matcher(all_of=[PlayerComponent, ActorComponent])).entities
        for entity in entities:
            playercomp: PlayerComponent = entity.get(PlayerComponent)
            if playercomp.name == playername:
                return entity
        return None
############################################################################################################
    def get_entity_by_code_name_component(self, name: str) -> Optional[Entity]:
        compclass = self.code_name_component_system.get_component_class_by_name(name)
        if compclass is None:
            return None
        findstages: Set[Entity] = self.get_group(Matcher(compclass)).entities
        if len(findstages) > 0:
            return next(iter(findstages))
        return None
############################################################################################################
    def get_stage_entity(self, stagename: str) -> Optional[Entity]:
        entity: Optional[Entity] = self.get_entity_by_code_name_component(stagename)
        if entity is not None and entity.has(StageComponent):
            return entity
        return None
############################################################################################################
    def get_actor_entity(self, actorname: str) -> Optional[Entity]:
        entity: Optional[Entity] = self.get_entity_by_code_name_component(actorname)
        if entity is not None and entity.has(ActorComponent):
            return entity
        return None
############################################################################################################
    # 目标场景中的所有角色
    def actors_in_stage(self, stagename: str) -> List[Entity]:   
        # 测试！！！
        stage_tag_component = self.code_name_component_system.get_stage_tag_component_class_by_name(stagename)
        entities: Set[Entity] =  self.get_group(Matcher(all_of=[ActorComponent, stage_tag_component])).entities
        return list(entities)
############################################################################################################
    # actors_in_stage 的另外一个实现
    def actors_in_stage_(self, entity: Entity) -> List[Entity]: 
        stage_entity = self.safe_get_stage_entity(entity)
        if stage_entity is None:
            return []
        stagecomp: StageComponent = stage_entity.get(StageComponent)
        return self.actors_in_stage(stagecomp.name)
############################################################################################################
     # 直接从实体中获取场景实体，如果是Actor，就获取当前场景，如果是场景，就是自己
    def safe_get_stage_entity(self, entity: Entity) -> Optional[Entity]:
        if entity.has(StageComponent):
            # 我自己！！！
            return entity
        elif entity.has(ActorComponent):
            actor_comp: ActorComponent = entity.get(ActorComponent)
            return self.get_stage_entity(actor_comp.current_stage)
        logger.error("实体不是Actor或者Stage")
        return None
############################################################################################################
    # 特定的如下几种类型来获取名字
    def safe_get_entity_name(self, entity: Entity) -> str:
        if entity.has(ActorComponent):
            actor_comp: ActorComponent = entity.get(ActorComponent)
            return str(actor_comp.name)
        elif entity.has(StageComponent):
            stagecomp: StageComponent = entity.get(StageComponent)
            return str(stagecomp.name)
        elif entity.has(WorldComponent):
            worldcomp: WorldComponent = entity.get(WorldComponent)
            return str(worldcomp.name)
        logger.error("实体没有名字")
        return ""
############################################################################################################
    ##给一个实体添加记忆，尽量统一走这个方法, add_human_message_to_entity
    def safe_add_human_message_to_entity(self, entity: Entity, messagecontent: str) -> bool:
        if messagecontent == "":
            logger.error("消息内容为空，无法添加记忆")
            return False
        name = self.safe_get_entity_name(entity)
        if name == "":
            logger.error("实体没有名字，无法添加记忆")
            return False
        self.agent_connect_system.add_human_message_to_chat_history(name, messagecontent)
        return True
############################################################################################################
    # 更改场景的标记组件
    def change_stage_tag_component(self, entity: Entity, from_stagename: str, to_stagename: str) -> None:
        if not entity.has(ActorComponent):
            logger.error("实体不是Actor, 目前场景标记只给Actor")
            return
        
        # 查看一下，如果一样基本就是错误
        if from_stagename == to_stagename:
            logger.error(f"stagename相同，无需修改: {from_stagename}")

        # 删除旧的
        from_stagetag_comp_class = self.code_name_component_system.get_stage_tag_component_class_by_name(from_stagename)
        if from_stagetag_comp_class is not None and entity.has(from_stagetag_comp_class):
            entity.remove(from_stagetag_comp_class)

        # 添加新的
        to_stagetag_comp_class = self.code_name_component_system.get_stage_tag_component_class_by_name(to_stagename)
        if to_stagetag_comp_class is not None and not entity.has(to_stagetag_comp_class):
            entity.add(to_stagetag_comp_class, to_stagename)
############################################################################################################
    # 获取场景内所有的角色的外形信息
    def appearance_in_stage(self, entity: Entity) -> Dict[str, str]:
        #
        res: Dict[str, str] = {}
        stageentity = self.safe_get_stage_entity(entity)
        if stageentity is None:
            return res
        #
        safe_stage_name = self.safe_get_entity_name(stageentity)
        actors_int_stage: List[Entity] = self.actors_in_stage(safe_stage_name)
        for actor in actors_int_stage:
            if actor.has(AppearanceComponent):
                actor_comp: ActorComponent = actor.get(ActorComponent)
                appearance_comp: AppearanceComponent = actor.get(AppearanceComponent)
                res[actor_comp.name] = appearance_comp.appearance
            else:
                logger.error(f"{actor_comp.name}没有AppearanceComponent?!")

        return res
############################################################################################################

        
