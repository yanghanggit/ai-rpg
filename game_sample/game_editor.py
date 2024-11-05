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
from game_sample.group_editor import ExcelEditorGroup
from game_sample.stage_editor import ExcelEditorStage
from game_sample.world_system_editor import ExcelEditorWorldSystem
import pandas as pd
import game_sample.utils
from my_models.entity_models import (
    # EditorEntityType,
    # EditorProperty,
    GameModel,
    DataBaseModel,
    # GameAgentsConfigModel,
)
from game_sample.actor_spawn_editor import ExcelEditorActorSpawn
from game_sample.spawner_editor import ExcelEditorSpawner
import game_sample.configuration as configuration
from my_models.editor_models import EditorEntityType, EditorProperty
from loguru import logger
from my_models.config_models import GameAgentsConfigModel


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
        self._cache_groups: Optional[List[ExcelEditorGroup]] = None
        self._cache_actor_spawns: Optional[List[ExcelEditorActorSpawn]] = None
        self._cache_spawners: Optional[List[ExcelEditorSpawner]] = None

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
            + self._parse_props_from_actors(
                self._gather_editor_actors_from_spawns(self.editor_actor_spawns)
            )
        )

        self._cache_props = list(set(all_props))

        return self._cache_props

    ############################################################################################################################
    @property
    def editor_world_systems(self) -> List[ExcelEditorWorldSystem]:

        if self._cache_world_systems is None:
            self._cache_world_systems = []
            for item in self._data:
                if item[EditorProperty.TYPE] != EditorEntityType.WORLD_SYSTEM:
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
                if item[EditorProperty.TYPE] != EditorEntityType.PLAYER:
                    continue

                if item[EditorProperty.NAME] not in self._actor_data_base:
                    assert False, f"Invalid Player name: {item[EditorProperty.NAME]}"
                    continue

                self._cache_players.append(
                    ExcelEditorActor(
                        data=item,
                        actor_data_base=self._actor_data_base,
                        prop_data_base=self._prop_data_base,
                    )
                )

        return self._cache_players

    ############################################################################################################################
    @property
    def editor_actors(self) -> List[ExcelEditorActor]:
        if self._cache_actors is None:
            self._cache_actors = []

            for item in self._data:
                if item[EditorProperty.TYPE] != EditorEntityType.ACTOR:
                    continue

                if item[EditorProperty.NAME] not in self._actor_data_base:
                    assert False, f"Invalid Actor name: {item[EditorProperty.NAME]}"
                    continue

                self._cache_actors.append(
                    ExcelEditorActor(
                        data=item,
                        actor_data_base=self._actor_data_base,
                        prop_data_base=self._prop_data_base,
                    )
                )

            # 扩展生成！
            self._cache_actors.extend(self._extend_group())

        return self._cache_actors

    ############################################################################################################################
    def _extend_group(self) -> List[ExcelEditorActor]:
        ret: List[ExcelEditorActor] = []
        for group in self.editor_groups:
            ret.extend(group.generate_excel_actors)
        return ret

    ############################################################################################################################
    @property
    def editor_groups(self) -> List[ExcelEditorGroup]:

        if self._cache_groups is None:
            self._cache_groups = []
            for item in self._data:
                if item[EditorProperty.TYPE] != EditorEntityType.ACTOR_GROUP:
                    continue

                self._cache_groups.append(
                    ExcelEditorGroup(item, self._actor_data_base, self._prop_data_base)
                )

        return self._cache_groups

    ############################################################################################################################
    @property
    def editor_actor_spawns(self) -> List[ExcelEditorActorSpawn]:

        if not configuration.EN_SPAWNER_FEATURE:
            return []

        if self._cache_actor_spawns is None:
            self._cache_actor_spawns = []
            for item in self._data:
                if item[EditorProperty.TYPE] != EditorEntityType.ACTOR_SPAWN:
                    continue

                self._cache_actor_spawns.append(
                    ExcelEditorActorSpawn(
                        item,
                        self._actor_data_base,
                        self._prop_data_base,
                    )
                )

        return self._cache_actor_spawns

    ############################################################################################################################

    @property
    def editor_spawners(self) -> List[ExcelEditorSpawner]:

        if not configuration.EN_SPAWNER_FEATURE:
            return []

        if self._cache_spawners is None:
            self._cache_spawners = []
            for item in self._data:
                if item[EditorProperty.TYPE] != EditorEntityType.SPAWNER:
                    continue

                self._cache_spawners.append(
                    ExcelEditorSpawner(
                        item,
                        self._actor_data_base,
                        self._prop_data_base,
                    )
                )

        return self._cache_spawners

    ############################################################################################################################
    def _gather_editor_actors_from_spawns(
        self, editor_actor_spawns: List[ExcelEditorActorSpawn]
    ) -> List[ExcelEditorActor]:
        ret: List[ExcelEditorActor] = []
        for editor_actor_spawn in editor_actor_spawns:
            ret.append(editor_actor_spawn.prototype_editor_actor)
        return ret

    ############################################################################################################################
    @property
    def editor_stages(self) -> List[ExcelEditorStage]:

        if self._cache_stages is None:
            self._cache_stages = []
            for item in self._data:
                if item[EditorProperty.TYPE] != EditorEntityType.STAGE:
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
                if item[EditorProperty.TYPE] != EditorEntityType.ABOUT_GAME:
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
    def _match_actor_spawns_and_spawners(
        self,
        editor_actor_spawns: List[ExcelEditorActorSpawn],
        editor_spawners: List[ExcelEditorSpawner],
    ) -> None:

        for spawner in editor_spawners:
            for actor_spawn in editor_actor_spawns:
                spawner.match_actor_spawner(actor_spawn)

    ############################################################################################################################
    def gen_model(self) -> GameModel:

        # 匹配组
        for group in self.editor_groups:
            for stage in self.editor_stages:
                stage.match_group(group)

        # 匹配角色生成器与生成器
        self._match_actor_spawns_and_spawners(
            self.editor_actor_spawns, self.editor_spawners
        )

        # 准备返回数据，但是 actors 与 stages 需要后续加工
        ret: GameModel = GameModel(
            save_round=0,
            players=[
                editor_actor.gen_instance() for editor_actor in self.editor_players
            ],
            actors=[],
            stages=[],
            world_systems=[
                editor_world_system.gen_instance()
                for editor_world_system in self.editor_world_systems
            ],
            database=self._data_base(),
            about_game=self.about_game,
            version=self._version,
        )

        # 添加角色的数据
        for editor_actor in self.editor_actors:
            ret.actors.append(editor_actor.gen_instance())

        # 添加场景的数据
        for editor_stage in self.editor_stages:
            ret.stages.append(editor_stage.gen_instance())

        return ret

    ############################################################################################################################
    def _data_base(self) -> DataBaseModel:

        # 准备返回数据
        ret: DataBaseModel = DataBaseModel(
            actors=[],
            stages=[data.gen_model() for data in self.editor_stages],
            props=[data.gen_model() for data in self.editor_props],
            world_systems=[data.gen_model() for data in self.editor_world_systems],
            spawners=[data.gen_model() for data in self.editor_spawners],
        )

        # 生成唯一的actor模型, 用于生成数据库
        unique_actor_model: Dict[str, ExcelEditorActor] = {}
        for data in (
            self.editor_players
            + self.editor_actors
            + self._gather_editor_actors_from_spawns(self.editor_actor_spawns)
        ):
            if data.data_base_name in unique_actor_model:
                continue
            unique_actor_model[data.data_base_name] = data

        for data in unique_actor_model.values():
            ret.actors.append(data.gen_model())

        return ret

    ############################################################################################################################
    def write(self, directory: Path) -> int:
        return game_sample.utils.write_text_file(
            directory,
            f"{self._name}.json",
            self.gen_model().model_dump_json(),
        )

    ############################################################################################################################
    def write_agents_config(self, dir: Path) -> int:

        model = GameAgentsConfigModel(actors=[], stages=[], world_systems=[])

        for actor in (
            self.editor_players
            + self.editor_actors
            + self._gather_editor_actors_from_spawns(self.editor_actor_spawns)
        ):
            model.actors.append({actor.name: f"{actor.codename}_agent.py"})

        for stage in self.editor_stages:
            model.stages.append({stage.name: f"{stage.codename}_agent.py"})

        for world_system in self.editor_world_systems:
            model.world_systems.append(
                {world_system.name: f"{world_system.codename}_agent.py"}
            )

        return game_sample.utils.write_text_file(
            dir,
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
