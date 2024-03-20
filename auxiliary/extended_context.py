
from entitas import Entity, Matcher, Context, Group # type: ignore
from auxiliary.components import (WorldComponent, 
                        StageComponent, 
                        NPCComponent, 
                        PlayerComponent,
                        UniquePropComponent,
                        BackpackComponent,
                        SearchActionComponent)
from agents.tools.extract_md_content import wirte_content_into_md
#from auxiliary.actor_agent import ActorAgent
from auxiliary.actor_action import ActorAction
from auxiliary.file_system import FileSystem
from typing import Optional, cast
from actor_agent import ActorAgent

class ExtendedContext(Context):

    #
    def __init__(self) -> None:
        super().__init__()
        self.file_system = FileSystem()

    # def init_file_system(self) -> None:
    #     self.file_system = FileSystem()

    # def file_system(self) -> FileSystem:
    #     return self.file_system

    #
    def getworld(self) -> Optional[Entity]:
        for entity in self.get_group(Matcher(WorldComponent)).entities:
            return entity
        return None
    
    def getstage(self, name: str) -> Optional[Entity]:
        for entity in self.get_group(Matcher(StageComponent)).entities:
            comp = entity.get(StageComponent)
            if comp.name == name:
                return entity
        return None
    
    def getnpc(self, name: str) -> Optional[Entity]:
        for entity in self.get_group(Matcher(NPCComponent)).entities:
            comp = entity.get(NPCComponent)
            if comp.name == name:
                return entity
        return None
    
    def get_npcs_in_stage(self, stage_name: str) -> list[Entity]:   
        npcs: list[Entity] = []
        for entity in self.get_group(Matcher(NPCComponent)).entities:
            comp = entity.get(NPCComponent)
            if comp.current_stage == stage_name:
                npcs.append(entity)
        return npcs
    

    def getplayer(self) -> Optional[Entity]:
        for entity in self.get_group(Matcher(PlayerComponent)).entities:
            return entity
        return None
    

    def get_stagecomponent_by_uncertain_entity(self, entity: Entity) -> Optional[StageComponent]:
        if entity.has(StageComponent):
            return cast(StageComponent, entity.get(StageComponent)) 

        elif entity.has(NPCComponent):
            current_stage_name = entity.get(NPCComponent).current_stage
            for stage in self.get_group(Matcher(StageComponent)).entities:
                if stage.get(StageComponent).name == current_stage_name:
                    return cast(StageComponent, stage.get(StageComponent))
        return None
        
    def show_stages_log(self) -> dict[str, list[str]]:

        stagesentities = self.get_group(Matcher(StageComponent)).entities
        npcsentities = self.get_group(Matcher(NPCComponent)).entities
        map: dict[str, list[str]] = {}

        for entity in stagesentities:
            stagecomp = entity.get(StageComponent)
            ls = map.get(stagecomp.name, [])
            map[stagecomp.name] = ls

            for entity in npcsentities:
                npccomp = entity.get(NPCComponent)
                if npccomp.current_stage == stagecomp.name:
                    ls.append(npccomp.name)

        return map

    ##给一个实体添加记忆，尽量统一走这个方法
    def add_agent_memory(self, entity: Entity, memory: str) -> bool:
        if entity.has(NPCComponent):
            npccomp: NPCComponent = entity.get(NPCComponent)
            npcagent: ActorAgent = npccomp.agent
            npcagent.add_chat_history(memory)
            return True
        elif entity.has(StageComponent):
            stagecomp: StageComponent = entity.get(StageComponent)
            stageagent: ActorAgent = stagecomp.agent
            stageagent.add_chat_history(memory)
            return True
    
        raise ValueError("实体不是NPC或者Stage")
        return False
    

    ## 方便调用的存档方法
    def savearchive(self, archive: str, filename: str) -> None:
        wirte_content_into_md(archive, f"/savedData/{filename}.md")

    # 向Entity的背包中添加道具
    def put_unique_prop_into_backpack(self, entity: Entity, unique_prop_name: str) -> bool:
        if entity.has(BackpackComponent):
            npc_backpack_comp: BackpackComponent = entity.get(BackpackComponent)
            self.file_system.add_content_into_backpack(npc_backpack_comp, unique_prop_name)
            return True
        return False


    # 向Entity所在的场景中添加导演脚本
    def add_content_to_director_script_by_entity(self, entity: Entity, content: str) -> bool:
        npc_stage: Optional[StageComponent] = self.get_stagecomponent_by_uncertain_entity(entity)
        if npc_stage is None:
            return False
        npc_stage.directorscripts.append(content)
        return True

    # 获取Entity的ActorAction
    def get_search_action_by_entity(self, entity: Entity) -> Optional[ActorAction]:
        if entity.has(SearchActionComponent):
            npc_search_action_component: SearchActionComponent = entity.get(SearchActionComponent)
            return cast(ActorAction, npc_search_action_component.action)
        return None

    # 获取所有UniqueProps的名字
    def get_all_unique_props_names(self) -> set[str]:
        unique_props_group: Group = self.get_group(Matcher(UniquePropComponent))
        unique_props_entities = unique_props_group.entities

        unique_props_names: set[str] = set()
        for entity in unique_props_entities:
            unique_props_names.add(entity.get(UniquePropComponent).name)
        
        return unique_props_names
    
    # 根据Prop的名字获取Entity
    def get_unique_prop_entity_by_name(self, name: str) -> Optional[Entity]:
        for entity in self.get_group(Matcher(UniquePropComponent)).entities:
            if entity.get(UniquePropComponent).name == name:
                return entity
        return None
    