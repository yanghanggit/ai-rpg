from loguru import logger


class ComplexName:

    def __init__(self, source_name: str) -> None:
        self._source_name: str = source_name

    ############################################################################################################
    @property
    def source_name(self) -> str:
        return str(self._source_name)

    #################################################################################################################################
    @property
    def is_complex_name(self) -> bool:

        if "#" in self.source_name:
            assert ":" in self.source_name, f"Invalid actor names: {self.source_name}"

        return "#" in self.source_name and ":" in self.source_name

    #################################################################################################################################
    @property
    def actor_name(self) -> str:

        if not self.is_complex_name:
            return self.source_name

        name = self.source_name.split("#")[0]
        return name

    #################################################################################################################################
    @property
    def group_name(self) -> str:

        if not self.is_complex_name:
            return ""

        group_name_and_count = self.source_name.split("#")[1]
        group_name = group_name_and_count.split(":")[0]
        return group_name

    #################################################################################################################################
    @property
    def group_count(self) -> int:

        if not self.is_complex_name:
            return 0

        group_name_and_count = self.source_name.split("#")[1]
        count = group_name_and_count.split(":")[1]
        assert count.isnumeric(), f"Invalid actor names: {self.source_name}"
        if int(count) < 0:
            logger.error(f"Invalid group count: {self.source_name}")
            return 0
        return int(count)

    #################################################################################################################################
