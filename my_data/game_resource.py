from typing import Any, List
from my_data.model_def import (
    ActorProxyModel,
    StageProxyModel,
    WorldSystemProxyModel,
    GameModel,
)
from my_data.data_base import DataBase
from pathlib import Path
import json


class GameResource:

    def __init__(self, name: str, data: Any, runtime_file_dir: Path) -> None:

        self._game_name: str = name

        self._runtime_dir: Path = runtime_file_dir
        assert self._runtime_dir is not None
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        assert self._runtime_dir.exists()

        self._model = GameModel.model_validate_json(
            json.dumps(data, ensure_ascii=False)
        )
        self._data_base = DataBase(self._model.database)

    ###############################################################################################################################################
    @property
    def version(self) -> str:
        return self._model.version

    ###############################################################################################################################################
    @property
    def about_game(self) -> str:
        return self._model.about_game

    ###############################################################################################################################################
    @property
    def world_systems_proxy(self) -> List[WorldSystemProxyModel]:
        return self._model.world_systems

    ###############################################################################################################################################
    @property
    def players_proxy(self) -> List[ActorProxyModel]:
        return self._model.players

    ###############################################################################################################################################
    @property
    def actors_proxy(self) -> List[ActorProxyModel]:
        return self._model.actors

    ###############################################################################################################################################
    @property
    def stages_proxy(self) -> List[StageProxyModel]:
        return self._model.stages
