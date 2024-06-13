from typing import Optional
from auxiliary.base_data import ActorData, PropData, StageData, WorldSystemData

class DataBaseSystem:

    def __init__(self, description: str) -> None:
        self.description = description
        self.actors: dict[str, ActorData] = {}
        self.stages: dict[str, StageData] = {}
        self.props: dict[str, PropData] = {}
        self.world_systems: dict[str, WorldSystemData] = {}

    def add_actor(self, actorname: str, actordata: ActorData) -> None:
        self.actors.setdefault(actorname, actordata)

    def get_actor(self, actorname: str) -> Optional[ActorData]:
        return self.actors.get(actorname, None)

    def add_stage(self, stagename: str, stage: StageData) -> None:
        self.stages.setdefault(stagename, stage)
    
    def get_stage(self, stagename: str) -> Optional[StageData]:
        return self.stages.get(stagename, None)
    
    def add_prop(self, propname: str, prop: PropData) -> None:
        self.props.setdefault(propname, prop)

    def get_prop(self, propname: str) -> Optional[PropData]:
        return self.props.get(propname, None)
    
    def add_world_system(self, worldname: str, world: WorldSystemData) -> None:
        self.world_systems.setdefault(worldname, world)

    def get_world_system(self, worldname: str) -> Optional[WorldSystemData]:
        return self.world_systems.get(worldname, None)