import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from typing import List, Dict, Any, Optional
from game_sample.excel_data_prop import ExcelDataProp
from game_sample.excel_data_world_system import ExcelDataWorldSystem
from game_sample.excel_data_stage import ExcelDataStage
from game_sample.excel_data_actor import ExcelDataActor
from game_sample.actor_editor import ExcelEditorActor
from game_sample.stage_editor import ExcelEditorStage
from game_sample.world_system_editor import ExcelEditorWorldSystem
import pandas as pd
import game_sample.utils
from my_models.models_def import (
    EditorEntityType,
    EditorProperty,
    GameModel,
    DataBaseModel,
    GameAgentsConfigModel,
)


################################################################################################################
class ExcelEditorGame:
    def __init__(
        self,
        game_name: str,
        version: str,
        data: List[Any],
        actor_data_base: Dict[str, ExcelDataActor],
        prop_data_base: Dict[str, ExcelDataProp],
        stage_data_base: Dict[str, ExcelDataStage],
        world_system_data_base: Dict[str, ExcelDataWorldSystem],
    ) -> None:

        #
        assert data is not None
        assert actor_data_base is not None
        assert prop_data_base is not None
        assert stage_data_base is not None
        assert world_system_data_base is not None

        #
        self._name: str = game_name
        self._version: str = version
        self._data: List[Any] = data
        self._actor_data_base: Dict[str, ExcelDataActor] = actor_data_base
        self._prop_data_base: Dict[str, ExcelDataProp] = prop_data_base
        self._stage_data_base: Dict[str, ExcelDataStage] = stage_data_base
        self._world_system_data_base: Dict[str, ExcelDataWorldSystem] = (
            world_system_data_base
        )

        # 缓存数据
        self._cache_world_systems: Optional[List[ExcelEditorWorldSystem]] = None
        self._cache_players: Optional[List[ExcelEditorActor]] = None
        self._cache_actors: Optional[List[ExcelEditorActor]] = None
        self._cache_stages: Optional[List[ExcelEditorStage]] = None
        self._cache_props: Optional[List[ExcelDataProp]] = None
        self._cache_configs: Optional[List[Any]] = None

        # 构建场景的图关系。
        self._build_stage_graph()

    ############################################################################################################################
    @property
    def editor_props(self) -> List[ExcelDataProp]:

        if self._cache_props is not None:
            assert isinstance(self._cache_props, list)
            return self._cache_props

        all_props = (
            self._parse_props_from_actors(self.editor_players)
            + self._parse_props_from_actors(self.editor_actors)
            + self._parse_props_from_stages(self.editor_stages)
        )

        self._cache_props = list(set(all_props))

        return self._cache_props

    ############################################################################################################################
    @property
    def editor_world_systems(self) -> List[ExcelEditorWorldSystem]:

        if self._cache_world_systems is None:
            self._cache_world_systems = []
            for item in self._data:
                if item[EditorProperty.TYPE] != EditorEntityType.WorldSystem:
                    continue

                if item[EditorProperty.NAME] not in self._world_system_data_base:
                    assert (
                        False
                    ), f"Invalid WorldSystem name: {item[EditorProperty.NAME]}"
                    continue

                self._cache_world_systems.append(
                    ExcelEditorWorldSystem(item, self._world_system_data_base)
                )

        return self._cache_world_systems

    ############################################################################################################################
    @property
    def editor_players(self) -> List[ExcelEditorActor]:
        if self._cache_players is None:
            self._cache_players = []
            for item in self._data:
                if item[EditorProperty.TYPE] != EditorEntityType.Player:
                    continue

                if item[EditorProperty.NAME] not in self._actor_data_base:
                    assert False, f"Invalid Player name: {item[EditorProperty.NAME]}"
                    continue

                self._cache_players.append(
                    ExcelEditorActor(item, self._actor_data_base, self._prop_data_base)
                )

        return self._cache_players

    ############################################################################################################################
    @property
    def editor_actors(self) -> List[ExcelEditorActor]:
        if self._cache_actors is None:
            self._cache_actors = []
            for item in self._data:
                if item[EditorProperty.TYPE] != EditorEntityType.Actor:
                    continue

                if item[EditorProperty.NAME] not in self._actor_data_base:
                    assert False, f"Invalid Actor name: {item[EditorProperty.NAME]}"
                    continue

                self._cache_actors.append(
                    ExcelEditorActor(item, self._actor_data_base, self._prop_data_base)
                )

        return self._cache_actors

    ############################################################################################################################
    @property
    def editor_stages(self) -> List[ExcelEditorStage]:

        if self._cache_stages is None:
            self._cache_stages = []
            for item in self._data:
                if item[EditorProperty.TYPE] != EditorEntityType.Stage:
                    continue

                if item[EditorProperty.NAME] not in self._stage_data_base:
                    assert False, f"Invalid Stage name: {item[EditorProperty.NAME]}"
                    continue

                self._cache_stages.append(
                    ExcelEditorStage(
                        item,
                        self._actor_data_base,
                        self._prop_data_base,
                        self._stage_data_base,
                    )
                )

        return self._cache_stages

    ############################################################################################################################
    @property
    def editor_configs(self) -> List[Any]:
        if self._cache_configs is None:
            self._cache_configs = []
            for item in self._data:
                if item[EditorProperty.TYPE] != EditorEntityType.AboutGame:
                    continue
                self._cache_configs.append(item)
        return self._cache_configs

    ############################################################################################################################
    @property
    def about_game(self) -> str:
        if len(self.editor_configs) == 0:
            return ""
        data = self.editor_configs[0]
        if not pd.isna(data[EditorProperty.DESCRIPTION]):
            return str(data[EditorProperty.DESCRIPTION])
        return ""

    ############################################################################################################################
    def _parse_props_from_actors(
        self, actors: List[ExcelEditorActor]
    ) -> List[ExcelDataProp]:

        ret = []
        for actor in actors:
            for tp in actor.parse_actor_prop():
                prop = tp[0]
                assert prop not in ret
                if prop not in ret:
                    ret.append(prop)
        return ret

    ############################################################################################################################
    def _parse_props_from_stages(
        self, stages: List[ExcelEditorStage]
    ) -> List[ExcelDataProp]:

        ret = []
        for stage in stages:
            for tp in stage.parse_props_in_stage():
                prop = tp[0]
                assert prop not in ret
                if prop not in ret:
                    ret.append(prop)

        return ret

    ############################################################################################################################
    def gen_model(self) -> GameModel:

        return GameModel(
            save_round=0,
            players=[editor_actor.instance() for editor_actor in self.editor_players],
            actors=[editor_actor.instance() for editor_actor in self.editor_actors],
            stages=[editor_stage.instance() for editor_stage in self.editor_stages],
            world_systems=[
                editor_world_system.instance()
                for editor_world_system in self.editor_world_systems
            ],
            database=self._data_base(),
            about_game=self.about_game,
            version=self._version,
        )

    ############################################################################################################################
    def _data_base(self) -> DataBaseModel:

        return DataBaseModel(
            actors=[
                data.gen_model() for data in self.editor_players + self.editor_actors
            ],
            stages=[data.gen_model() for data in self.editor_stages],
            props=[data.gen_model() for data in self.editor_props],
            world_systems=[data.gen_model() for data in self.editor_world_systems],
        )

    ############################################################################################################################
    def write(self, directory: Path) -> int:
        return game_sample.utils.write_text_file(
            directory,
            f"{self._name}.json",
            self.gen_model().model_dump_json(),
        )

    ############################################################################################################################
    def write_agents(self, directory: Path) -> int:

        model = GameAgentsConfigModel(
            actors=[
                {actor.name: str(actor.gen_agentpy_path)}
                for actor in self.editor_players + self.editor_actors
            ],
            stages=[
                {stage.name: str(stage.gen_agentpy_path)}
                for stage in self.editor_stages
            ],
            world_systems=[
                {world_system.name: str(world_system.gen_agentpy_path)}
                for world_system in self.editor_world_systems
            ],
        )

        return game_sample.utils.write_text_file(
            directory,
            f"{self._name}_agents.json",
            model.model_dump_json(),
        )

    ############################################################################################################################
    def _get_stage_editor(self, stage_name: str) -> Optional[ExcelEditorStage]:
        for stage in self.editor_stages:
            if stage.name == stage_name:
                return stage
        return None

    ############################################################################################################################
    def _build_stage_graph(self) -> None:
        for stage_editor in self.editor_stages:

            for stage_name in stage_editor.stage_graph:

                matching_stage = self._get_stage_editor(stage_name)
                if matching_stage is None:
                    assert False, f"Invalid stage name: {stage_name}"
                    continue

                matching_stage.add_stage_graph(stage_editor.name)


############################################################################################################################
