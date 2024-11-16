from loguru import logger
from enum import StrEnum, unique


@unique
class ComplexActorNameSymbol(StrEnum):
    GROUP_FLAG = "?"
    COUNT_FLAG = "="
    GUID_FLAG = "%"


class ComplexActorName:

    #################################################################################################################################
    @staticmethod
    def format_name_with_guid(name: str, guid: int) -> str:
        return f"{name}{ComplexActorNameSymbol.GUID_FLAG}{guid}"

    #################################################################################################################################
    @staticmethod
    def contains_guid(name: str) -> bool:
        return ComplexActorNameSymbol.GUID_FLAG in name

    #################################################################################################################################
    @staticmethod
    def extract_name(name: str) -> str:
        return name.split(ComplexActorNameSymbol.GUID_FLAG)[0]

    #################################################################################################################################
    @staticmethod
    def extract_guid(name: str) -> int:
        return int(name.split(ComplexActorNameSymbol.GUID_FLAG)[1])

    #################################################################################################################################
    def __init__(self, source_name: str) -> None:
        self._source_name: str = source_name

    #################################################################################################################################
    @property
    def source_name(self) -> str:
        return str(self._source_name)

    #################################################################################################################################
    @property
    def is_complex_name(self) -> bool:

        if ComplexActorNameSymbol.GROUP_FLAG in self.source_name:
            assert (
                ComplexActorNameSymbol.COUNT_FLAG in self.source_name
            ), f"Invalid actor names: {self.source_name}"

        return (
            ComplexActorNameSymbol.GROUP_FLAG in self.source_name
            and ComplexActorNameSymbol.COUNT_FLAG in self.source_name
        )

    #################################################################################################################################
    @property
    def actor_name(self) -> str:

        if not self.is_complex_name:
            return self.source_name

        name = self.source_name.split(ComplexActorNameSymbol.GROUP_FLAG)[0]
        return name

    #################################################################################################################################
    @property
    def group_name(self) -> str:

        if not self.is_complex_name:
            return ""

        group_name_and_count = self.source_name.split(
            ComplexActorNameSymbol.GROUP_FLAG
        )[1]
        group_name = group_name_and_count.split(ComplexActorNameSymbol.COUNT_FLAG)[0]
        return group_name

    #################################################################################################################################
    @property
    def group_count(self) -> int:

        if not self.is_complex_name:
            return 0

        group_name_and_count = self.source_name.split(
            ComplexActorNameSymbol.GROUP_FLAG
        )[1]
        count = group_name_and_count.split(ComplexActorNameSymbol.COUNT_FLAG)[1]
        assert count.isnumeric(), f"Invalid actor names: {self.source_name}"
        if int(count) < 0:
            logger.error(f"Invalid group count: {self.source_name}")
            return 0
        return int(count)

    #################################################################################################################################
