

from typing import Any, List, Optional

#
class NPCBuilder:

    def __init__(self) -> None:
        self.data: Optional[dict[str, Any]] = None

    def __str__(self) -> str:
        return f"NPCBuilder: {self.data}"

    def build(self, json_data: dict[str, Any]) -> None:
        self.data = json_data
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
#
class WorldBuilder:
    #
    def __init__(self) -> None:
        self.data: Optional[dict[str, Any]] = None
        self.stage_builders: List[StageBuilder] = []

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
    


   
