import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from typing import Dict, Any, cast
from game_sample.excel_data_prop import ExcelDataProp
from game_sample.excel_data_actor import ExcelDataActor
from my_models.editor_models import EditorEntityType, EditorProperty
from game_sample.actor_editor import ExcelEditorActor
from loguru import logger
from my_format_string.complex_name import ComplexName


class ExcelEditorActorSpawn:
    def __init__(
        self,
        data: Any,
        actor_data_base: Dict[str, ExcelDataActor],
        prop_data_base: Dict[str, ExcelDataProp],
    ) -> None:

        assert data is not None
        assert actor_data_base is not None
        assert prop_data_base is not None

        # 我的数据
        self._data: Any = data
        self._actor_data_base: Dict[str, ExcelDataActor] = actor_data_base
        self._prop_data_base: Dict[str, ExcelDataProp] = prop_data_base

        # 包一个这个类
        self._prototype_editor_actor: ExcelEditorActor = ExcelEditorActor(
            ComplexName(self.original_name),
            data=data,
            actor_data_base=actor_data_base,
            prop_data_base=prop_data_base,
            editor_spawn=self,
        )

        if self.type not in [EditorEntityType.ACTOR_SPAWN]:
            assert False, f"Invalid actor type: {self.type}"

        assert "#" in self.original_name, f"Invalid actor names: {self.original_name}"
        logger.debug(f"ExcelEditorActorSpawn: {self.original_name}")
        logger.debug(f"actor_name: {self.actor_name}")
        logger.debug(f"group_name: {self.group_name}")

    #################################################################################################################################
    @property
    def type(self) -> str:
        assert self._data is not None
        return cast(str, self._data[EditorProperty.TYPE])

    #################################################################################################################################
    @property
    def prototype_editor_actor(self) -> ExcelEditorActor:
        return self._prototype_editor_actor

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
        group_name = self.original_name.split("#")[1]
        return group_name

    #################################################################################################################################
