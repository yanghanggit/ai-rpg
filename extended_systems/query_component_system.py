from typing import Dict, Optional, Any, final
from collections import namedtuple


@final
class QueryComponentSystem:

    def __init__(self, name: str) -> None:
        self._name: str = name
        self._name_2_query_code_name: Dict[str, str] = {}
        self._query_code_name_2_component: Dict[str, type[Any]] = {}
        self._name_2_stage_tag: Dict[str, str] = {}
        self._stage_tag_2_component: Dict[str, type[Any]] = {}

    ########################################################################################################################
    def register_query_component_class(self, name: str, code_name: str) -> type[Any]:
        assert name not in self._name_2_query_code_name, f"{name} already registered"
        self._name_2_query_code_name[name] = code_name
        self._query_code_name_2_component[code_name] = namedtuple(code_name, "name")
        return self._query_code_name_2_component[code_name]

    ########################################################################################################################
    def get_query_component_class(self, name: str) -> Optional[type[Any]]:
        code_name = self._name_2_query_code_name.get(name, None)
        if code_name is None:
            return None
        return self._query_code_name_2_component.get(code_name, None)

    ########################################################################################################################
    def register_stage_tag_component_class(
        self, stage_name: str, stage_code_name: str
    ) -> type[Any]:
        assert (
            stage_name not in self._name_2_stage_tag
        ), f"{stage_name} already registered"
        stage_tag = f"stagetag_{stage_code_name}"
        self._name_2_stage_tag[stage_name] = stage_tag
        self._stage_tag_2_component[stage_tag] = namedtuple(stage_tag, "name")
        return self._stage_tag_2_component[stage_tag]

    ########################################################################################################################
    def get_stage_tag_component_class(self, stage_name: str) -> Optional[type[Any]]:
        stage_tag = self._name_2_stage_tag.get(stage_name, None)
        if stage_tag is None:
            return None
        return self._stage_tag_2_component.get(stage_tag, None)


########################################################################################################################
