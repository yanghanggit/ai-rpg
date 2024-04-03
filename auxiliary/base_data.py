##干净与基础的数据结构

class StageConditionData:
    def __init__(self, name: str, type: str, prop_name: str) -> None:
        self.name = name
        self.type = type
        self.prop_name = prop_name


class PropData:
    def __init__(self, name: str, codename: str, description: str, is_unique: bool) -> None:
        self.name = name
        self.codename = codename
        self.description = description
        self.is_unique = is_unique

class NPCData:
    def __init__(self, name: str, codename: str, url: str, memory: str, props: set[PropData] = set()) -> None:
        self.name = name
        self.codename = codename
        self.url = url
        self.memory = memory
        self.props: set[PropData] = props


class StageData:
    def __init__(self, name: str, codename: str, description: str, url: str, memory: str, entry_conditions: list[StageConditionData], exit_conditions: list[StageConditionData], npcs: set[NPCData], props: set[PropData]) -> None:
        self.name = name
        self.codename = codename
        self.description = description
        self.url = url
        self.memory = memory
        self.entry_conditions: list[StageConditionData] = entry_conditions
        self.exit_conditions: list[StageConditionData] = exit_conditions
        self.npcs: set[NPCData] = npcs
        self.props: set[PropData] = props





        