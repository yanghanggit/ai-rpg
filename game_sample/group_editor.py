import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from typing import List, Dict, Any, cast, Optional
from game_sample.excel_data_prop import ExcelDataProp
from game_sample.excel_data_actor import ExcelDataActor
from game_sample.editor_guid_generator import editor_guid_generator
from my_models.editor_models import EditorEntityType, EditorProperty
from game_sample.actor_editor import ExcelEditorActor
from loguru import logger
import game_sample.configuration as configuration


class ExcelEditorGroup:
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
        self._cache_spawn_actors: Optional[List[ExcelEditorActor]] = None

        if self.type not in [EditorEntityType.ACTOR_GROUP]:
            assert False, f"Invalid actor type: {self.type}"

        assert "#" in self.original_name, f"Invalid actor names: {self.original_name}"
        assert ":" in self.original_name, f"Invalid actor names: {self.original_name}"
        logger.debug(f"ExcelEditorGroup: {self.original_name}")
        logger.debug(f"actor_name: {self.actor_name}")
        logger.debug(f"group_name: {self.group_name}")
        logger.debug(f"group_count: {self.group_count}")

    #################################################################################################################################
    @property
    def type(self) -> str:
        assert self._data is not None
        return cast(str, self._data[EditorProperty.TYPE])

    #################################################################################################################################
    @property
    def original_name(self) -> str:
        assert self._data is not None
        return str(self._data[EditorProperty.NAME])

    #################################################################################################################################
    @property
    def actor_name(self) -> str:
        name = self.original_name.split("#")[0]
        return name

    #################################################################################################################################
    @property
    def group_name(self) -> str:
        assert "#" in self.original_name, f"Invalid actor names: {self.original_name}"
        group_name_and_count = self.original_name.split("#")[1]
        group_name = group_name_and_count.split(":")[0]
        return group_name

    #################################################################################################################################
    @property
    def group_count(self) -> int:
        assert "#" in self.original_name, f"Invalid actor names: {self.original_name}"
        group_name_and_count = self.original_name.split("#")[1]
        count = group_name_and_count.split(":")[1]
        assert count.isnumeric(), f"Invalid actor names: {self.original_name}"
        ret = int(count)
        if ret < 0:
            logger.error(f"Invalid group count: {self.original_name}")
            ret = 0
        return ret

    #################################################################################################################################
    @property
    def generate_excel_actors(self) -> List[ExcelEditorActor]:
        if not configuration.EN_ACTOR_GROUP_FEATURE:
            return []

        if self._cache_spawn_actors is None:
            self._cache_spawn_actors = []

            for i in range(self.group_count):
                self._cache_spawn_actors.append(
                    ExcelEditorActor(
                        data=self._data,
                        actor_data_base=self._actor_data_base,
                        prop_data_base=self._prop_data_base,
                        editor_group=self,
                        group_gen_guid=editor_guid_generator.gen_actor_guid(
                            self.actor_name
                        ),
                    )
                )

        return self._cache_spawn_actors

    #################################################################################################################################
    def equal(self, string_val: str) -> bool:
        assert "#" in string_val, f"Invalid actor names: {string_val}"
        assert ":" in string_val, f"Invalid actor names: {string_val}"
        return self.original_name == string_val

    #################################################################################################################################
