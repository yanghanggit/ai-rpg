import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from loguru import logger
from typing import Dict, Any
from game_sample.excel_data import ExcelDataWorldSystem


######################################################################################################################
class ExcelEditorWorldSystem:
    def __init__(self, raw_data: Any, world_system_data_base: Dict[str, ExcelDataWorldSystem]) -> None:
        self._raw_data: Any = raw_data
        assert self._raw_data is not None
        self._world_system_data_base = world_system_data_base
        if raw_data["type"] not in ["WorldSystem"]:
            logger.error(f"Invalid type: {raw_data['type']}")
            assert False
######################################################################################################################
    @property
    def data(self) -> ExcelDataWorldSystem:
        return self._world_system_data_base[self._raw_data["name"]]
######################################################################################################################
    # 核心函数！！！
    def serialization(self) -> Dict[str, Any]:
        output: Dict[str, str] = {}
        output['name'] = self.data.name
        output['codename'] = self.data.codename
        output['url'] = self.data.localhost
        return output
######################################################################################################################
    # 我的代理
    def proxy(self) -> Dict[str, Any]:
        output: Dict[str, Any] = {}
        output['name'] = self.data.name
        return output
######################################################################################################################