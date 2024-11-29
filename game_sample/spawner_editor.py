import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from typing import List, Dict, Any, cast, Set
from game_sample.prop_data import ExcelDataProp
from game_sample.actor_data import ExcelDataActor
from models.entity_models import (
    SpawnerModel,
)
from models.editor_models import EditorProperty
from loguru import logger
from format_string.complex_actor_name import ComplexActorName
from game_sample.actor_editor import ExcelEditorActor


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
        self._editor_actor_prototypes: List[ExcelEditorActor] = []

        logger.debug(f"ExcelEditorSpawner: {self.name}")
        logger.debug(f"ExcelEditorSpawner: {self.spawn}")

    #################################################################################################################################
    @property
    def name(self) -> str:
        return str(self._data[EditorProperty.NAME])

    #################################################################################################################################
    @property
    def spawn(self) -> List[ComplexActorName]:
        assert self._data is not None
        raw_string = cast(str, self._data[EditorProperty.SPAWN_CONFIG])
        if raw_string is None:
            return []
        tmp = [str(attr) for attr in raw_string.split(";")]
        return [ComplexActorName(attr) for attr in tmp]

    #################################################################################################################################

    def gen_model(self) -> SpawnerModel:
        return SpawnerModel(
            name=self.name,
            actor_prototypes=[
                actor.format_actor_name_with_guid
                for actor in self._editor_actor_prototypes
            ],
        )

    #################################################################################################################################
    def gather_valid_spawner_groups(
        self, global_group: Dict[str, List[ExcelEditorActor]]
    ) -> Set[str]:
        ret: Set[str] = set()

        for spawn in self.spawn:
            if spawn.group_name not in global_group:
                assert False, f"Invalid group: {spawn.group_name}"
                continue

            self._editor_actor_prototypes.extend(global_group[spawn.group_name])
            ret.add(spawn.group_name)

        return ret

    #################################################################################################################################
