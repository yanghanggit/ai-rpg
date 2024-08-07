from typing import Any, List
from my_data.data_model import ActorProxyModel, StageProxyModel, WorldSystemProxyModel, GameBuilderModel
from my_data.data_base_system import DataBaseSystem
from pathlib import Path
import json

class GameBuilder:

    """
    这是一个分析游戏json的数据的类。
    将游戏数据转换为游戏对象。
    内部管理着WorldSystemBuilder，PlayerBuilder，ActorBuilder，StageBuilder，DataBaseSystem。
    """

    def __init__(self, 
                 name: str, 
                 data: Any,
                 runtime_file_dir: Path) -> None:
        
        self._game_name: str = name

        self._runtime_dir: Path = runtime_file_dir
        assert self._runtime_dir is not None
        assert self._runtime_dir.exists()

        #logger.debug(json.dumps(GameBuilderModel.model_json_schema(), indent=2))  
        self._model = GameBuilderModel.model_validate_json(json.dumps(data, ensure_ascii = False))
        self._data_base_system: DataBaseSystem = DataBaseSystem(self._model.database)
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
###############################################################################################################################################
    


