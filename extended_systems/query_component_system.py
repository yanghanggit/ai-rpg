from typing import Dict, Optional, Any, final
from collections import namedtuple


@final
class QueryComponentSystem:

    def __init__(self) -> None:
        self._name_2_query_code_name: Dict[str, str] = {}
        self._query_code_name_2_component: Dict[str, type[Any]] = {}
        self._name_2_stage_tag: Dict[str, str] = {}
        self._stage_tag_2_component: Dict[str, type[Any]] = {}

    ########################################################################################################################
    def register_query_component_class(
        self, instance_name: str, data_base_code_name: str, guid: int
    ) -> type[Any]:

        assert (
            instance_name not in self._name_2_query_code_name
        ), f"{instance_name} already registered"
        assert (
            "%" not in data_base_code_name
        ), f"{data_base_code_name} is not a valid code name"

        dynamic_query_name = f"{data_base_code_name}{guid}"
        self._name_2_query_code_name[instance_name] = dynamic_query_name
        self._query_code_name_2_component[dynamic_query_name] = namedtuple(
            dynamic_query_name, "name"
        )
        return self._query_code_name_2_component[dynamic_query_name]

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
