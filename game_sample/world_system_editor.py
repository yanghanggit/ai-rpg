import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from typing import Dict, Any, cast
from game_sample.world_system_data import ExcelDataWorldSystem
from game_sample.guid_generator import editor_guid_generator
from models.entity_models import (
    WorldSystemModel,
    WorldSystemInstanceModel,
)
from models.editor_models import EditorEntityType, EditorProperty


######################################################################################################################
class ExcelEditorWorldSystem:
    def __init__(
        self, data: Any, world_system_data_base: Dict[str, ExcelDataWorldSystem]
    ) -> None:

        assert data is not None
        assert world_system_data_base is not None

        self._data: Any = data
        self._world_system_data_base = world_system_data_base

        if self.type not in [EditorEntityType.WORLD_SYSTEM]:
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
    def name(self) -> str:
        assert self.excel_data is not None
        return self.excel_data.name

    ######################################################################################################################
    @property
    def codename(self) -> str:
        assert self.excel_data is not None
        return self.excel_data.codename

    ######################################################################################################################
    @property
    def system_prompt(self) -> str:
        assert self.excel_data is not None
        return self.excel_data._gen_system_prompt

    ######################################################################################################################
    def gen_model(self) -> WorldSystemModel:

        return WorldSystemModel(
            name=self.excel_data.name,
            codename=self.excel_data.codename,
            url=self.excel_data.localhost_api_url,
            system_prompt=self.system_prompt,
        )

    ######################################################################################################################
    # 我的代理
    def gen_instance(self) -> WorldSystemInstanceModel:
        return WorldSystemInstanceModel(
            name=self.excel_data.name,
            guid=editor_guid_generator.gen_world_system_guid(self.excel_data.name),
        )


######################################################################################################################
