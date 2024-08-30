import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent  # 将项目根目录添加到sys.path
sys.path.append(str(root_dir))
from loguru import logger
from typing import List, Dict, Any, Optional, cast

# from game_sample.gen_funcs import (proxy_prop)
from game_sample.excel_data_prop import ExcelDataProp
from game_sample.excel_data_actor import ExcelDataActor
from game_sample.excel_data_stage import ExcelDataStage
import pandas as pd
import game_sample.utils


class ExcelEditorStage:

    def __init__(
        self,
        my_data: Any,
        actor_data_base: Dict[str, ExcelDataActor],
        prop_data_base: Dict[str, ExcelDataProp],
        stage_data_base: Dict[str, ExcelDataStage],
    ) -> None:

        if my_data["type"] not in ["Stage"]:
            assert False, f"Invalid Stage type: {my_data['type']}"
        #
        self._my_data: Any = my_data
        self._actor_data_base: Dict[str, ExcelDataActor] = actor_data_base
        self._prop_data_base: Dict[str, ExcelDataProp] = prop_data_base
        self._stage_data_base: Dict[str, ExcelDataStage] = stage_data_base
        self._stage_prop: List[tuple[ExcelDataProp, int]] = []
        self._actors_in_stage: List[ExcelDataActor] = []
        # 分析数据
        self.parse_stage_props()
        self.parse_actors_in_stage()

    #################################################################################################################################
    @property
    def attributes(self) -> List[int]:
        assert self._my_data is not None
        data = cast(str, self._my_data["attributes"])
        assert "," in data, f"raw_string_val: {data} is not valid."
        values = [int(attr) for attr in data.split(",")]
        if len(values) < 10:
            values.extend([0] * (10 - len(values)))
        return values

    ################################################################################################################################
    def parse_stage_props(self) -> None:
        data: Optional[str] = self._my_data["stage_prop"]
        if data is None:
            return

        for prop_str in data.split(";"):
            if prop_str == "":
                continue

            tp = game_sample.utils.parse_prop_string(prop_str)
            if tp[0] not in self._prop_data_base:
                assert False, f"Invalid prop: {tp[0]}"
                continue

            prop_data = self._prop_data_base[tp[0]]
            if not prop_data.can_placed:
                assert False, f"Invalid prop: {prop_data.name}"
                continue

            self._stage_prop.append((prop_data, tp[1]))

    ################################################################################################################################
    def parse_actors_in_stage(self) -> None:
        data: Optional[str] = self._my_data["actors_in_stage"]
        if data is None:
            return
        names = data.split(";")
        for _n in names:
            if _n in self._actor_data_base:
                self._actors_in_stage.append(self._actor_data_base[_n])
            else:
                logger.error(f"Invalid actor: {_n}")

    ################################################################################################################################
    @property
    def kick_off_message(self) -> str:
        assert self._my_data is not None
        return cast(str, self._my_data["kick_off_message"])

    ################################################################################################################################
    @property
    def stage_graph(self) -> List[str]:
        assert self._my_data is not None
        if self._my_data["stage_graph"] is None:
            return []
        copy_data = str(self._my_data["stage_graph"])
        ret = copy_data.split(";")
        if self.name in ret:
            copy_name = str(self.name)
            ret.remove(copy_name)
        return ret

    ################################################################################################################################
    def add_stage_graph(self, graph: str) -> None:
        stage_graph_value = self.stage_graph
        if graph not in stage_graph_value:
            stage_graph_value.append(graph)
            self._my_data["stage_graph"] = ";".join(stage_graph_value)

    ################################################################################################################################
    def stage_props_proxy(
        self, props: List[tuple[ExcelDataProp, int]]
    ) -> List[Dict[str, str]]:
        ls: List[Dict[str, str]] = []
        for tp in props:
            prop = tp[0]
            count = tp[1]
            _dt = prop.proxy()  # proxy_prop(prop) #代理即可
            _dt["count"] = str(count)
            ls.append(_dt)
        return ls

    ################################################################################################################################
    ## 这里只做Actor引用，所以导出名字即可
    def stage_actors_proxy(self, actors: List[ExcelDataActor]) -> List[Dict[str, str]]:
        ls: List[Dict[str, str]] = []
        for _d in actors:
            _dt: Dict[str, str] = {}
            _dt["name"] = _d.name  ## 这里只做引用，所以导出名字即可
            ls.append(_dt)
        return ls

    ################################################################################################################################
    def serialization(self) -> Dict[str, Any]:

        data_stage: ExcelDataStage = self._stage_data_base[self._my_data["name"]]

        out_put: Dict[str, Any] = {}
        out_put["name"] = data_stage.name
        out_put["codename"] = data_stage.codename
        out_put["description"] = data_stage.description
        out_put["url"] = data_stage.localhost
        out_put["kick_off_message"] = self.kick_off_message
        out_put["stage_graph"] = self.stage_graph
        out_put["attributes"] = self.attributes

        return out_put

    ################################################################################################################################
    def proxy(self) -> Dict[str, Any]:

        data_stage: ExcelDataStage = self._stage_data_base[self._my_data["name"]]
        output: Dict[str, Any] = {}
        output["name"] = data_stage.name
        #
        props = self.stage_props_proxy(self._stage_prop)
        output["props"] = props
        #
        actors = self.stage_actors_proxy(self._actors_in_stage)
        output["actors"] = actors
        #
        return output

    #################################################################################################################################
    @property
    def excel_data(self) -> Optional[ExcelDataStage]:
        assert self._my_data is not None
        assert self._stage_data_base is not None
        return self._stage_data_base[self._my_data["name"]]

    ################################################################################################################################
    @property
    def gen_agentpy_path(self) -> Path:
        assert self.excel_data is not None
        return self.excel_data.gen_agentpy_path

    ################################################################################################################################
    @property
    def name(self) -> str:
        assert self.excel_data is not None
        return self.excel_data.name


################################################################################################################################
