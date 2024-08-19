from typing import Optional, Dict
from build_game.data_model import (
    DataBaseSystemModel,
    ActorModel,
    PropModel,
    StageModel,
    WorldSystemModel,
)


class DataBaseSystem:
    """
    将所有的数据存储在这里，以便于在游戏中使用。
    """

    def __init__(self, model: Optional[DataBaseSystemModel]) -> None:

        self._model: Optional[DataBaseSystemModel] = model
        assert self._model is not None

        self._actors: Dict[str, ActorModel] = {}
        self._stages: Dict[str, StageModel] = {}
        self._props: Dict[str, PropModel] = {}
        self._world_systems: Dict[str, WorldSystemModel] = {}

        self.make_dict()

    ###############################################################################################################################################
    def make_dict(self) -> None:

        assert self._model is not None
        assert self._model.actors is not None
        assert self._model.stages is not None
        assert self._model.props is not None
        assert self._model.world_systems is not None

        self._actors.clear()
        for actor in self._model.actors:
            self._actors.setdefault(actor.name, actor)

        self._stages.clear()
        for stage in self._model.stages:
            self._stages.setdefault(stage.name, stage)

        self._props.clear()
        for prop in self._model.props:
            self._props.setdefault(prop.name, prop)

        self._world_systems.clear()
        for world_system in self._model.world_systems:
            self._world_systems.setdefault(world_system.name, world_system)

    ###############################################################################################################################################
    def get_actor(self, actor_name: str) -> Optional[ActorModel]:
        return self._actors.get(actor_name, None)

    ###############################################################################################################################################
    def get_stage(self, stage_name: str) -> Optional[StageModel]:
        return self._stages.get(stage_name, None)

    ###############################################################################################################################################
    def get_prop(self, prop_name: str) -> Optional[PropModel]:
        return self._props.get(prop_name, None)

    ###############################################################################################################################################
    def get_world_system(self, world_system_name: str) -> Optional[WorldSystemModel]:
        return self._world_systems.get(world_system_name, None)
