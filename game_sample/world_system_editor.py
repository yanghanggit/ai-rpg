import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from loguru import logger
from typing import Dict, Any
from game_sample.excel_data_world_system import ExcelDataWorldSystem
from game_sample.editor_guid_generator import editor_guid_generator


######################################################################################################################
class ExcelEditorWorldSystem:
    def __init__(
        self, my_data: Any, world_system_data_base: Dict[str, ExcelDataWorldSystem]
    ) -> None:
        self._my_data: Any = my_data
        assert self._my_data is not None
        self._world_system_data_base = world_system_data_base
        if my_data["type"] not in ["WorldSystem"]:
            logger.error(f"Invalid type: {my_data['type']}")
            assert False

    ######################################################################################################################
    @property
    def excel_data(self) -> ExcelDataWorldSystem:
        return self._world_system_data_base[self._my_data["name"]]

    ######################################################################################################################
    # 核心函数！！！
    def serialization(self) -> Dict[str, Any]:
        output: Dict[str, str] = {}
        output["name"] = self.excel_data.name
        output["codename"] = self.excel_data.codename
        output["url"] = self.excel_data.localhost
        return output

    ######################################################################################################################
    # 我的代理
    def proxy(self) -> Dict[str, Any]:
        output: Dict[str, Any] = {}
        output["name"] = self.excel_data.name
        output["guid"] = editor_guid_generator.gen_world_system_guid(
            self.excel_data.name
        )
        return output

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
