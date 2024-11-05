from typing import Dict, Optional, Any, final
from collections import namedtuple


@final
class CodeNameComponentSystem:

    def __init__(self, name: str) -> None:
        self._name: str = name
        self._name2codename: Dict[str, str] = {}
        self._codename2component: Dict[str, type[Any]] = {}
        self._name2stagetag: Dict[str, str] = {}
        self._stagetag2component: Dict[str, type[Any]] = {}

    ########################################################################################################################
    def register_code_name_component_class(
        self, name: str, code_name: str
    ) -> type[Any]:
        assert name not in self._name2codename, f"{name} already registered"
        self._name2codename[name] = code_name
        self._codename2component[code_name] = namedtuple(code_name, "name")
        return self._codename2component[code_name]

    ########################################################################################################################
    def get_code_name_component_class(self, name: str) -> Optional[type[Any]]:
        code_name = self._name2codename.get(name, None)
        if code_name is None:
            return None
        return self._codename2component.get(code_name, None)

    ########################################################################################################################
    def register_stage_tag_component_class(
        self, stage_name: str, stage_code_name: str
    ) -> None:

        stage_tag = f"stagetag_{stage_code_name}"
        self._name2stagetag[stage_name] = stage_tag
        self._stagetag2component[stage_tag] = namedtuple(stage_tag, "name")

    ########################################################################################################################
    def get_stage_tag_component_class(self, stage_name: str) -> Optional[type[Any]]:
        stage_tag = self._name2stagetag.get(stage_name, None)
        if stage_tag is None:
            return None
        return self._stagetag2component.get(stage_tag, None)


########################################################################################################################
