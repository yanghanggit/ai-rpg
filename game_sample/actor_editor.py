import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from typing import List, Dict, Any, Optional, cast
from game_sample.excel_data_prop import ExcelDataProp
import game_sample.utils
from game_sample.excel_data_actor import ExcelDataActor
from game_sample.editor_guid_generator import editor_guid_generator
from my_models.models_def import (
    EditorEntityType,
    EditorProperty,
    ActorModel,
    AttributesIndex,
    ActorInstanceModel,
    PropInstanceModel,
)


class ExcelEditorActor:

    def __init__(
        self,
        data: Any,
        actor_data_base: Dict[str, ExcelDataActor],
        prop_data_base: Dict[str, ExcelDataProp],
    ) -> None:
        assert data is not None
        assert actor_data_base is not None
        assert prop_data_base is not None

        #
        self._data: Any = data
        self._actor_data_base: Dict[str, ExcelDataActor] = actor_data_base
        self._prop_data_base: Dict[str, ExcelDataProp] = prop_data_base

        if self.type not in [EditorEntityType.Player, EditorEntityType.Actor]:
            assert False, f"Invalid actor type: {self.type}"

    #################################################################################################################################
    @property
    def type(self) -> str:
        assert self._data is not None
        return cast(str, self._data[EditorProperty.TYPE])

    #################################################################################################################################
    @property
    def excel_data(self) -> Optional[ExcelDataActor]:
        assert self._data is not None
        return self._actor_data_base[self._data[EditorProperty.NAME]]

    #################################################################################################################################
    @property
    def attributes(self) -> List[int]:
        assert self._data is not None
        data = cast(str, self._data[EditorProperty.ATTRIBUTES])
        assert "," in data, f"raw_string_val: {data} is not valid."
        values = [int(attr) for attr in data.split(",")]
        if len(values) < AttributesIndex.MAX.value:
            values.extend([0] * (AttributesIndex.MAX.value - len(values)))
        return values

    #################################################################################################################################
    @property
    def kick_off_message(self) -> str:
        assert self._data is not None
        return cast(str, self._data[EditorProperty.KICK_OFF_MESSAGE])

    #################################################################################################################################
    @property
    def actor_current_using_prop(self) -> List[str]:
        assert self._data is not None
        raw_string = cast(str, self._data[EditorProperty.ACTOR_CURRENT_USING_PROP])
        if raw_string is None:
            return []
        return [str(attr) for attr in raw_string.split(";")]

    #################################################################################################################################
    @property
    def actor_prop(self) -> List[str]:
        data: Optional[str] = self._data[EditorProperty.ACTOR_PROP]
        if data is None:
            return []

        split_data = data.split(";")
        return [prop for prop in split_data if prop != ""]

    #################################################################################################################################
    @property
    def name(self) -> str:
        assert self.excel_data is not None
        return self.excel_data.name

    #################################################################################################################################
    def parse_actor_prop(self) -> List[tuple[ExcelDataProp, int]]:

        ret: List[tuple[ExcelDataProp, int]] = []

        actor_prop = self.actor_prop
        for prop_info in actor_prop:
            if prop_info == "":
                continue

            parse = game_sample.utils.parse_prop_info(prop_info)
            prop_name = parse[0]
            prop_count = parse[1]

            if prop_name not in self._prop_data_base:
                assert False, f"Invalid prop: {prop_name}"
                continue

            ret.append((self._prop_data_base[prop_name], prop_count))

        return ret

    #################################################################################################################################
    # 核心函数！！！
    def gen_model(self) -> ActorModel:

        assert self.excel_data is not None

        return ActorModel(
            name=self.excel_data.name,
            codename=self.excel_data.codename,
            url=self.excel_data.localhost,
            kick_off_message=self.kick_off_message,
            actor_archives=self.excel_data._actor_archives,
            stage_archives=self.excel_data._stage_archives,
            attributes=self.attributes,
            body=self.excel_data.body,
        )

    #################################################################################################################################
    def instance(self) -> ActorInstanceModel:
        assert self.excel_data is not None
        ret: ActorInstanceModel = ActorInstanceModel(
            name=self.excel_data.name,
            guid=editor_guid_generator.gen_actor_guid(self.excel_data.name),
            props=[],
            actor_current_using_prop=self.actor_current_using_prop,
        )

        for tp in self.parse_actor_prop():
            ret.props.append(
                PropInstanceModel(
                    name=tp[0].name,
                    guid=editor_guid_generator.gen_prop_guid(tp[0].name),
                    count=tp[1],
                )
            )

        return ret

    #################################################################################################################################
