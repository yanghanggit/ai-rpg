from loguru import logger
from entitas import (Entity, # type: ignore
                    Matcher, 
                    Context)
from auxiliary.components import (WorldComponent, 
                        StageComponent, 
                        NPCComponent, 
                        PlayerComponent)
from auxiliary.file_system import FileSystem
from auxiliary.memory_system import MemorySystem
from typing import Optional
from auxiliary.agent_connect_system import AgentConnectSystem
from auxiliary.code_name_component_system import CodeNameComponentSystem
from auxiliary.chaos_engineering_system import IChaosEngineering
from typing import List, Any, Optional


class ExtendedContext(Context):
    #
    def __init__(self, 
                 filesystem: FileSystem, 
                 memorysystem: MemorySystem, 
                 agentconnectsys: AgentConnectSystem, 
                 codenamecompsys: CodeNameComponentSystem, 
                 chaossystem: IChaosEngineering) -> None:
        
        #
        super().__init__()
        
        #
        self.file_system = filesystem
        self.memory_system = memorysystem
        self.agent_connect_system = agentconnectsys
        self.code_name_component_system = codenamecompsys
        self.chaos_engineering_system = chaossystem
        self.savedata = False
        #        
        assert self.file_system is not None, "self.file_system is None"
        assert self.memory_system is not None, "self.memory_system is None"
        assert self.agent_connect_system is not None, "self.agent_connect_system is None"
        assert self.code_name_component_system is not None, "self.code_name_component_system is None"
        assert self.chaos_engineering_system is not None, "self.chaos_engineering_system is None"
############################################################################################################
    #世界基本就一个（或者及其少的数量），所以就遍历一下得了。
    def getworld(self, worldname: str) -> Optional[Entity]:
        entities: set[Entity] = self.get_group(Matcher(WorldComponent)).entities
        for entity in entities:
            worldcomp: WorldComponent = entity.get(WorldComponent)
            if worldcomp.name == worldname:
                return entity
        return None
############################################################################################################
    #玩家基本就一个（或者及其少的数量），所以就遍历一下得了，注意是playername，比如yanghang。
    def getplayer(self, playername: str) -> Optional[Entity]:
        entities: set[Entity] = self.get_group(Matcher(all_of=[PlayerComponent, NPCComponent])).entities
        for entity in entities:
            playercomp: PlayerComponent = entity.get(PlayerComponent)
            if playercomp.name == playername:
                return entity
        return None
############################################################################################################
    def get_by_code_name_component(self, name: str) -> Optional[Entity]:
        compclass = self.code_name_component_system.get_component_class_by_name(name)
        if compclass is None:
            return None
        findstages: set[Entity] = self.get_group(Matcher(compclass)).entities
        if len(findstages) > 0:
            return next(iter(findstages))
        return None
############################################################################################################
    def getstage(self, stagename: str) -> Optional[Entity]:
        return self.get_by_code_name_component(stagename)
############################################################################################################
    def getnpc(self, npcname: str) -> Optional[Entity]:
        return self.get_by_code_name_component(npcname)
############################################################################################################
    def npcs_in_this_stage(self, stagename: str) -> list[Entity]:   
        # 测试！！！
        stage_tag_component = self.code_name_component_system.get_stage_tag_component_class_by_name(stagename)
        entities: set[Entity] =  self.get_group(Matcher(all_of=[NPCComponent, stage_tag_component])).entities
        return list(entities)
############################################################################################################
    def safe_get_stage_entity(self, entity: Entity) -> Optional[Entity]:
        if entity.has(StageComponent):
            # 我自己！！！
            return entity
        elif entity.has(NPCComponent):
            npccomp: NPCComponent = entity.get(NPCComponent)
            return self.getstage(npccomp.current_stage)
        #raise ValueError("实体不是NPC或者Stage")
        logger.error("实体不是NPC或者Stage")
        return None
############################################################################################################
    def safe_get_entity_name(self, entity: Entity) -> str:
        if entity.has(NPCComponent):
            npccomp: NPCComponent = entity.get(NPCComponent)
            return str(npccomp.name)
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
            logger.warning("消息内容为空，无法添加记忆")
            return False
        name = self.safe_get_entity_name(entity)
        if name == "":
            logger.error("实体没有名字，无法添加记忆")
            return False
        self.agent_connect_system.add_human_message_to_chat_history(name, messagecontent)
        return True
############################################################################################################
    def change_stage_tag_component(self, entity: Entity, from_stagename: str, to_stagename: str) -> None:
        if not entity.has(NPCComponent):
            logger.error("实体不是NPC, 目前场景标记只给NPC")
            return
        
        npccomp: NPCComponent = entity.get(NPCComponent)
        #logger.debug(f"change_stage_tag:{npccomp.name}: {from_stagename} -> {to_stagename}")

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
    def check_component_register(self, classname: str, actions_register: List[Any]) -> Any:
        for component in actions_register:
            if component.__name__ == classname:
                return component
        return None
############################################################################################################
    def check_dialogue_action(self, actionname: str, actionvalues: List[str], actions_register: List[Any]) -> bool:
        from auxiliary.dialogue_rule import parse_target_and_message

        if actionname not in [component.__name__ for component in actions_register]:
            # 不是一个对话类型
            return False
    
        for value in actionvalues:
            pair = parse_target_and_message(value)
            target: Optional[str] = pair[0]
            message: Optional[str] = pair[1]
            if target is None or message is None:
                logger.error(f"target is None: {value}")
                return False
        #可以过
        return True
############################################################################################################


        
