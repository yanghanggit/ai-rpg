from typing import final
from enum import StrEnum, unique


@unique
class ComplexNameSymbol(StrEnum):
    GUID_FLAG = "%"


@final
class ComplexName:

    #################################################################################################################################
    def __init__(self, source_name: str) -> None:
        self._source_name: str = source_name

    #################################################################################################################################
    @property
    def source_name(self) -> str:
        return str(self._source_name)

    #################################################################################################################################
    @property
    def is_complex(self) -> bool:
        return ComplexNameSymbol.GUID_FLAG in self.source_name

    #################################################################################################################################
    @property
    def parse_name(self) -> str:
        if not self.is_complex:
            return self.source_name
        name = self.source_name.split(ComplexNameSymbol.GUID_FLAG)[0]
        return name

    #################################################################################################################################
    @property
    def guid(self) -> int:
        if ComplexNameSymbol.GUID_FLAG not in self.source_name:
            return 0
        return int(self.source_name.split(ComplexNameSymbol.GUID_FLAG)[1])

    #################################################################################################################################
