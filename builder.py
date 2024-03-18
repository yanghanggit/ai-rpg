

from typing import Any, List, Optional

#
class NPCBuilder:

    def __init__(self) -> None:
        self.data: Optional[dict[str, Any]] = None

    def __str__(self) -> str:
        return f"NPCBuilder: {self.data}"

    def build(self, json_data: dict[str, Any]) -> None:
        self.data = json_data

class UniquePropBuilder:

    def __init__(self) -> None:
        self.data: Optional[dict[str, Any]] = None

    def __str__(self) -> str:
        return f"UniquePropBuilder: {self.data}"

    def build(self, json_data: dict[str, Any]) -> None:
        self.data = json_data

class StageEntryConditionsBuilder:

    def __init__(self) -> None:
        self.data: Optional[dict[str, Any]] = None

    def __str__(self) -> str:
        return f"StageEntryConditionBuilder: {self.data}"

    def build(self, json_data: dict[str, Any]) -> None:
        self.data = json_data

class StageExitConditionsBuilder:

    def __init__(self) -> None:
        self.data: Optional[dict[str, Any]] = None

    def __str__(self) -> str:
        return f"StageExitConditionBuilder: {self.data}"

    def build(self, json_data: dict[str, Any]) -> None:
        self.data = json_data

#
class StageBuilder:

    def __init__(self) -> None:
        self.data: Optional[dict[str, Any]] = None
        self.npc_builders: List[NPCBuilder] = []
        self.unique_prop_builders: List[UniquePropBuilder] = []
        self.entry_condition_builders: List[StageEntryConditionsBuilder] = []
        self.exit_condition_builders: List[StageExitConditionsBuilder] = []

    def __str__(self) -> str:
        return f"StageBuilder: {self.data}"

    def build(self, json_data: dict[str, Any]) -> None:
        self.data = json_data
        npcs = json_data.get("NPCs", [])  # 使用.get安全访问
        for npc in npcs:
            npc_builder = NPCBuilder()
            npc_builder.build(npc)
            self.npc_builders.append(npc_builder)

        unique_props = json_data.get("UniqueProps", [])
        for unique_prop in unique_props:
            unique_prop_builder = UniquePropBuilder()
            unique_prop_builder.build(unique_prop)
            self.unique_prop_builders.append(unique_prop_builder)
        
        stage_entry_conditions = json_data.get("EntryConditions", [])
        for stage_entry_condition in stage_entry_conditions:
            stage_entry_condition_builder = StageEntryConditionsBuilder()
            stage_entry_condition_builder.build(stage_entry_condition)
            self.entry_condition_builders.append(stage_entry_condition_builder)

        stage_exit_conditions = json_data.get("ExitConditions", [])
        for stage_exit_condition in stage_exit_conditions:
            stage_exit_condition_builder = StageExitConditionsBuilder()
            stage_exit_condition_builder.build(stage_exit_condition)
            self.exit_condition_builders.append(stage_exit_condition_builder)

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
    


   
