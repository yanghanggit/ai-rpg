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
from loguru import logger

class ExtendedContext(Context):
    #
    def __init__(self) -> None:
        super().__init__()
        self.file_system = FileSystem("file_system， Because it involves IO operations, an independent system is more convenient.")
        self.memory_system = MemorySystem("memorey_system， Because it involves IO operations, an independent system is more convenient.")
        self.agent_connect_system = AgentConnectSystem("agent_connect_system， Because it involves net operations, an independent system is more convenient.")
        self.code_name_component_system = CodeNameComponentSystem("Build components by codename for special purposes")
    #
    def get1world(self) -> Optional[Entity]:
        for entity in self.get_group(Matcher(WorldComponent)).entities:
            return entity
        return None
    #
    def get1player(self) -> Optional[Entity]:
        for entity in self.get_group(Matcher(PlayerComponent)).entities:
            return entity
        return None
    
    #yh add 特殊的方法
    def get_by_code_name_component(self, name: str) -> Optional[Entity]:
        compclass = self.code_name_component_system.get_component_class_by_name(name)
        if compclass is None:
            return None
        findstages: set[Entity] = self.get_group(Matcher(compclass)).entities
        if len(findstages) > 0:
            return next(iter(findstages))
        return None
    
    #
    def getstage(self, name: str) -> Optional[Entity]:
        return self.get_by_code_name_component(name)
    
    #
    def getnpc(self, name: str) -> Optional[Entity]:
        return self.get_by_code_name_component(name)
    
    #
    def getentity(self, name: str) -> Optional[Entity]:
        return self.get_by_code_name_component(name)
    
    def npcs_in_this_stage(self, stage_name: str) -> list[Entity]:   
        # 测试！！！
        stage_tag_component = self.code_name_component_system.get_stage_tag_component_class_by_name(stage_name)
        entities: set[Entity] =  self.get_group(Matcher(all_of=[NPCComponent, stage_tag_component])).entities
        return list(entities)

    def get_stage_entity_by_uncertain_entity(self, entity: Entity) -> Optional[Entity]:
        if entity.has(StageComponent):
            # 我自己！！！
            return entity
        elif entity.has(NPCComponent):
            npccomp: NPCComponent = entity.get(NPCComponent)
            return self.getstage(npccomp.current_stage)
        raise ValueError("实体不是NPC或者Stage")
        return None

    ##给一个实体添加记忆，尽量统一走这个方法
    def add_agent_memory(self, entity: Entity, memory: str) -> bool:
        agent_connect_system = self.agent_connect_system
        if entity.has(NPCComponent):
            npccomp: NPCComponent = entity.get(NPCComponent)
            agent_connect_system.add_chat_history(npccomp.name, memory)
            return True
        elif entity.has(StageComponent):
            stagecomp: StageComponent = entity.get(StageComponent)
            agent_connect_system.add_chat_history(stagecomp.name, memory)
            return True
        raise ValueError("实体不是NPC或者Stage")
        return False

    # 向Entity所在的场景中添加导演脚本
    def legacy_add_content_to_director_script_by_entity(self, entity: Entity, content: str) -> bool:
        stageentity = self.get_stage_entity_by_uncertain_entity(entity)
        if stageentity is None:
            return False
        stagecomp: StageComponent = stageentity.get(StageComponent)
        stagecomp.directorscripts.append(content)
        return True
    
    #
    def change_stage_tag_component(self, entity: Entity, from_stagename: str, to_stagename: str) -> None:
        if not entity.has(NPCComponent):
            raise ValueError("实体不是NPC, 目前场景标记只给NPC!")
        
        npccomp: NPCComponent = entity.get(NPCComponent)
        logger.warning(f"change_stage_tag:{npccomp.name}: {from_stagename} -> {to_stagename}")
        if from_stagename == to_stagename:
            logger.error(f"stagename相同，无需修改: {from_stagename}")

        from_stagetag_comp_class = self.code_name_component_system.get_stage_tag_component_class_by_name(from_stagename)
        if from_stagetag_comp_class is not None and entity.has(from_stagetag_comp_class):
            entity.remove(from_stagetag_comp_class)

        to_stagetag_comp_class = self.code_name_component_system.get_stage_tag_component_class_by_name(to_stagename)
        if to_stagetag_comp_class is None:
            logger.error(f"stagetag component not found: {to_stagename}")
            return
        
        if not entity.has(to_stagetag_comp_class):
             entity.add(to_stagetag_comp_class, to_stagename)

        
       