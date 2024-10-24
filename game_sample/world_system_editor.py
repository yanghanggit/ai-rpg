import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from typing import Dict, Any, cast
from game_sample.excel_data_world_system import ExcelDataWorldSystem
from game_sample.editor_guid_generator import editor_guid_generator
from my_models.models_def import (
    EditorEntityType,
    EditorProperty,
    WorldSystemModel,
    WorldSystemInstanceModel,
)


######################################################################################################################
class ExcelEditorWorldSystem:
    def __init__(
        self, data: Any, world_system_data_base: Dict[str, ExcelDataWorldSystem]
    ) -> None:

        assert data is not None
        assert world_system_data_base is not None

        self._data: Any = data
        self._world_system_data_base = world_system_data_base

        if self.type not in [EditorEntityType.WorldSystem]:
            assert False, f"Invalid type: {self.type}"

    ######################################################################################################################

    @property
    def type(self) -> str:
        assert self._data is not None
        return cast(str, self._data[EditorProperty.TYPE])

    ######################################################################################################################
    @property
    def excel_data(self) -> ExcelDataWorldSystem:
        return self._world_system_data_base[self._data[EditorProperty.NAME]]

    ######################################################################################################################
    @property
    def gen_agentpy_path(self) -> Path:
        assert self.excel_data is not None
        return self.excel_data.gen_agentpy_path

    ######################################################################################################################
    @property
    def name(self) -> str:
        assert self.excel_data is not None
        return self.excel_data.name

    ######################################################################################################################
    def gen_model(self) -> WorldSystemModel:

        return WorldSystemModel(
            name=self.excel_data.name,
            codename=self.excel_data.codename,
            url=self.excel_data.localhost,
        )

    ######################################################################################################################
    # 我的代理
    def instance(self) -> WorldSystemInstanceModel:
        return WorldSystemInstanceModel(
            name=self.excel_data.name,
            guid=editor_guid_generator.gen_world_system_guid(self.excel_data.name),
        )


######################################################################################################################
