import sys
from pathlib import Path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from loguru import logger
from typing import List, Dict, Any, Optional
from budding_world.excel_data import ExcelDataWorldSystem


######################################################################################################################
class ExcelEditorWorldSystem:
    def __init__(self, raw_data: Any, world_system_data_base: Dict[str, ExcelDataWorldSystem]) -> None:
        self._raw_data: Any = raw_data
        assert self._raw_data is not None
        self._world_system_data_base = world_system_data_base
        if raw_data["type"] not in ["WorldSystem"]:
            logger.error(f"Invalid type: {raw_data['type']}")
            assert False
            #return
######################################################################################################################
    @property
    def data(self) -> ExcelDataWorldSystem:
        return self._world_system_data_base[self._raw_data["name"]]
######################################################################################################################
    def _serialization_core(self, target: Optional[ExcelDataWorldSystem]) -> Dict[str, str]:
        if target is None:
            return {}
        _dt: Dict[str, str] = {}
        _dt['name'] = target._name
        _dt['codename'] = target._codename
        _dt['url'] = target.localhost()
        return _dt
######################################################################################################################
    # 核心函数！！！
    def serialization(self) -> Dict[str, Any]:
        _dt: Dict[str, Any] = {}
        _dt["world_system"] = self._serialization_core(self.data)
        return _dt
######################################################################################################################
    # 我的代理
    def proxy(self) -> Dict[str, Any]:
        output: Dict[str, Any] = {}
        proxy: Dict[str, str] = {}
        proxy['name'] = self.data._name
        output["world_system"] = proxy
        return output
######################################################################################################################