from typing import Any, List, Optional, Dict
from my_models.entity_models import (
    ActorInstanceModel,
    StageInstanceModel,
    WorldSystemInstanceModel,
    GameModel,
    DataBaseModel,
    ActorModel,
    PropModel,
    StageModel,
    WorldSystemModel,
    SpawnerModel,
)
from pathlib import Path
import json
from loguru import logger
from my_models.file_models import (
    EntityProfileModel,
    ActorArchiveFileModel,
    StageArchiveFileModel,
)
from my_models.player_models import PlayerProxyModel
from my_models.agent_models import AgentChatHistoryDumpModel


class ActorInstanceName:

    def __init__(self, original_name: str) -> None:
        self._original_name: str = original_name

    @property
    def original_name(self) -> str:
        return self._original_name

    @property
    def real_name(self) -> str:
        return self._original_name.split("#")[0]

    @property
    def guid(self) -> int:
        return int(self._original_name.split("#")[1])


###############################################################################################################################################


class DataBase:
    """
    将所有的数据存储在这里，以便于在游戏中使用。
    """

    def __init__(self, model: Optional[DataBaseModel]) -> None:

        self._model: Optional[DataBaseModel] = model
        assert self._model is not None

        self._actors: Dict[str, ActorModel] = {}
        self._stages: Dict[str, StageModel] = {}
        self._props: Dict[str, PropModel] = {}
        self._world_systems: Dict[str, WorldSystemModel] = {}
        self._spawners: Dict[str, SpawnerModel] = {}

        self.make_dict()

    ###############################################################################################################################################
    def make_dict(self) -> None:

        assert self._model is not None
        assert self._model.actors is not None
        assert self._model.stages is not None
        assert self._model.props is not None
        assert self._model.world_systems is not None

        self._actors.clear()
        for actor in self._model.actors:
            self._actors.setdefault(actor.name, actor)

        self._stages.clear()
        for stage in self._model.stages:
            self._stages.setdefault(stage.name, stage)

        self._props.clear()
        for prop in self._model.props:
            self._props.setdefault(prop.name, prop)

        self._world_systems.clear()
        for world_system in self._model.world_systems:
            self._world_systems.setdefault(world_system.name, world_system)

        self._spawners.clear()
        for spawner in self._model.spawners:
            self._spawners.setdefault(spawner.name, spawner)

    ###############################################################################################################################################
    def get_actor(self, actor_name: str) -> Optional[ActorModel]:
        instance_name = ActorInstanceName(actor_name)
        return self._actors.get(instance_name.real_name, None)

    ###############################################################################################################################################
    def get_stage(self, stage_name: str) -> Optional[StageModel]:
        return self._stages.get(stage_name, None)

    ###############################################################################################################################################
    def get_prop(self, prop_name: str) -> Optional[PropModel]:
        return self._props.get(prop_name, None)

    ###############################################################################################################################################
    def get_world_system(self, world_system_name: str) -> Optional[WorldSystemModel]:
        return self._world_systems.get(world_system_name, None)

    ###############################################################################################################################################
    def get_spawner(self, spawner_name: str) -> Optional[SpawnerModel]:
        return self._spawners.get(spawner_name, None)


###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################
###############################################################################################################################################


class RPGGameResource:

    @staticmethod
    def generate_runtime_file_name(game_name: str) -> str:
        return f"""{game_name}_runtime.json"""

    def __init__(self, name: str, data: Any, game_runtime_dir: Path) -> None:

        # 资源的名字也是游戏的名字
        self._game_name: str = name

        # 运行时路径保存
        self._runtime_dir: Path = game_runtime_dir
        assert self._runtime_dir.exists()

        # 核心数据
        self._model = GameModel.model_validate_json(
            json.dumps(data, ensure_ascii=False)
        )

        # 数据单独处理
        self._data_base = DataBase(self._model.database)

        # 运行时模型，用于后续的存储时候用。
        self._runtime_model = self._model.model_copy(deep=True)

        # load 相关的数据结构
        self._load_dir: Optional[Path] = None
        self._load_zip_file_path: Optional[Path] = None
        self._load_chat_history_dict: Dict[str, AgentChatHistoryDumpModel] = {}
        self._load_entity_profile_dict: Dict[str, EntityProfileModel] = {}
        self._load_actor_archive_dict: Dict[str, List[ActorArchiveFileModel]] = {}
        self._load_stage_archive_dict: Dict[str, List[StageArchiveFileModel]] = {}
        self._load_player_proxy_dict: Dict[str, PlayerProxyModel] = {}

    ###############################################################################################################################################
    @property
    def data_base(self) -> DataBase:
        return self._data_base

    ###############################################################################################################################################
    @property
    def version(self) -> str:
        return self._model.version

    ###############################################################################################################################################
    @property
    def about_game(self) -> str:
        return self._model.about_game

    ###############################################################################################################################################
    @property
    def save_round(self) -> int:
        return self._model.save_round

    ###############################################################################################################################################
    @property
    def world_system_instances(self) -> List[WorldSystemInstanceModel]:
        return self._model.world_systems

    ###############################################################################################################################################
    @property
    def player_instances(self) -> List[ActorInstanceModel]:
        return self._model.players

    ###############################################################################################################################################
    @property
    def actor_instances(self) -> List[ActorInstanceModel]:
        return self._model.actors

    ###############################################################################################################################################
    def get_actor_instance(self, name: str) -> Optional[ActorInstanceModel]:
        for actor in self.actor_instances:
            if actor.name == name:
                return actor
        return None

    ###############################################################################################################################################
    @property
    def stages_instances(self) -> List[StageInstanceModel]:
        return self._model.stages

    ###############################################################################################################################################
    @property
    def is_load(self) -> bool:
        return self._load_dir is not None

    ###############################################################################################################################################
    def get_entity_profile(self, name: str) -> Optional[EntityProfileModel]:
        return self._load_entity_profile_dict.get(name, None)

    ###############################################################################################################################################
    def get_chat_history(self, name: str) -> Optional[AgentChatHistoryDumpModel]:
        return self._load_chat_history_dict.get(name, None)

    ###############################################################################################################################################
    def get_actor_archives(self, name: str) -> List[ActorArchiveFileModel]:
        return self._load_actor_archive_dict.get(name, [])

    ###############################################################################################################################################
    def get_stage_archives(self, name: str) -> List[StageArchiveFileModel]:
        return self._load_stage_archive_dict.get(name, [])

    ###############################################################################################################################################
    def get_player_proxy(self, name: str) -> Optional[PlayerProxyModel]:
        return self._load_player_proxy_dict.get(name, None)

    ###############################################################################################################################################
    def load(self, load_dir: Path, load_zip_file_path: Path) -> None:
        assert self._load_dir is None

        self._load_dir = load_dir
        self._load_zip_file_path = load_zip_file_path

        assert self._load_dir.exists()
        assert load_zip_file_path.exists()

        logger.info(f"load = {load_dir}")

        self._load_world_systems()
        self._load_player_actors()
        self._load_actors()
        self._load_stages()
        self._load_player_proxy()

        logger.info(f"load = {load_dir} done.")

    ###############################################################################################################################################
    def _load_world_systems(self) -> None:

        assert self._load_dir is not None and self._load_dir.exists()

        for world_system_instance in self.world_system_instances:

            # 载入聊天记录
            chat_history_dump_model = self._load_chat_history(
                world_system_instance.name, self._load_dir
            )
            if chat_history_dump_model is not None:
                self._load_chat_history_dict[world_system_instance.name] = (
                    chat_history_dump_model
                )

    ###############################################################################################################################################
    def _load_player_actors(self) -> None:

        assert self._load_dir is not None and self._load_dir.exists()

        for player_instance in self.player_instances:

            # 载入聊天记录
            chat_history_dump_model = self._load_chat_history(
                player_instance.name, self._load_dir
            )
            if chat_history_dump_model is not None:
                self._load_chat_history_dict[player_instance.name] = (
                    chat_history_dump_model
                )

            # 载入实体的profile
            entity_profile = self._load_entity_profile(
                player_instance.name, self._load_dir
            )
            if entity_profile is not None:
                self._load_entity_profile_dict[player_instance.name] = entity_profile

            # 载入actor的存档
            self._load_actor_archive_dict[player_instance.name] = (
                self._load_actor_archive_file(player_instance.name, self._load_dir)
            )

            # 载入stage的存档
            self._load_stage_archive_dict[player_instance.name] = (
                self._load_stage_archive_file(player_instance.name, self._load_dir)
            )

    ###############################################################################################################################################
    def _load_actors(self) -> None:

        assert self._load_dir is not None and self._load_dir.exists()

        for actor_instance in self.actor_instances:

            # 载入聊天记录
            chat_history_dump_model = self._load_chat_history(
                actor_instance.name, self._load_dir
            )

            if chat_history_dump_model is not None:
                self._load_chat_history_dict[actor_instance.name] = (
                    chat_history_dump_model
                )

            # 载入实体的profile
            entity_profile = self._load_entity_profile(
                actor_instance.name, self._load_dir
            )
            if entity_profile is not None:
                self._load_entity_profile_dict[actor_instance.name] = entity_profile

            # 载入actor的存档
            self._load_actor_archive_dict[actor_instance.name] = (
                self._load_actor_archive_file(actor_instance.name, self._load_dir)
            )

            # 载入stage的存档
            self._load_stage_archive_dict[actor_instance.name] = (
                self._load_stage_archive_file(actor_instance.name, self._load_dir)
            )

    ###############################################################################################################################################
    def _load_stages(self) -> None:

        assert self._load_dir is not None and self._load_dir.exists()

        for stage_instance in self.stages_instances:

            # 载入聊天记录
            chat_history_dump_model = self._load_chat_history(
                stage_instance.name, self._load_dir
            )
            if chat_history_dump_model is not None:
                self._load_chat_history_dict[stage_instance.name] = (
                    chat_history_dump_model
                )

            # 载入实体的profile
            entity_profile = self._load_entity_profile(
                stage_instance.name, self._load_dir
            )
            if entity_profile is not None:
                self._load_entity_profile_dict[stage_instance.name] = entity_profile

            # 载入actor的存档
            self._load_actor_archive_dict[stage_instance.name] = (
                self._load_actor_archive_file(stage_instance.name, self._load_dir)
            )

            # 载入stage的存档
            self._load_stage_archive_dict[stage_instance.name] = (
                self._load_stage_archive_file(stage_instance.name, self._load_dir)
            )

    ###############################################################################################################################################
    def _load_chat_history(
        self, name: str, load_dir: Path
    ) -> Optional[AgentChatHistoryDumpModel]:

        chat_history_file_path = load_dir / f"{name}/chat_history.json"
        if not chat_history_file_path.exists():
            return None

        content = chat_history_file_path.read_text(encoding="utf-8")
        if content is None:
            return None

        return AgentChatHistoryDumpModel.model_validate_json(content)

    ###############################################################################################################################################
    def _load_entity_profile(
        self, name: str, load_dir: Path
    ) -> Optional[EntityProfileModel]:

        entity_profile_file_path = load_dir / f"{name}/entity.json"
        if not entity_profile_file_path.exists():
            return None

        content = entity_profile_file_path.read_text(encoding="utf-8")
        if content is None:
            return None

        data = json.loads(content)
        if data is None:
            return None

        return EntityProfileModel.model_validate_json(
            json.dumps(data, ensure_ascii=False)
        )

    ###############################################################################################################################################
    def _load_stage_archive_file(
        self, name: str, load_dir: Path
    ) -> List[StageArchiveFileModel]:

        stage_archives_dir = load_dir / f"{name}/stage_archives"
        if not stage_archives_dir.exists():
            return []

        ret: List[StageArchiveFileModel] = []

        # 获得 stage_archives_dir 这个dir 下的所有后缀为.json的文件。并输入到一个列表里
        stage_archive_files = list(stage_archives_dir.glob("*.json"))
        for stage_archive_file in stage_archive_files:
            content = stage_archive_file.read_text(encoding="utf-8")
            if content is None:
                continue

            new_model = StageArchiveFileModel.model_validate_json(content)
            ret.append(new_model)

        return ret

    ###############################################################################################################################################
    def _load_actor_archive_file(
        self, name: str, load_dir: Path
    ) -> List[ActorArchiveFileModel]:

        actor_archives_dir = load_dir / f"{name}/actor_archives"
        if not actor_archives_dir.exists():
            return []

        ret: List[ActorArchiveFileModel] = []
        actor_archive_files = list(actor_archives_dir.glob("*.json"))
        for actor_archive_file in actor_archive_files:
            content = actor_archive_file.read_text(encoding="utf-8")
            if content is None:
                continue

            new_model = ActorArchiveFileModel.model_validate_json(content)
            ret.append(new_model)

        return []

    ###############################################################################################################################################
    def resolve_player_proxy_save_file_path(self, player_name: str) -> Path:
        assert self._runtime_dir.exists()
        dir = self._runtime_dir / "players"
        dir.mkdir(parents=True, exist_ok=True)
        return dir / f"""{player_name}.json"""

    ###############################################################################################################################################
    def _load_player_proxy(self) -> None:

        assert self._load_dir is not None and self._load_dir.exists()

        self._load_player_proxy_dict.clear()

        players_dir = self._load_dir / f"players"
        if not players_dir.exists():
            return

        player_proxy_files = list(players_dir.glob("*.json"))
        for player_proxy_file in player_proxy_files:
            content = player_proxy_file.read_text(encoding="utf-8")
            if content is None:
                continue

            model = PlayerProxyModel.model_validate_json(content)
            self._load_player_proxy_dict[model.name] = model

    ###############################################################################################################################################
