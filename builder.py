###
### 测试与LLM无关的代码，和一些尝试
###

from world import World
from stage import Stage
from npc import NPC
from typing import Any, List, Optional

#
class NPCBuilder:

    def __init__(self) -> None:
        self.data: Optional[dict[str, Any]] = None

    def __str__(self) -> str:
        return f"NPCBuilder: {self.data}"

    def build(self, json_data: dict[str, Any]) -> None:
        self.data = json_data
    
    def create_npc(self)-> NPC:
        if self.data is None:  # 检查data不为None
            raise ValueError("NPC data is not set")
        npc = NPC(self.data['name'])
        npc.url = self.data['url']
        return npc
#
class StageBuilder:

    def __init__(self) -> None:
        self.data: Optional[dict[str, Any]] = None
        self.npc_builders: List[NPCBuilder] = []

    def __str__(self) -> str:
        return f"StageBuilder: {self.data}"

    def build(self, json_data: dict[str, Any]) -> None:
        self.data = json_data
        npcs = json_data.get("NPCs", [])  # 使用.get安全访问
        for npc in npcs:
            npc_builder = NPCBuilder()
            npc_builder.build(npc)
            self.npc_builders.append(npc_builder)

    def create_stage(self)-> Stage:
        if self.data is None:  # 检查data不为None
            raise ValueError("Stage data is not set")
        stage = Stage(self.data['name'])
        stage.url = self.data['url']
        return stage  
#
class WorldBuilder:
    #
    def __init__(self) -> None:
        self.data: Optional[dict[str, Any]] = None
        self.stage_builders: List[StageBuilder] = []
        self.world: Optional[World] = None  

    def __str__(self) -> str:
        return f"WorldBuilder: {self.data}"       

    #
    def build(self, json_data: dict[str, Any]) -> None:
        world_data = json_data.get("World")
        if world_data:
            self.data = world_data
            stages_data = world_data.get("Stages", [])
            for stage in stages_data:
                stage_builder = StageBuilder()
                stage_builder.build(stage)
                self.stage_builders.append(stage_builder)
    #
    def create_world(self) -> World:
        if self.data is None:  # 检查data不为None
            raise ValueError("World data is not set")

        self.world = World(self.data['name'])
        self.world.url = self.data['url']    
        for stage_builder in self.stage_builders:
            stage = stage_builder.create_stage()
            self.world.add_stage(stage)
            for npc_builder in stage_builder.npc_builders:
                npc = npc_builder.create_npc()
                stage.add_actor(npc)
        return self.world

    


   
