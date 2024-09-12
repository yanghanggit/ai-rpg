from typing import Dict, Optional, Any
from collections import namedtuple


class CodeNameComponentSystem:

    def __init__(self, name: str) -> None:
        self._name: str = name
        self._name2codename: Dict[str, str] = {}
        self._codename2component: Dict[str, Any] = {}
        self._name2stagetag: Dict[str, str] = {}
        self._stagetag2component: Dict[str, Any] = {}

    ########################################################################################################################
    def register_code_name_component_class(self, name: str, codename: str) -> None:
        self._name2codename[name] = codename
        self._codename2component[codename] = namedtuple(codename, "name")

    ########################################################################################################################
    def get_component_class_by_name(self, name: str) -> Optional[Any]:
        codename = self._name2codename.get(name, None)
        if codename is None:
            return None
        return self._codename2component.get(codename, None)

    ########################################################################################################################
    def get_component_class_by_code_name(self, codename: str) -> Optional[Any]:
        return self._codename2component.get(codename, None)

    ########################################################################################################################
    def register_stage_tag_component_class(
        self, stagename: str, stagecodename: str
    ) -> None:
        stagetag = f"stagetag_{stagecodename}"
        self._name2stagetag[stagename] = stagetag
        self._stagetag2component[stagetag] = namedtuple(stagetag, "name")

    ########################################################################################################################
    def get_stage_tag_component_class_by_name(self, stagename: str) -> Optional[Any]:
        stagetag = self._name2stagetag.get(stagename, None)
        if stagetag is None:
            return None
        return self._stagetag2component.get(stagetag, None)


########################################################################################################################
