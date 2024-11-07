import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
from typing import List, Dict, Any, Optional, Set
from game_sample.prop_data import ExcelDataProp
from game_sample.world_system_data import ExcelDataWorldSystem
from game_sample.stage_data import ExcelDataStage
from game_sample.actor_data import ExcelDataActor
from game_sample.actor_editor import ExcelEditorActor
from game_sample.stage_editor import ExcelEditorStage
from game_sample.world_system_editor import ExcelEditorWorldSystem
import pandas as pd
import game_sample.utils
from my_models.entity_models import (
    GameModel,
    DataBaseModel,
)
from game_sample.spawner_editor import ExcelEditorSpawner
from my_models.editor_models import EditorEntityType, EditorProperty
from loguru import logger
from my_models.config_models import GameAgentsConfigModel
from my_format_string.complex_name import ComplexName
from game_sample.guid_generator import editor_guid_generator
import game_sample.configuration


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
        self._cache_actor_group: Optional[Dict[str, List[ExcelEditorActor]]] = None
        self._cache_stages: Optional[List[ExcelEditorStage]] = None
        self._cache_props: Optional[List[ExcelDataProp]] = None
        self._cache_configs: Optional[List[Any]] = None
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

                assert str(item[EditorProperty.NAME]) in self._actor_data_base
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
    def global_editor_group(self) -> Dict[str, List[ExcelEditorActor]]:
        # 惰性初始化一次！
        self.editor_actors
        assert self._cache_actor_group is not None
        return self._cache_actor_group

    ############################################################################################################################
    @property
    def editor_actors(self) -> List[ExcelEditorActor]:

        if self._cache_actors is None:

            # 肯定是一起的。
            assert self._cache_actor_group is None

            # 第一次初始化
            self._cache_actors = []
            self._cache_actor_group = {}

            for item in self._data:
                if (
                    item[EditorProperty.TYPE] != EditorEntityType.ACTOR
                    and item[EditorProperty.TYPE] != EditorEntityType.GROUP
                ):
                    # 只关注角色与组
                    continue

                # 复杂的对象用于分析到底是什么
                actor_complex_identifier = ComplexName(str(item[EditorProperty.NAME]))
                if actor_complex_identifier.is_complex_name:

                    if not game_sample.configuration.EN_GROUP_FEATURE:
                        continue  # 不支持组功能

                    assert actor_complex_identifier.actor_name in self._actor_data_base

                    group_actors: List[ExcelEditorActor] = []

                    for i in range(actor_complex_identifier.group_count):
                        group_editor_actor = ExcelEditorActor(
                            data=item,
                            actor_data_base=self._actor_data_base,
                            prop_data_base=self._prop_data_base,
                            group_generation_id=editor_guid_generator.gen_actor_guid(
                                actor_complex_identifier.actor_name
                            ),
                        )

                        group_actors.append(group_editor_actor)

                    self._cache_actors.extend(group_actors)
                    self._cache_actor_group.setdefault(
                        actor_complex_identifier.group_name, []
                    ).extend(group_actors)

                else:

                    assert item[EditorProperty.NAME] in self._actor_data_base
                    assert actor_complex_identifier.actor_name in self._actor_data_base
                    self._cache_actors.append(
                        ExcelEditorActor(
                            data=item,
                            actor_data_base=self._actor_data_base,
                            prop_data_base=self._prop_data_base,
                        )
                    )

        return self._cache_actors

    ############################################################################################################################

    @property
    def editor_spawners(self) -> List[ExcelEditorSpawner]:

        if not game_sample.configuration.EN_SPAWNER_FEATURE:
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
    def gen_model(self) -> GameModel:

        duplicate_group_tracker: Dict[str, int] = {}

        # step1: 匹配角色与组 ----------------------------------------------
        if game_sample.configuration.EN_GROUP_FEATURE:

            for stage in self.editor_stages:
                matched_group_names = stage.validate_group_matches(
                    self.global_editor_group
                )
                for group_name in matched_group_names:
                    duplicate_group_tracker[group_name] = (
                        duplicate_group_tracker.get(group_name, 0) + 1
                    )

        # step2: 匹配角色生成器与生成器 ----------------------------------------------
        if game_sample.configuration.EN_SPAWNER_FEATURE:

            for spawner in self.editor_spawners:
                gather_valid_spawner_groups = spawner.gather_valid_spawner_groups(
                    self.global_editor_group
                )
                for group_name in gather_valid_spawner_groups:
                    duplicate_group_tracker[group_name] = (
                        duplicate_group_tracker.get(group_name, 0) + 1
                    )

        # 出问题就报警
        for k, v in duplicate_group_tracker.items():
            if v > 1:
                assert False, f"Invalid group name: {k}, {v}"

        # step3: 准备返回数据，但是 actors 与 stages 需要后续加工
        ret: GameModel = GameModel(
            save_round=0,
            players=[
                editor_actor.gen_instance() for editor_actor in self.editor_players
            ],
            actors=[editor_actor.gen_instance() for editor_actor in self.editor_actors],
            stages=[editor_stage.gen_instance() for editor_stage in self.editor_stages],
            world_systems=[
                editor_world_system.gen_instance()
                for editor_world_system in self.editor_world_systems
            ],
            database=self._data_base(),
            about_game=self.about_game,
            version=self._version,
        )

        # step4: 验证模型
        self._validate_model(ret)
        return ret

    ############################################################################################################################
    def _validate_model(self, model: GameModel) -> None:

        # 验证角色，如果场景里不出现就是错误
        confirmed_player_names: Set[str] = set()
        for player in model.players:
            for stage in model.stages:
                for actor in stage.actors:
                    if actor["name"] == player.name:
                        confirmed_player_names.add(player.name)

        if len(confirmed_player_names) != len(model.players):
            assert False, f"Invalid players: {model.players}, {confirmed_player_names}"

        # 验证孵化器，同时出现在2个场景里就是不对的
        validated_spawner_tracker: Dict[str, int] = {}
        for unqiue_data_base_spawn in model.database.spawners:
            for stage in model.stages:
                for spawner_in_stage in stage.spawners:
                    if unqiue_data_base_spawn.name == spawner_in_stage:
                        validated_spawner_tracker[unqiue_data_base_spawn.name] = (
                            validated_spawner_tracker.get(
                                unqiue_data_base_spawn.name, 0
                            )
                            + 1
                        )
        for k, v in validated_spawner_tracker.items():
            if v > 1:
                assert False, f"Invalid spawner name: {k}, {v}"

        # 一个角色在不同的场景出现就是错误的
        actor_frequency_count: Dict[str, int] = {}
        for stage in model.stages:
            for actor in stage.actors:
                actor_frequency_count[actor["name"]] = (
                    actor_frequency_count.get(actor["name"], 0) + 1
                )

        for k, v in actor_frequency_count.items():
            if v > 1:
                assert False, f"Invalid actor name: {k}, {v}"

        # actor instance 如果不在场景里出现，就必须在database的spawner里出现
        for actor2 in model.players + model.actors:
            if actor2.name in actor_frequency_count:
                continue

            actor_found_in_spawner = False
            for data_base_spawner in model.database.spawners:
                if actor2.name in data_base_spawner.actor_prototypes:
                    actor_found_in_spawner = True
                    logger.debug(
                        f"actor_found_in_spawner: {actor2.name}, {data_base_spawner.name}"
                    )
                    break

            assert actor_found_in_spawner, f"Invalid actor name: {actor2.name}"

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
        for data in self.editor_players + self.editor_actors:
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

        for actor in self.editor_players + self.editor_actors:
            model.actors.append({actor.agent_name: f"{actor.codename}_agent.py"})

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
