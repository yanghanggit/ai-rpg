import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from typing import Any, List, cast
from my_models.entity_models import PropModel, Attributes
from my_models.file_models import PropType, SkillUsageType
from enum import StrEnum, unique


@unique
class DataPropProperty(StrEnum):
    NAME = "name"
    CODE_NAME = "codename"
    DETAILS = "details"
    RAG = "RAG"
    TYPE = "type"
    ATTRIBUTES = "attributes"
    APPEARANCE = "appearance"


############################################################################################################


class ExcelDataProp:

    def __init__(self, data: Any) -> None:
        assert data is not None
        self._data = data

        assert self.type in [
            PropType.TYPE_SPECIAL,
            PropType.TYPE_WEAPON,
            PropType.TYPE_CLOTHES,
            PropType.TYPE_NON_CONSUMABLE_ITEM,
            PropType.TYPE_CONSUMABLE_ITEM,
            PropType.TYPE_SKILL,
        ], f"Invalid Prop type: {self.type}"

    ############################################################################################################
    @property
    def name(self) -> str:
        return str(self._data[DataPropProperty.NAME])

    ############################################################################################################
    @property
    def codename(self) -> str:
        return str(self._data[DataPropProperty.CODE_NAME])

    ############################################################################################################
    @property
    def details(self) -> str:
        ret = str(self._data[DataPropProperty.DETAILS])
        if self.type == PropType.TYPE_SKILL:
            assert (
                SkillUsageType.SINGLE_TARGET_SKILL_TAG in ret
                or SkillUsageType.MULTI_TARGET_SKILL_TAG in ret
            ), f"Invalid Skill Target Type: {ret}"
        return ret

    ############################################################################################################
    @property
    def rag(self) -> str:
        return str(self._data[DataPropProperty.RAG])

    ############################################################################################################
    @property
    def type(self) -> str:
        return str(self._data[DataPropProperty.TYPE])

    ############################################################################################################
    @property
    def attributes(self) -> List[int]:
        assert self._data is not None
        data = cast(str, self._data[DataPropProperty.ATTRIBUTES])
        assert "," in data, f"raw_string_val: {data} is not valid."
        values = [int(attr) for attr in data.split(",")]
        if len(values) < Attributes.MAX:
            values.extend([0] * (Attributes.MAX - len(values)))
        return values

    ############################################################################################################
    @property
    def appearance(self) -> str:
        return str(self._data[DataPropProperty.APPEARANCE])

    ############################################################################################################
    def gen_model(self) -> PropModel:

        return PropModel(
            name=self.name,
            codename=self.codename,
            details=self.details,
            type=self.type,
            attributes=self.attributes,
            appearance=self.appearance,
        )


############################################################################################################
