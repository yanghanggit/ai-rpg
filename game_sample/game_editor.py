import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from loguru import logger
import json
from typing import List, Dict, Any, Set, Optional
from game_sample.excel_data_prop import ExcelDataProp
from game_sample.excel_data_world_system import ExcelDataWorldSystem
from game_sample.excel_data_stage import ExcelDataStage
from game_sample.excel_data_actor import ExcelDataActor
from game_sample.actor_editor import ExcelEditorActor
from game_sample.stage_editor import ExcelEditorStage
from game_sample.world_system_editor import ExcelEditorWorldSystem
import pandas as pd
import game_sample.utils

EDITOR_WORLD_SYSTEM_TYPE = "WorldSystem"
EDITOR_PLAYER_TYPE = "Player"
EDITOR_ACTOR_TYPE = "Actor"
EDITOR_STAGE_TYPE = "Stage"
EDITOR_ABOUT_GAME_TYPE = "AboutGame"  # AboutGame


################################################################################################################
class ExcelEditorGame:
    def __init__(
        self,
        worldname: str,
        data: List[Any],
        actor_data_base: Dict[str, ExcelDataActor],
        prop_data_base: Dict[str, ExcelDataProp],
        stage_data_base: Dict[str, ExcelDataStage],
        world_system_data_base: Dict[str, ExcelDataWorldSystem],
    ) -> None:
        # 根数据
        self._name: str = worldname
        self._data: List[Any] = data
        self._actor_data_base: Dict[str, ExcelDataActor] = actor_data_base
        self._prop_data_base: Dict[str, ExcelDataProp] = prop_data_base
        self._stage_data_base: Dict[str, ExcelDataStage] = stage_data_base
        self._world_system_data_base: Dict[str, ExcelDataWorldSystem] = (
            world_system_data_base
        )

        # 笨一点，先留着吧。。。
        self._raw_world_systems: List[Any] = []
        self._raw_players: List[Any] = []
        self._raw_actors: List[Any] = []
        self._raw_stages: List[Any] = []
        self._raw_config: List[Any] = []

        # 真正的构建数据
        self._editor_players: List[ExcelEditorActor] = []
        self._editor_actors: List[ExcelEditorActor] = []
        self._editor_stages: List[ExcelEditorStage] = []
        self._editor_props: List[ExcelDataProp] = []
        self._editor_world_systems: List[ExcelEditorWorldSystem] = []

        ##把数据分类
        self.classify(
            self._raw_world_systems,
            self._raw_players,
            self._raw_actors,
            self._raw_stages,
            self._raw_config,
        )
        ##根据分类各种处理。。。

        # 生成角色的数据
        self._editor_players = self.create_players(self._raw_players)
        self._editor_actors = self.create_actors(self._raw_actors)

        # 生成场景的数据
        self._editor_stages = self.create_stages(self._raw_stages)

        # 生成道具的数据
        allprops = (
            self.parse_props_from_actor(self._editor_players)
            + self.parse_props_from_actor(self._editor_actors)
            + self.parse_props_from_stage(self._editor_stages)
        )
        globalnames: Set[str] = set()
        self._editor_props.clear()
        for prop in allprops:
            if prop.name not in globalnames:
                self._editor_props.append(prop)
                globalnames.add(prop.name)
        logger.debug(f"World: {self._name} has {len(self._editor_props)} props.")

        # 生成世界系统的数据
        self._editor_world_systems = self.create_world_systems(self._raw_world_systems)

        # 构建场景的图关系。
        self.make_stage_graph()

    ############################################################################################################################
    @property
    def about_game(self) -> str:
        if len(self._raw_config) == 0:
            return ""
        data = self._raw_config[0]
        about_game: str = ""
        if not pd.isna(data["description"]):
            about_game = data["description"]
        return about_game

    ############################################################################################################################
    def parse_props_from_actor(
        self, actors: List[ExcelEditorActor]
    ) -> List[ExcelDataProp]:
        res = []
        for _d in actors:
            for tp in _d._prop_data:
                prop = tp[0]
                if prop not in res:
                    res.append(prop)
        return res

    ############################################################################################################################
    def parse_props_from_stage(
        self, stages: List[ExcelEditorStage]
    ) -> List[ExcelDataProp]:
        res = []
        for stage in stages:
            for tp in stage._stage_prop:
                prop = tp[0]
                if prop not in res:
                    res.append(prop)
        return res

    ############################################################################################################################
    # 先将数据分类
    def classify(
        self,
        out_worlds: List[Any],
        out_players: List[Any],
        out_actors: List[Any],
        out_stages: List[Any],
        out_config: List[Any],
    ) -> None:
        #
        out_worlds.clear()
        out_players.clear()
        out_actors.clear()
        out_stages.clear()
        #
        for item in self._data:
            if item["type"] == EDITOR_WORLD_SYSTEM_TYPE:
                out_worlds.append(item)
            elif item["type"] == EDITOR_PLAYER_TYPE:
                out_players.append(item)
            elif item["type"] == EDITOR_ACTOR_TYPE:
                out_actors.append(item)
            elif item["type"] == EDITOR_STAGE_TYPE:
                out_stages.append(item)
            elif item["type"] == EDITOR_ABOUT_GAME_TYPE:
                out_config.append(item)
            else:
                logger.error(f"Invalid type: {item['type']}")

    ############################################################################################################################
    def create_world_systems(
        self, raw_world_systems: List[Any]
    ) -> List[ExcelEditorWorldSystem]:
        res: List[ExcelEditorWorldSystem] = []
        for item in raw_world_systems:
            if item["name"] not in self._world_system_data_base:
                logger.error(f"Invalid WorldSystem name: {item['name']}")
                continue
            res.append(ExcelEditorWorldSystem(item, self._world_system_data_base))
        return res

    ############################################################################################################################
    def create_players(self, players: List[Any]) -> List[ExcelEditorActor]:
        return self.create_actors(players)

    ############################################################################################################################
    def create_actors(self, actors: List[Any]) -> List[ExcelEditorActor]:
        res: List[ExcelEditorActor] = []
        for item in actors:
            if item["name"] not in self._actor_data_base:
                logger.error(f"Invalid  name: {item['name']}")
                continue
            editor_actor = ExcelEditorActor(
                item, self._actor_data_base, self._prop_data_base
            )
            res.append(editor_actor)
        return res

    ############################################################################################################################
    def create_stages(self, stages: List[Any]) -> List[ExcelEditorStage]:
        res: List[ExcelEditorStage] = []
        for item in stages:
            if item["name"] not in self._stage_data_base:
                logger.error(f"Invalid Stage name: {item['name']}")
                continue
            editor_stage = ExcelEditorStage(
                item, self._actor_data_base, self._prop_data_base, self._stage_data_base
            )
            res.append(editor_stage)
        return res

    ############################################################################################################################
    # 最后生成JSON
    def serialization(self) -> Dict[str, Any]:

        output: Dict[str, Any] = {}
        output["players"] = [
            editor_actor.proxy() for editor_actor in self._editor_players
        ]
        output["actors"] = [
            editor_actor.proxy() for editor_actor in self._editor_actors
        ]
        output["stages"] = [
            editor_stage.proxy() for editor_stage in self._editor_stages
        ]
        output["world_systems"] = [
            editor_world_system.proxy()
            for editor_world_system in self._editor_world_systems
        ]
        output["database"] = self.data_base()
        output["about_game"] = self.about_game

        version_sign = input("请输入版本号:")
        if version_sign == "":
            version_sign = "qwe"  # todo
            logger.warning(f"使用默认的版本号: {version_sign}")

        output["version"] = version_sign
        return output

    ############################################################################################################################
    def data_base(self) -> Dict[str, Any]:

        output: Dict[str, Any] = {}

        # 角色
        actor_data_base = self._editor_players + self._editor_actors
        output["actors"] = [data.serialization() for data in actor_data_base]

        # 场景
        output["stages"] = [data.serialization() for data in self._editor_stages]

        # 道具
        output["props"] = []
        for prop in self._editor_props:
            output["props"].append(prop.serialization())  # 要全的道具数据

        # 世界系统
        output["world_systems"] = [
            data.serialization() for data in self._editor_world_systems
        ]
        return output

    ############################################################################################################################
    def write_game_editor(self, directory: str) -> int:
        return game_sample.utils.write_text_file(
            Path(directory),
            f"{self._name}.json",
            json.dumps(self.serialization(), indent=4, ensure_ascii=False),
        )

    ############################################################################################################################
    def write_agent_list(self, directory: str) -> int:

        actors = self._editor_players + self._editor_actors
        actor_list: List[Dict[str, str]] = []
        for actor in actors:
            actor_list.append({actor.name: str(actor.gen_agentpy_path)})

        stage_list: List[Dict[str, str]] = []
        for stage in self._editor_stages:
            stage_list.append({stage.name: str(stage.gen_agentpy_path)})

        world_system_list: List[Dict[str, str]] = []
        for world_system in self._editor_world_systems:
            world_system_list.append(
                {world_system.name: str(world_system.gen_agentpy_path)}
            )

        final = {
            "actors": actor_list,
            "stages": stage_list,
            "world_systems": world_system_list,
        }
        return game_sample.utils.write_text_file(
            Path(directory),
            f"{self._name}_agents.json",
            json.dumps(final, indent=2, ensure_ascii=False),
        )

    ############################################################################################################################
    def get_stage_editor(self, stage_name: str) -> Optional[ExcelEditorStage]:
        for stage in self._editor_stages:
            if stage.name == stage_name:
                return stage
        return None

    ############################################################################################################################
    def make_stage_graph(self) -> None:

        for stage_editor in self._editor_stages:

            stage_graph = stage_editor.stage_graph
            for stage_name_in_graph in stage_graph:

                find_stage = self.get_stage_editor(stage_name_in_graph)
                assert (
                    find_stage is not None
                ), f"Invalid stage name: {stage_name_in_graph}"
                if find_stage is None:
                    logger.error(f"Invalid stage name: {stage_name_in_graph}")
                    continue

                find_stage.add_stage_graph(stage_editor.name)


############################################################################################################################
