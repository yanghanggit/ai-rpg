import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from typing import Any, Dict, List, cast


class ExcelDataProp:

    def __init__(self, data: Any) -> None:
        self._data = data
        assert self.type in [ "Special", "Weapon", "Clothes", "NonConsumableItem", "ConsumableItem", "Skill"], f"Invalid Prop type: {self.type}"

    @property
    def name(self) -> str:
        return str(self._data["name"])

    @property
    def codename(self) -> str:
        return str(self._data["codename"])

    @property
    def description(self) -> str:
        return str(self._data["description"])

    @property
    def rag(self) -> str:
        return str(self._data["RAG"])

    @property
    def type(self) -> str:
        return str(self._data["type"])

    @property
    def attributes(self) -> List[int]:
        assert self._data is not None
        data = cast(str, self._data["attributes"])
        assert "," in data, f"raw_string_val: {data} is not valid."
        values = [int(attr) for attr in data.split(",")]
        if len(values) < 10:
            values.extend([0] * (10 - len(values)))
        return values

    @property
    def appearance(self) -> str:
        return str(self._data["appearance"])

    ############################################################################################################
    @property
    def can_placed(self) -> bool:
        return (
            self.type == "Weapon"
            or self.type == "Clothes"
            or self.type == "NonConsumableItem"
            or self.type == "ConsumableItem"
        )

    ############################################################################################################
    def serialization(self) -> Dict[str, Any]:
        output: Dict[str, Any] = {}
        output["name"] = self.name
        output["codename"] = self.codename
        output["description"] = self.description
        output["type"] = self.type
        output["attributes"] = self.attributes
        output["appearance"] = self.appearance
        return output

    ############################################################################################################
    def proxy(self) -> Dict[str, Any]:
        output: Dict[str, str] = {}
        output["name"] = self.name
        return output


############################################################################################################
