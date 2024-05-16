from typing import Optional
from auxiliary.base_data import NPCData, PropData, StageData

class DataBaseSystem:

    def __init__(self, description: str) -> None:
        self.description = description
        self.npcs: dict[str, NPCData] = {}
        self.stages: dict[str, StageData] = {}
        self.props: dict[str, PropData] = {}

    def add_npc(self, npcname: str, npc: NPCData) -> None:
        self.npcs.setdefault(npcname, npc)

    def get_npc(self, npcname: str) -> Optional[NPCData]:
        return self.npcs.get(npcname, None)

    def add_stage(self, stagename: str, stage: StageData) -> None:
        self.stages.setdefault(stagename, stage)
    
    def get_stage(self, stagename: str) -> Optional[StageData]:
        return self.stages.get(stagename, None)
    
    def add_prop(self, propname: str, prop: PropData) -> None:
        self.props.setdefault(propname, prop)

    def get_prop(self, propname: str) -> Optional[PropData]:
        return self.props.get(propname, None)