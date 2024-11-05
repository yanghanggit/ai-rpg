import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from typing import List, Dict, Any, cast
from game_sample.excel_data_prop import ExcelDataProp
from game_sample.excel_data_actor import ExcelDataActor
from my_models.models_def import (
    EditorProperty,
    SpawnerModel,
)
from loguru import logger
from game_sample.actor_spawn_editor import ExcelEditorActorSpawn


class ExcelEditorSpawner:
    def __init__(
        self,
        data: Any,
        actor_data_base: Dict[str, ExcelDataActor],
        prop_data_base: Dict[str, ExcelDataProp],
    ) -> None:

        assert data is not None
        assert actor_data_base is not None
        assert prop_data_base is not None

        #
        self._data: Any = data
        self._actor_data_base: Dict[str, ExcelDataActor] = actor_data_base
        self._prop_data_base: Dict[str, ExcelDataProp] = prop_data_base
        self._editor_actor_spawns: List[ExcelEditorActorSpawn] = []

        logger.debug(f"ExcelEditorSpawner: {self.name}")
        logger.debug(f"ExcelEditorSpawner: {self.spawn}")
        logger.debug(f"ExcelEditorSpawner: {self.extract_actor_names}")

    #################################################################################################################################
    @property
    def name(self) -> str:
        return str(self._data[EditorProperty.NAME])

    #################################################################################################################################
    @property
    def spawn(self) -> List[str]:
        assert self._data is not None
        raw_string = cast(str, self._data[EditorProperty.SPAWN])
        if raw_string is None:
            return []
        return [str(attr) for attr in raw_string.split(";")]

    #################################################################################################################################
    @property
    def extract_actor_names(self) -> List[str]:
        original_spawn = self.spawn
        actor_names = []
        for name in original_spawn:
            if "#" in name:
                actor_name = name.split("#")[0]
                actor_names.append(actor_name)
            else:
                actor_names.append(name)

        return actor_names

    #################################################################################################################################

    def gen_model(self) -> SpawnerModel:
        ret = SpawnerModel(name=self.name, spawn=self.spawn, actor_prototype=[])

        for editor_actor_spawn in self._editor_actor_spawns:
            prototype_instance = (
                editor_actor_spawn.prototype_editor_actor.gen_instance()
            )
            prototype_instance.guid = 0  # 0表示这个是一个原型
            prototype_instance.suffix = editor_actor_spawn.group_name  # 这个是一个组名
            ret.actor_prototype.append(prototype_instance)

        return ret

    #################################################################################################################################
    def match_actor_spawner(self, editor_actor_spawn: ExcelEditorActorSpawn) -> bool:

        for data in self.spawn:
            if data == editor_actor_spawn.original_name:
                self._editor_actor_spawns.append(editor_actor_spawn)
                return True

        self._editor_actor_spawns
        return False

    #################################################################################################################################
