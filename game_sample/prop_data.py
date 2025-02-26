import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from typing import Any, List, cast
from rpg_models.entity_models import PropModel, Attributes
from rpg_models.file_models import PropType, PropSkillUsageMode
from enum import StrEnum, unique
import pandas


@unique
class DataPropProperty(StrEnum):
    NAME = "name"
    CODE_NAME = "codename"
    DETAILS = "details"
    TYPE = "type"
    ATTRIBUTES = "attributes"
    APPEARANCE = "appearance"
    INSIGHT = "insight"


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
        return str(self._data[DataPropProperty.DETAILS])

    ############################################################################################################
    @property
    def type(self) -> str:
        return str(self._data[DataPropProperty.TYPE])

    ############################################################################################################
    @property
    def attributes(self) -> List[int]:

        if pandas.isna(self._data[DataPropProperty.ATTRIBUTES]):
            assert False, f"attributes is None: {self.name}"
            return [0] * Attributes.MAX

        assert self._data is not None
        data = cast(str, self._data[DataPropProperty.ATTRIBUTES])
        assert "," in data, f"raw_string_val: {data} is not valid."
        values = [int(attr) for attr in data.split(",")]
        if len(values) < Attributes.MAX:
            values.extend([0] * (Attributes.MAX - len(values)))

        assert (
            values[Attributes.DAMAGE] * values[Attributes.HEAL] == 0
        ), f"Invalid Attributes: {values}"
        return values

    ############################################################################################################
    @property
    def appearance(self) -> str:
        ret = str(self._data[DataPropProperty.APPEARANCE])
        if self.type == PropType.TYPE_SKILL:
            assert (
                PropSkillUsageMode.CASTER_TAG in ret
            ), f"Invalid Skill Target Type: {ret}"
            assert (
                PropSkillUsageMode.SINGLE_TARGET_TAG in ret
                or PropSkillUsageMode.MULTI_TARGETS_TAG in ret
            ), f"Invalid Skill Target Type: {ret}"

        return ret

    ############################################################################################################
    @property
    def insight(self) -> str:
        if pandas.isna(self._data[DataPropProperty.INSIGHT]):
            return ""
        return str(self._data[DataPropProperty.INSIGHT])

    ############################################################################################################
    def gen_model(self) -> PropModel:

        return PropModel(
            name=self.name,
            codename=self.codename,
            details=self.details,
            type=self.type,
            attributes=self.attributes,
            appearance=self.appearance,
            insight=self.insight,
        )


############################################################################################################
