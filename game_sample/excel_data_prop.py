import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from typing import Any, Dict


class ExcelDataProp:

    def __init__(self, data: Any) -> None:
        self._data = data

    @property
    def name(self) -> str:
        return str(self._data["name"])

    @property
    def codename(self) -> str:
        return str(self._data["codename"])

    @property
    def description(self) -> str:
        return str(self._data["description"])

    # @property
    # def isunique(self) -> str:
    #     return str(self._data["isunique"])

    @property
    def rag(self) -> str:
        return str(self._data["RAG"])

    @property
    def type(self) -> str:
        return str(self._data["type"])

    @property
    def attributes(self) -> str:
        return str(self._data["attributes"])

    @property
    def appearance(self) -> str:
        return str(self._data["appearance"])

    ############################################################################################################
    def serialization(self) -> Dict[str, Any]:
        output: Dict[str, Any] = {}
        output["name"] = self.name
        output["codename"] = self.codename
        output["description"] = self.description
        # output["isunique"] = self.isunique
        output["type"] = self.type
        output["attributes"] = [int(attr) for attr in self.attributes.split(",")]
        output["appearance"] = self.appearance
        return output

    ############################################################################################################
    def proxy(self) -> Dict[str, Any]:
        output: Dict[str, str] = {}
        output["name"] = self.name
        return output


############################################################################################################
